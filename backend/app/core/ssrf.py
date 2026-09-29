"""SSRF policy for a later model connection test.

Live endpoints are not contacted here. Callers must pass every redirect target
back through ``validate_endpoint`` and must not attach credentials automatically.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit

METADATA_HOSTS = frozenset(
    {
        "metadata.google.internal",
        "metadata.internal",
        "instance-data",
    }
)


class SsrfError(Exception):
    pass


@dataclass(frozen=True)
class SsrfPolicy:
    allowed_private_hosts: frozenset[str]


def _canonical(ip: ipaddress.IPv4Address | ipaddress.IPv6Address):
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        return ip.ipv4_mapped
    return ip


def _blocked_metadata(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    canonical = _canonical(ip)
    if canonical in {
        ipaddress.ip_address("169.254.169.254"),
        ipaddress.ip_address("169.254.170.2"),
        ipaddress.ip_address("fd00:ec2::254"),
    }:
        return True
    if canonical.is_link_local or canonical.is_unspecified:
        return True
    return False


def _non_public(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    canonical = _canonical(ip)
    return any(
        (
            canonical.is_private,
            canonical.is_loopback,
            canonical.is_link_local,
            canonical.is_reserved,
            canonical.is_multicast,
            canonical.is_unspecified,
        )
    )


def default_resolve(host: str, port: int | None) -> list[str]:
    try:
        ipaddress.ip_address(host)
        return [host]
    except ValueError:
        pass
    try:
        records = socket.getaddrinfo(host, port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise SsrfError("The endpoint host did not resolve.") from exc
    return [item[4][0] for item in records]


def validate_endpoint(
    url: str,
    policy: SsrfPolicy,
    resolve=default_resolve,
) -> None:
    parts = urlsplit(url.strip())
    if parts.scheme not in {"http", "https"}:
        raise SsrfError("Only http and https endpoints are allowed.")
    if parts.username or parts.password:
        raise SsrfError("Credentials in the endpoint URL are not allowed.")
    host = (parts.hostname or "").lower().rstrip(".")
    if not host:
        raise SsrfError("The endpoint needs a host.")
    if host in METADATA_HOSTS:
        raise SsrfError("Metadata and control-plane hosts are blocked.")

    addresses = resolve(host, parts.port)
    if not addresses:
        raise SsrfError("The endpoint host did not resolve.")
    parsed = []
    for address in addresses:
        try:
            parsed.append(_canonical(ipaddress.ip_address(address)))
        except ValueError as exc:
            raise SsrfError("The endpoint resolved to an invalid address.") from exc
        if _blocked_metadata(parsed[-1]):
            raise SsrfError("Metadata and control-plane addresses are blocked.")

    allowed = host in policy.allowed_private_hosts or any(
        str(ip) in policy.allowed_private_hosts for ip in parsed
    )
    private = any(_non_public(ip) for ip in parsed)
    if private and not allowed:
        raise SsrfError(
            "Private and loopback addresses are allowed only for hosts named in the deployment policy."
        )
    if parts.scheme == "http" and not allowed:
        raise SsrfError("Plain HTTP is allowed only for an explicitly listed private model host.")
