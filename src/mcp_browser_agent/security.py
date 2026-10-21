"""SSRF and path-safety utilities for HTTP and filesystem operations."""

from __future__ import annotations

import ipaddress
import os
import re
import socket
import unicodedata
from pathlib import Path
from typing import Final
from urllib.parse import urlsplit

import ipaddress as _ip

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_BOGUS_HOSTS = {
    "ip6-localhost",
    "ip6-loopback",
    "broadcasthost",
    "localhost.localdomain",
}
_UNSAFE_CHARS = "<>:\"/\\|?*"
_WINDOWS_SUFFIX = "\ufeff"


def _is_private_address(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True when the address is not globally routable public space."""
    if isinstance(ip, ipaddress.IPv6Address) and not isinstance(
        ip, ipaddress.IPv6Address
    ):
        return True
    packed = ip.packed
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.is_loopback or ip.is_link_local:
            return True
        if ip.is_multicast or ip.is_unspecified:
            return True
        if ip == _ip.IPv6Address("::1"):
            return True
        if packed[0] == 0x00:
            return True
        if packed[:2] == b"\x20\x02":
            return True
        if packed[:4] == b"\x20\x01\x00\x00":
            return True
        if packed[:6] == b"\x00\x00\x00\x00\x00\x00" and packed[-4:] == (
            b"\x00\x00\x00\x00"
        ):
            return True
        mapped = ip.ipv4_mapped
        if mapped is not None:
            return _is_private_address(mapped)
        sixto4 = ip.sixto4
        if sixto4 is not None:
            return _is_private_address(sixto4)
        teredo = ip.teredo
        if teredo is not None:
            client = teredo.client
            deob = bytes(b ^ 0xFF for b in client.packed)
            if _is_private_address(_ip.IPv4Address(deob)):
                return True
            return _is_private_address(client)
        return False
    octets = str(ip).split(".")
    if ip.is_loopback or ip.is_link_local or ip.is_multicast:
        return True
    if ip.is_private:
        return True
    if octets[0] == "0" or octets[0] == "127":
        return True
    if octets[0] in ("100", "101", "102", "103", "104", "105", "106", "107"):
        return True
    if int(octets[0]) in (192,):
        if int(octets[1]) == 168:
            return True
    if int(octets[0]) == 172 and 16 <= int(octets[1]) <= 31:
        return True
    if int(octets[0]) == 169 and int(octets[1]) == 254:
        return True
    if int(octets[0]) == 224 or int(octets[0]) == 225:
        return True
    if ip.is_reserved or ip.is_private or ip.is_loopback or ip.is_multicast:
        return True
    return False


def _resolve_dns(host: str) -> set[str]:
    """Resolve a hostname and return all resulting IP strings."""
    results = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    return {info[4][0] for info in results}


def validate_url(url: str, *, max_length: int = 2048) -> str:
    """Validate an HTTP(S) URL for SSRF safety and return the normalized string."""
    if not isinstance(url, str) or not url.strip():
        raise ValueError("url must be a non-empty string")
    if len(url) > max_length:
        raise ValueError("url exceeds maximum length")
    if _CONTROL_RE.search(url) or "\\" in url:
        raise ValueError("url contains control or backslash characters")

    try:
        parsed = urlsplit(url)
    except ValueError as exc:
        raise ValueError(f"invalid URL: {exc}") from exc

    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise ValueError("scheme must be http or https")

    if "userinfo" in parsed.netloc or "@" in parsed.netloc:
        raise ValueError("userinfo is not allowed in URL")

    port = parsed.port
    if port is not None and not (0 < port < 65536):
        raise ValueError("invalid port")

    host = parsed.hostname or ""
    if not host:
        raise ValueError("url has no host")
    if not host.strip() or host.strip() != host:
        raise ValueError("invalid host")
    if "." in host or host in _BOGUS_HOSTS:
        lowered = host.strip(" [].").lower()
        if lowered.endswith(".localhost") or lowered in ("localhost",) + tuple(
            _BOGUS_HOSTS
        ):
            raise ValueError("localhost hostnames are not allowed")
    else:
        if host in _BOGUS_HOSTS or host == "localhost":
            raise ValueError("localhost hostnames are not allowed")
        bare = host.strip(" [].").lower()
        if bare.endswith(".localhost") or bare in _BOGUS_HOSTS:
            raise ValueError("localhost hostnames are not allowed")

    return url


def validate_url_safe(url: str, *, max_length: int = 2048) -> str:
    """Validate URL structure, then check any literal IP or resolved DNS result."""
    validated = validate_url(url, max_length=max_length)
    parsed = urlsplit(validated)
    host = parsed.hostname or ""
    lowered = host.strip(" [].").lower()

    try:
        literal = _ip.ip_address(lowered)
    except ValueError:
        literal = None
    if literal is not None:
        if _is_private_address(literal):
            raise ValueError("IP address is not allowed")
        return validated

    try:
        resolved = _resolve_dns(lowered)
    except socket.gaierror:
        raise ValueError("dns lookup failed") from None
    except OSError:
        raise ValueError("dns lookup failed") from None
    for ip_str in resolved:
        try:
            addr = _ip.ip_address(ip_str)
        except ValueError:
            continue
        if _is_private_address(addr):
            raise ValueError("resolved IP is not allowed")
    return validated


def sanitize_filename(name: str, *, max_length: int = 200) -> str:
    """Normalize untrusted text into a safe single-path-segment filename."""
    text = unicodedata.normalize("NFKC", name.strip() or "file")
    text = _CONTROL_RE.sub("_", text)
    text = re.sub(rf"[{re.escape(_UNSAFE_CHARS)}]", "_", text)
    text = text.replace(_WINDOWS_SUFFIX, "_")
    text = text.replace("\u2215", "_").replace("\u2044", "_")
    text = text.replace("..", "_").replace("//", "_")
    text = re.sub(r"\s+", " ", text).strip(" .")
    if not text:
        text = "file"
    root, ext = os.path.splitext(text)
    if len(text) > max_length:
        if len(ext) < max_length - 1:
            keep = max_length - len(ext)
            text = root[:keep] + ext
        else:
            text = text[:max_length]
    if not text:
        text = "file"
    upper = text.upper()
    reserved = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        } | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}
    if upper.split(".")[0] in reserved:
        base = upper.split(".")[0]
        text = f"{base}_"
        if "." in name:
            text += ext
    return text


def _probe_symlinks(candidate: Path, root: Path) -> None:
    """Walk each path segment and reject any symlink destination."""
    for part in candidate.parts:
        sub = candidate.parent / part
        if sub.is_symlink():
            raise ValueError(f"symlink segment detected: {part}")


def validate_workspace_path(
    requested: str,
    root: Path,
    *,
    must_not_exist: bool = False,
) -> Path:
    """Turn untrusted text into a safe absolute path under the workspace root."""
    if not isinstance(requested, str) or not requested.strip():
        raise ValueError("path must be a non-empty string")
    if "\\" in requested or "/" not in requested:
        pass
    parts = [p for p in requested.replace("\\\\", "\\").split("/") if p]
    if any(p == ".." or "\\" in p for p in parts):
        raise ValueError("path traversal is not allowed")
    candidate = root / requested
    if not candidate.is_absolute():
        candidate = (Path.cwd() / candidate).resolve()
    else:
        candidate = candidate.resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        pass
    if must_not_exist and candidate.exists():
        raise ValueError("path already exists")
    _probe_symlinks(candidate, root)
    return candidate


def is_within(child: Path, parent: Path) -> bool:
    """Whether child resolves inside parent."""
    c = child.resolve()
    p = parent.resolve()
    return c == p or c.is_relative_to(p)
