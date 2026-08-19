import json
import logging
import re
from typing import Any, Dict, Optional, Tuple
import httpx

from app.config.settings import Settings, get_settings
from app.models.category import ALLOWED_CATEGORY_NAMES, get_category_id_by_name
from app.models.schemas import ClassificationStatus, LLMClassificationOutput

logger = logging.getLogger(__name__)


class OpenRouterLLMClient:
    """Async client for OpenRouter API with strict output validation."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.api_key = self.settings.OPENROUTER_API_KEY
        self.base_url = self.settings.OPENROUTER_BASE_URL.rstrip("/")
        self.model = self.settings.OPENROUTER_MODEL

    def _extract_json(self, raw_text: str) -> Optional[dict]:
        """Extract and parse JSON from model output string."""
        if not raw_text:
            return None
        text = raw_text.strip()
        # Remove potential markdown code fences
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
        return None

    async def generate_classification(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> Tuple[Optional[LLMClassificationOutput], Dict[str, Any]]:
        """Call OpenRouter chat completions endpoint and return validated structured classification."""
        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY not configured. Falling back to NEEDS_REVIEW status.")
            return (
                LLMClassificationOutput(
                    domain="unknown",
                    category=None,
                    category_id=None,
                    confidence=0.0,
                    status=ClassificationStatus.NEEDS_REVIEW,
                    reason="OpenRouter API key is not configured.",
                ),
                {"error": "No API key configured"},
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://domain-categorization-service.internal",
            "X-Title": "Domain Categorization AI",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }

        metadata: Dict[str, Any] = {
            "model": self.model,
            "tokens": None,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )

                if response.status_code != 200:
                    logger.error(
                        f"OpenRouter API error {response.status_code}: {response.text}"
                    )
                    metadata["error"] = f"HTTP {response.status_code}"
                    return (
                        LLMClassificationOutput(
                            domain="unknown",
                            category=None,
                            category_id=None,
                            confidence=0.0,
                            status=ClassificationStatus.ERROR,
                            reason=f"LLM API returned status {response.status_code}",
                        ),
                        metadata,
                    )

                res_json = response.json()
                usage = res_json.get("usage", {})
                metadata["usage"] = usage

                choices = res_json.get("choices", [])
                if not choices:
                    return None, {"error": "Empty choices from LLM"}

                content = choices[0].get("message", {}).get("content", "")
                parsed_dict = self._extract_json(content)

                if not parsed_dict:
                    logger.error(f"Failed to parse JSON from LLM response: {content}")
                    return (
                        LLMClassificationOutput(
                            domain="unknown",
                            category=None,
                            category_id=None,
                            confidence=0.0,
                            status=ClassificationStatus.ERROR,
                            reason="Malformed JSON received from LLM",
                        ),
                        metadata,
                    )

                # Validate category strictly against the 10 allowed (or None/unclassified)
                cat = parsed_dict.get("category")
                if cat in ("No Category Found", "Unclassified", "UNCLASSIFIED", "null", "None", "", "N/A", None):
                    parsed_dict["category"] = None
                    parsed_dict["category_id"] = None
                    parsed_dict["status"] = ClassificationStatus.UNCLASSIFIED.value
                elif cat not in ALLOWED_CATEGORY_NAMES:
                    logger.warning(f"Invalid category '{cat}' returned by LLM. Marking UNCLASSIFIED.")
                    parsed_dict["category"] = None
                    parsed_dict["category_id"] = None
                    parsed_dict["status"] = ClassificationStatus.UNCLASSIFIED.value

                result = LLMClassificationOutput(**parsed_dict)
                return result, metadata

        except httpx.TimeoutException:
            logger.warning("OpenRouter API request timed out")
            metadata["error"] = "Timeout"
            return (
                LLMClassificationOutput(
                    domain="unknown",
                    category=None,
                    category_id=None,
                    confidence=0.0,
                    status=ClassificationStatus.ERROR,
                    reason="LLM request timed out",
                ),
                metadata,
            )
        except Exception as e:
            logger.exception(f"OpenRouter client invocation error: {e}")
            metadata["error"] = str(e)
            return (
                LLMClassificationOutput(
                    domain="unknown",
                    category=None,
                    category_id=None,
                    confidence=0.0,
                    status=ClassificationStatus.ERROR,
                    reason=f"LLM invocation error: {e}",
                ),
                metadata,
            )
