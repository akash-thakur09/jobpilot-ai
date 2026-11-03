import ipaddress
import re
import socket
import urllib.parse
from typing import Tuple, Optional, List, Dict, Any
import httpx
import httpcore
from httpcore._backends.anyio import AnyIOBackend
import xml.etree.ElementTree as ET

from backend.app.core.logging import logger


class SSRFProtectionError(ValueError):
    """Raised when a URL targets a disallowed, private, loopback, or metadata destination."""
    pass


class SSRFSafeNetworkBackend(AnyIOBackend):
    """
    Custom AnyIO network backend that intercepts socket connections before HTTP transmission.
    Validates the actual remote IP address returned by OS getaddrinfo/connect against SSRF rules,
    defeating DNS rebinding (TOCTOU) attacks where hostname resolution changes after URL validation.
    """
    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: Optional[float] = None,
        local_address: Optional[str] = None,
        socket_options: Optional[Any] = None,
    ):
        stream = await super().connect_tcp(
            host=host,
            port=port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )
        server_addr = stream.get_extra_info("server_addr")
        if server_addr:
            ip_str = str(server_addr[0])
            is_safe, reason = SafeFeedFetcher.is_safe_ip(ip_str)
            if not is_safe:
                await stream.aclose()
                raise SSRFProtectionError(
                    f"Connection established to prohibited peer IP {ip_str}: {reason}"
                )
        return stream


class SSRFSafeTransport(httpx.AsyncHTTPTransport):
    """
    HTTPX transport enforcing socket-level IP validation via SSRFSafeNetworkBackend.
    Ensures TLS SNI and server certificate verification use original hostname
    while TCP connections to private, loopback, or metadata endpoints are dropped immediately.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=self._pool._ssl_context,
            max_connections=self._pool._max_connections,
            max_keepalive_connections=self._pool._max_keepalive_connections,
            keepalive_expiry=self._pool._keepalive_expiry,
            http1=True,
            http2=False,
            retries=0,
            network_backend=SSRFSafeNetworkBackend(),
        )


def sanitize_url_for_logging(url: str) -> str:
    """
    Masks credentials and sensitive query tokens for safe logging.
    """
    if not url:
        return ""
    try:
        parsed = urllib.parse.urlsplit(url)
        netloc = parsed.netloc
        if "@" in netloc:
            netloc = netloc.split("@")[-1]
        query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        sensitive_keys = {"token", "key", "secret", "api_key", "auth", "password", "pwd", "credential"}
        sanitized_pairs = []
        for k, v in query_pairs:
            if any(s in k.lower() for s in sensitive_keys):
                sanitized_pairs.append((k, "***"))
            else:
                sanitized_pairs.append((k, v))
        sanitized_query = urllib.parse.urlencode(sanitized_pairs, safe="*")
        return urllib.parse.urlunsplit((parsed.scheme, netloc, parsed.path, sanitized_query, parsed.fragment))
    except Exception:
        return "[unparseable-url]"


def safe_parse_xml(xml_content: str) -> ET.Element:
    """
    Safely parses XML text while strictly preventing XML External Entity (XXE) injection
    and Billion Laughs / quadratic entity expansion attacks.
    Prohibits DOCTYPE and ENTITY declarations.
    """
    if not xml_content or not isinstance(xml_content, str):
        raise ValueError("XML content must be a non-empty string.")

    if re.search(r"<!(?:DOCTYPE|ENTITY)", xml_content, re.IGNORECASE):
        raise ValueError("XML parsing error: DOCTYPE and ENTITY declarations are prohibited for security.")

    parser = ET.XMLParser()
    return ET.fromstring(xml_content, parser=parser)


class SafeFeedFetcher:
    """
    Security-hardened HTTP client for fetching external RSS, Atom, XML, and JSON feeds.

    Protections:
    - Enforces HTTPS by default.
    - Rejects localhost, 127.0.0.0/8, and loopback addresses.
    - Rejects RFC 1918 private IPv4 subnets (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16).
    - Rejects link-local subnets (169.254.0.0/16, fe80::/10).
    - Rejects cloud metadata endpoints (169.254.169.254, 169.254.170.2, 100.100.100.200, metadata.google.internal).
    - Rejects embedded URL credentials (user:pass@host).
    - Performs pre-request DNS resolution validation across all returned A/AAAA records.
    - Performs connection-time socket peer IP validation via SSRFSafeNetworkBackend to defeat DNS rebinding.
    - Preserves TLS SNI and certificate chain verification with target server.
    - Validates each hop in redirect chains (revalidating destination scheme, DNS, and IP).
    - Enforces maximum response byte limits (streaming) to prevent memory exhaustion / decompression bombs.
    - Enforces hard timeout limits.
    """

    MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 Megabytes
    DEFAULT_TIMEOUT_SECONDS = 15.0
    MAX_REDIRECTS = 5

    BLOCKED_HOSTNAMES = {
        "localhost",
        "localhost.localdomain",
        "metadata.google.internal",
        "instance-data",
        "metadata.internal",
    }

    BLOCKED_IPS = {
        "169.254.169.254",  # AWS/GCP/Azure/OCI instance metadata
        "169.254.170.2",    # AWS ECS task metadata
        "100.100.100.200",  # Alibaba Cloud metadata
    }

    @classmethod
    def is_safe_ip(cls, ip_str: str) -> Tuple[bool, Optional[str]]:
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return False, f"Malformed IP address: {ip_str}"

        # Check IPv4-mapped IPv6 (e.g., ::ffff:127.0.0.1)
        if isinstance(ip, ipaddress.IPv6Address):
            if ip.ipv4_mapped:
                return cls.is_safe_ip(str(ip.ipv4_mapped))
            # Check 6to4 embedded IPv4 (2002::/16)
            if ip in ipaddress.ip_network("2002::/16"):
                embedded_v4 = ipaddress.ip_address(ip.packed[2:6])
                is_v4_safe, reason = cls.is_safe_ip(str(embedded_v4))
                if not is_v4_safe:
                    return False, f"6to4 embedded IPv4 address {embedded_v4} is prohibited: {reason}"

        if ip_str in cls.BLOCKED_IPS:
            return False, f"Cloud metadata IP address {ip_str} is prohibited."
        if ip.is_loopback:
            return False, f"Loopback address {ip_str} is prohibited."
        if ip.is_private:
            return False, f"Private network address {ip_str} is prohibited."
        if ip.is_link_local:
            return False, f"Link-local address {ip_str} is prohibited."
        if ip.is_multicast:
            return False, f"Multicast address {ip_str} is prohibited."
        if ip.is_reserved:
            return False, f"Reserved address {ip_str} is prohibited."
        if ip.is_unspecified:
            return False, f"Unspecified address {ip_str} is prohibited."

        return True, None

    @classmethod
    def validate_url(cls, url: str, allow_http: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Validates URL against SSRF attack vectors.
        """
        if not url or not isinstance(url, str):
            return False, "URL must be a non-empty string."

        clean_url = url.strip()
        try:
            parsed = urllib.parse.urlsplit(clean_url)
        except Exception as e:
            return False, f"Invalid URL structure: {e}"

        # Reject URL credentials
        if parsed.username or parsed.password:
            return False, "URLs with embedded credentials (username/password) are prohibited."

        scheme = (parsed.scheme or "").lower()
        if allow_http:
            if scheme not in ("http", "https"):
                return False, f"Unsupported URL scheme '{scheme}'. Only HTTP and HTTPS are permitted."
        else:
            if scheme != "https":
                return False, f"Disallowed URL scheme '{scheme}'. HTTPS is required by default for feed security."

        hostname = parsed.hostname
        if not hostname:
            return False, "URL is missing a valid hostname."

        hn_lower = hostname.lower().rstrip(".")
        if hn_lower in cls.BLOCKED_HOSTNAMES:
            return False, f"Access to restricted hostname '{hostname}' is prohibited."

        if hn_lower.endswith(".localhost") or hn_lower.endswith(".local") or hn_lower.endswith(".internal"):
            return False, f"Access to internal domain '{hostname}' is prohibited."

        # If hostname is directly an IP address
        try:
            is_ip = True
            ipaddress.ip_address(hn_lower)
        except ValueError:
            is_ip = False

        if is_ip:
            is_safe, reason = cls.is_safe_ip(hn_lower)
            if not is_safe:
                return False, reason
            return True, None

        # Resolve DNS to check resulting IPs
        try:
            addr_infos = socket.getaddrinfo(hn_lower, None)
        except socket.gaierror as dns_err:
            return False, f"DNS resolution failed for hostname '{hostname}': {dns_err}"
        except Exception as e:
            return False, f"Host resolution error for '{hostname}': {e}"

        if not addr_infos:
            return False, f"Could not resolve any IP addresses for hostname '{hostname}'"

        for info in addr_infos:
            resolved_ip = info[4][0]
            is_safe, reason = cls.is_safe_ip(resolved_ip)
            if not is_safe:
                return False, f"Hostname '{hostname}' resolves to restricted IP {resolved_ip}: {reason}"

        return True, None

    @classmethod
    async def fetch_text(
        cls,
        url: str,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        headers: Optional[Dict[str, str]] = None,
        allow_http: bool = False,
    ) -> Tuple[str, str]:
        """
        Securely fetches URL content as text with SSRF validation, connection-level IP verification,
        redirect revalidation, and response byte cap.

        Returns:
            (content_type, body_text)
        """
        current_url = url.strip()
        req_headers = {
            "User-Agent": "JobPilot-AI-Agent/2.0 (Candidate Feed Reader; +https://github.com/jobpilot)",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, application/json, text/xml, text/plain;q=0.9",
        }
        if headers:
            req_headers.update(headers)

        effective_timeout = min(timeout_seconds, cls.DEFAULT_TIMEOUT_SECONDS)

        for redirect_count in range(cls.MAX_REDIRECTS + 1):
            # 1. Revalidate current_url on every hop
            is_valid, reason = cls.validate_url(current_url, allow_http=allow_http)
            if not is_valid:
                raise SSRFProtectionError(f"SSRF Protection: Blocked target '{current_url}': {reason}")

            transport = SSRFSafeTransport(verify=True)
            async with httpx.AsyncClient(
                transport=transport,
                timeout=effective_timeout,
                follow_redirects=False,
                headers=req_headers,
            ) as client:
                try:
                    async with client.stream("GET", current_url) as resp:
                        # 2. Check for redirect
                        if resp.status_code in (301, 302, 303, 307, 308):
                            if redirect_count >= cls.MAX_REDIRECTS:
                                raise SSRFProtectionError(f"Exceeded maximum redirect limit of {cls.MAX_REDIRECTS}")

                            loc = resp.headers.get("Location")
                            if not loc:
                                raise SSRFProtectionError("Redirect response received without Location header.")

                            # Resolve relative redirect
                            next_url = urllib.parse.urljoin(current_url, loc)
                            clean_current = sanitize_url_for_logging(current_url)
                            clean_next = sanitize_url_for_logging(next_url)
                            logger.info(f"[SafeFeedFetcher] Following redirect from {clean_current} to {clean_next}")
                            current_url = next_url
                            continue

                        if resp.status_code == 429:
                            from backend.app.collectors.base import SourceRateLimitException
                            retry_after = resp.headers.get("Retry-After")
                            seconds = int(retry_after) if retry_after and retry_after.isdigit() else 60
                            raise SourceRateLimitException("Target feed returned HTTP 429 Too Many Requests", retry_after_seconds=seconds)

                        resp.raise_for_status()

                        # 3. Check Content-Length header if present
                        cl_header = resp.headers.get("content-length")
                        if cl_header and cl_header.isdigit():
                            if int(cl_header) > cls.MAX_RESPONSE_BYTES:
                                raise ValueError(
                                    f"Feed Content-Length {cl_header} exceeds maximum limit of {cls.MAX_RESPONSE_BYTES} bytes."
                                )

                        # 4. Read stream enforcing byte limit on decoded content
                        content_type = resp.headers.get("content-type", "").lower()
                        chunks = bytearray()
                        async for chunk in resp.aiter_bytes():
                            if len(chunks) + len(chunk) > cls.MAX_RESPONSE_BYTES:
                                raise ValueError(
                                    f"Feed response exceeded maximum size limit of {cls.MAX_RESPONSE_BYTES} bytes."
                                )
                            chunks.extend(chunk)

                        charset = resp.encoding or "utf-8"
                        try:
                            text_body = chunks.decode(charset, errors="replace")
                        except Exception:
                            text_body = chunks.decode("utf-8", errors="replace")

                        return content_type, text_body

                except SSRFProtectionError:
                    raise
                except httpx.ConnectError as conn_err:
                    cur: Optional[BaseException] = conn_err
                    while cur:
                        if isinstance(cur, SSRFProtectionError):
                            raise cur
                        cur = getattr(cur, "__cause__", None) or getattr(cur, "__context__", None)
                    raise

        raise SSRFProtectionError("Unexpected termination of redirect loop.")
