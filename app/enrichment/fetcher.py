import asyncio
import logging
import time
from urllib.parse import urljoin, urlparse
from typing import Dict, Optional
import httpx

from app.config.settings import Settings, get_settings
from app.enrichment.parser import parse_html_metadata
from app.enrichment.ssrf import is_safe_url
from app.models.schemas import FetchResult, FetchStatus, StructuredMetadata

logger = logging.getLogger(__name__)


class HostRateLimiter:
    """Per-host rate limiter ensuring batch jobs do not hammer any single domain."""

    def __init__(self, min_interval_seconds: float = 0.5):
        self.min_interval = min_interval_seconds
        self._last_request_time: Dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def throttle(self, hostname: str) -> None:
        if not hostname:
            return
        async with self._lock:
            now = time.time()
            last_time = self._last_request_time.get(hostname, 0.0)
            elapsed = now - last_time
            if elapsed < self.min_interval:
                wait_time = self.min_interval - elapsed
                await asyncio.sleep(wait_time)
            self._last_request_time[hostname] = time.time()


class HTTPMetadataFetcher:
    """Layer 1: SSRF-protected, streaming HTTP fetcher with redirect tracing and structured output."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        rate_limiter: Optional[HostRateLimiter] = None,
    ):
        self.settings = settings or get_settings()
        self.rate_limiter = rate_limiter or HostRateLimiter(min_interval_seconds=0.3)

    async def fetch(self, input_url_or_domain: str) -> FetchResult:
        """Execute Layer 1 HTTP metadata extraction for any URL or domain."""
        raw = input_url_or_domain.strip()
        if not raw:
            return FetchResult(
                url=raw,
                domain="",
                fetch_status=FetchStatus.ERROR,
                error_message="Empty URL or domain provided",
            )

        # Ensure scheme
        if not raw.startswith("http://") and not raw.startswith("https://"):
            initial_url = f"https://{raw}"
        else:
            initial_url = raw

        parsed = urlparse(initial_url)
        initial_host = parsed.hostname or raw

        # Apply per-host rate limiting
        await self.rate_limiter.throttle(initial_host)

        # Attempt HTTPS first, fallback to HTTP
        urls_to_try = [initial_url]
        if initial_url.startswith("https://"):
            urls_to_try.append(initial_url.replace("https://", "http://", 1))

        last_error_type = FetchStatus.ERROR
        last_error_msg = None
        last_status_code = None
        final_destination = initial_url

        max_redirects = self.settings.ENRICHMENT_MAX_REDIRECTS
        max_bytes = self.settings.ENRICHMENT_MAX_RESPONSE_BYTES
        timeout = httpx.Timeout(self.settings.ENRICHMENT_TIMEOUT_SECONDS)

        headers = {
            "User-Agent": self.settings.ENRICHMENT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        for attempt_url in urls_to_try:
            current_url = attempt_url
            redirect_count = 0

            try:
                # SSRF Check on initial URL
                is_safe, err_msg = is_safe_url(current_url)
                if not is_safe:
                    logger.warning(f"SSRF blocked initial URL '{current_url}': {err_msg}")
                    return FetchResult(
                        url=input_url_or_domain,
                        domain=initial_host,
                        final_url=current_url,
                        fetch_status=FetchStatus.SSRF_BLOCKED,
                        error_message=f"SSRF Blocked: {err_msg}",
                    )

                async with httpx.AsyncClient(
                    timeout=timeout,
                    follow_redirects=False,
                    verify=True,
                ) as client:
                    while redirect_count <= max_redirects:
                        final_destination = current_url
                        curr_parsed = urlparse(current_url)
                        curr_host = curr_parsed.hostname or ""

                        # Re-verify SSRF for redirect destination
                        is_safe, err_msg = is_safe_url(current_url)
                        if not is_safe:
                            logger.warning(f"SSRF blocked redirect target '{current_url}': {err_msg}")
                            return FetchResult(
                                url=input_url_or_domain,
                                domain=curr_host,
                                final_url=current_url,
                                fetch_status=FetchStatus.SSRF_BLOCKED,
                                error_message=f"SSRF Blocked on redirect: {err_msg}",
                            )

                        response = await client.get(current_url, headers=headers)
                        last_status_code = response.status_code

                        # Handle Redirects manually to preserve security & record final URL
                        if response.is_redirect:
                            location = response.headers.get("location")
                            if not location:
                                break
                            current_url = urljoin(current_url, location)
                            redirect_count += 1
                            if redirect_count > max_redirects:
                                return FetchResult(
                                    url=input_url_or_domain,
                                    domain=urlparse(current_url).hostname or initial_host,
                                    final_url=current_url,
                                    http_status=response.status_code,
                                    fetch_status=FetchStatus.ERROR,
                                    error_message=f"Exceeded max redirects ({max_redirects})",
                                )
                            continue

                        # Check HTTP status error
                        if response.status_code >= 400:
                            return FetchResult(
                                url=input_url_or_domain,
                                domain=curr_host,
                                final_url=current_url,
                                http_status=response.status_code,
                                fetch_status=FetchStatus.HTTP_ERROR,
                                error_message=f"HTTP {response.status_code}",
                            )

                        # Read stream up to byte cap
                        content_bytes = response.content[:max_bytes]
                        try:
                            html_text = content_bytes.decode(response.encoding or "utf-8", errors="replace")
                        except Exception:
                            html_text = content_bytes.decode("utf-8", errors="replace")

                        metadata = parse_html_metadata(html_text)
                        return FetchResult(
                            url=input_url_or_domain,
                            domain=curr_host,
                            http_status=response.status_code,
                            final_url=current_url,
                            fetch_status=FetchStatus.SUCCESS,
                            metadata=metadata,
                        )

            except httpx.TimeoutException:
                last_error_type = FetchStatus.TIMEOUT
                last_error_msg = "Request timed out"
                logger.info(f"Layer 1 HTTP timeout for {current_url}")
            except httpx.ConnectError as e:
                last_error_type = FetchStatus.DNS_FAILURE
                last_error_msg = f"Connection/DNS failed: {e}"
                logger.info(f"Layer 1 HTTP connection failure for {current_url}: {e}")
            except Exception as e:
                last_error_type = FetchStatus.ERROR
                last_error_msg = str(e)
                logger.warning(f"Layer 1 HTTP unexpected error for {current_url}: {e}")

        # If all attempts failed, return structured failure
        final_host = urlparse(final_destination).hostname or initial_host
        return FetchResult(
            url=input_url_or_domain,
            domain=final_host,
            http_status=last_status_code,
            final_url=final_destination,
            fetch_status=last_error_type,
            metadata=StructuredMetadata(),
            error_message=last_error_msg or "Failed to fetch website metadata",
        )


# Backward compatibility alias
SafeHTTPFetcher = HTTPMetadataFetcher
