import ipaddress
import socket
import logging
from urllib.parse import urlparse
from typing import List, Tuple

logger = logging.getLogger(__name__)

# Blocked IP Networks (IPv4 and IPv6)
BLOCKED_IP_NETWORKS = [
    # IPv4 Private / Loopback / Link-Local / Multicast / Broadcast / Reserved
    ipaddress.ip_network("0.0.0.0/8"),          # Current network
    ipaddress.ip_network("10.0.0.0/8"),         # Private
    ipaddress.ip_network("100.64.0.0/10"),      # Shared Address Space (Carrier-grade NAT)
    ipaddress.ip_network("127.0.0.0/8"),        # Loopback
    ipaddress.ip_network("169.254.0.0/16"),     # Link-Local & Cloud Metadata (169.254.169.254)
    ipaddress.ip_network("172.16.0.0/12"),      # Private
    ipaddress.ip_network("192.0.0.0/24"),       # IETF Protocol Assignments
    ipaddress.ip_network("192.0.2.0/24"),       # TEST-NET-1
    ipaddress.ip_network("192.88.99.0/24"),     # 6to4 Relay Anycast
    ipaddress.ip_network("192.168.0.0/16"),     # Private
    ipaddress.ip_network("198.18.0.0/15"),      # Network benchmark tests
    ipaddress.ip_network("198.51.100.0/24"),    # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),     # TEST-NET-3
    ipaddress.ip_network("224.0.0.0/4"),        # Multicast
    ipaddress.ip_network("240.0.0.0/4"),        # Reserved for future use
    ipaddress.ip_network("255.255.255.255/32"), # Broadcast

    # IPv6 Blocked
    ipaddress.ip_network("::/128"),             # Unspecified
    ipaddress.ip_network("::1/128"),            # Loopback
    ipaddress.ip_network("fc00::/7"),           # Unique Local (ULA)
    ipaddress.ip_network("fe80::/10"),          # Link-Local
    ipaddress.ip_network("ff00::/8"),           # Multicast
]


def is_ip_blocked(ip_str: str) -> bool:
    """Check whether an IP address belongs to any blocked/private/internal range."""
    try:
        ip_obj = ipaddress.ip_address(ip_str)
        for net in BLOCKED_IP_NETWORKS:
            if ip_obj in net:
                return True
        # Also check standard python flags
        if (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_multicast
            or ip_obj.is_reserved
            or ip_obj.is_unspecified
        ):
            return True
        return False
    except ValueError:
        return True  # Malformed IP is treated as blocked


def resolve_and_validate_hostname(hostname: str) -> Tuple[bool, List[str], str]:
    """Resolve a hostname to IPs and verify none are in blocked/private ranges.

    Returns: (is_safe, resolved_ips, error_message)
    """
    if not hostname or not hostname.strip():
        return False, [], "Empty hostname"

    host = hostname.strip().lower()

    # Block localhost string explicitly
    if host in ("localhost", "127.0.0.1", "::1", "metadata.google.internal"):
        return False, [], f"Blocked internal host '{host}'"

    try:
        # Resolve address info for both IPv4 and IPv6
        addr_info = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        resolved_ips = list({res[4][0] for res in addr_info})

        if not resolved_ips:
            return False, [], f"No IP addresses resolved for '{host}'"

        for ip in resolved_ips:
            if is_ip_blocked(ip):
                logger.warning(f"SSRF Protection: Blocked resolution '{host}' -> '{ip}'")
                return False, resolved_ips, f"Host '{host}' resolved to blocked IP '{ip}'"

        return True, resolved_ips, ""
    except socket.gaierror as e:
        return False, [], f"DNS resolution failed for '{host}': {e}"
    except Exception as e:
        return False, [], f"Validation error for '{host}': {e}"


def is_safe_url(url: str) -> Tuple[bool, str]:
    """Validate full URL against SSRF rules before making outbound requests."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False, f"Unsupported scheme: {parsed.scheme}"

    hostname = parsed.hostname
    if not hostname:
        return False, "URL has no hostname"

    is_safe, ips, err = resolve_and_validate_hostname(hostname)
    if not is_safe:
        return False, f"SSRF Blocked: {err}"

    return True, ""
