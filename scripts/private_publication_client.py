#!/usr/bin/env python3
"""Client-side assertions for disposable GoreeCloud Tasks private publication.

The client intentionally disables trust validation because the disposable Caddy route
uses Caddy's internal CA. Certificate hostname/SAN assertions are performed separately.
"""

from __future__ import annotations

import json
import socket
import ssl
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

HOST = "tasks.goreecloud.com"
BASE_URL = f"https://{HOST}"
CONTEXT = ssl._create_unverified_context()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


def request(path: str, *, headers: dict[str, str] | None = None, follow_redirects: bool = True):
    handlers: list[urllib.request.BaseHandler] = [urllib.request.HTTPSHandler(context=CONTEXT)]
    if not follow_redirects:
        handlers.append(NoRedirect())
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(BASE_URL + path, headers=headers or {})
    try:
        with opener.open(req, timeout=8) as response:
            return response.status, response.headers, response.read(), response.geturl()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers, exc.read(), exc.geturl()


def assert_approved() -> None:
    address = socket.gethostbyname(HOST)
    if not address.startswith("100."):
        raise AssertionError(f"private hostname resolved outside synthetic NetBird range: {address}")

    status, _, body, _ = request("/health/", follow_redirects=False)
    if status != 200:
        raise AssertionError(f"approved client health request returned {status}, expected 200")
    payload = json.loads(body.decode("utf-8"))
    if payload != {"status": "ok"}:
        raise AssertionError(f"unexpected health response: {payload!r}")

    status, headers, _, _ = request("/", follow_redirects=False)
    if status != 302:
        raise AssertionError(f"unauthenticated root request returned {status}, expected login redirect")
    location = headers.get("Location", "")
    if not location.startswith("/accounts/login/"):
        raise AssertionError(f"unexpected unauthenticated redirect target: {location!r}")

    status, headers, body, _ = request("/accounts/login/")
    if status != 200:
        raise AssertionError(f"login page returned {status}, expected 200")
    if b"csrfmiddlewaretoken" not in body:
        raise AssertionError("login page did not contain a CSRF token")
    cookies = headers.get_all("Set-Cookie", [])
    csrf_cookies = [value for value in cookies if "csrftoken=" in value]
    if not csrf_cookies:
        raise AssertionError("login response did not issue a CSRF cookie")
    if not all("Secure" in value for value in csrf_cookies):
        raise AssertionError("CSRF cookie was not marked Secure on the HTTPS publication path")

    print("Approved private client assertions passed.")


def assert_denied() -> None:
    status, _, body, _ = request(
        "/health/",
        headers={"X-Forwarded-For": "100.100.0.10"},
        follow_redirects=False,
    )
    if status != 403:
        raise AssertionError(
            f"unapproved client with spoofed X-Forwarded-For returned {status}, expected 403"
        )
    if body.strip() != b"Forbidden":
        raise AssertionError(f"unexpected denial body: {body!r}")
    print("Unapproved-source denial and spoof-resistance assertions passed.")


def assert_certificate() -> None:
    with socket.create_connection((HOST, 443), timeout=8) as raw:
        with CONTEXT.wrap_socket(raw, server_hostname=HOST) as tls_socket:
            certificate_der = tls_socket.getpeercert(binary_form=True)
            negotiated = tls_socket.version()

    if not negotiated or not negotiated.startswith("TLS"):
        raise AssertionError(f"unexpected TLS negotiation result: {negotiated!r}")

    certificate_pem = ssl.DER_cert_to_PEM_cert(certificate_der)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
        handle.write(certificate_pem)
        certificate_path = Path(handle.name)
    try:
        decoded = ssl._ssl._test_decode_cert(str(certificate_path))
    finally:
        certificate_path.unlink(missing_ok=True)

    sans = set(decoded.get("subjectAltName", ()))
    if ("DNS", HOST) not in sans:
        raise AssertionError(f"TLS certificate SANs do not contain {HOST!r}: {sorted(sans)!r}")

    print(f"TLS hostname assertion passed using {negotiated}.")


def assert_isolation() -> None:
    for hostname in ("goreecloud-tasks", "db"):
        try:
            addresses = socket.getaddrinfo(hostname, None)
        except socket.gaierror:
            continue
        raise AssertionError(
            f"private client unexpectedly resolved internal-only backend {hostname!r}: {addresses!r}"
        )
    print("Direct backend/database isolation assertions passed.")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: private_publication_client.py approved|denied|certificate|isolation")

    action = sys.argv[1]
    actions = {
        "approved": assert_approved,
        "denied": assert_denied,
        "certificate": assert_certificate,
        "isolation": assert_isolation,
    }
    try:
        assertion = actions[action]
    except KeyError as exc:
        raise SystemExit(f"unsupported action: {action}") from exc
    assertion()


if __name__ == "__main__":
    main()
