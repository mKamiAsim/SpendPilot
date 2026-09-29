# ADR 0005: SSRF policy for a later model endpoint

Date: 29 September 2026

## Decision

`app.core.ssrf.validate_endpoint` is the policy a later connection test must call before any outbound model request, and again for every redirect. This function does not open a connection.

Allowed:

- `http` and `https` only
- no username or password in the URL
- public addresses

Blocked even if present in `MODEL_ALLOWED_PRIVATE_HOSTS`:

- host names `metadata.google.internal`, `metadata.internal`, and `instance-data`
- `169.254.169.254`, `169.254.170.2`, and `fd00:ec2::254`
- link-local and unspecified addresses, including IPv4-mapped forms

Private, loopback, reserved, and multicast addresses are rejected unless the configured host, or the resolved address, is listed in `MODEL_ALLOWED_PRIVATE_HOSTS`. Plain `http` is allowed only for a host that passed that private-host exception. The allow list is not a bypass for metadata targets.

DNS resolution uses `getaddrinfo` unless the host is already an IP. A later client must not follow redirects on its own.

## Unverified

The connection test now calls this policy before every request, including redirect targets. No live model endpoint is configured in this environment. `MODEL_SMOKE_URL` is empty, so the live smoke test stays pending. The deterministic fake provider does not open a connection. See ADR 0007.
