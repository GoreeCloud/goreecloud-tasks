#!/usr/bin/env python3
import argparse
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

TASKS_URL = "https://tasks.goreecloud.com/health/"
NTFY_BASE_URL = "http://ntfy"
TOPIC = "goreecloud-uptime"
CA_FILE = "/caddy-data/caddy/pki/authorities/local/root.crt"
PUBLISHER_TOKEN_FILE = "/run/secrets/ntfy_publisher_token"
SUBSCRIBER_TOKEN_FILE = "/run/secrets/ntfy_subscriber_token"

DOWN_TITLE = "GoreeCloud Tasks DOWN"
DOWN_MESSAGE = "GoreeCloud Tasks health endpoint is unavailable. Review Uptime Kuma and protected service logs."
UP_TITLE = "GoreeCloud Tasks RECOVERED"
UP_MESSAGE = "GoreeCloud Tasks health endpoint recovered."


def read_token(path: str) -> str:
    return Path(path).read_text(encoding="utf-8").strip()


def tasks_status() -> tuple[int, dict | None]:
    context = ssl.create_default_context(cafile=CA_FILE)
    request = urllib.request.Request(TASKS_URL, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=10, context=context) as response:
            body = response.read().decode("utf-8")
            payload = json.loads(body)
            return response.status, payload
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except urllib.error.URLError:
        return 0, None


def require_up() -> None:
    status, payload = tasks_status()
    if status != 200 or payload != {"status": "ok"}:
        raise SystemExit(f"expected healthy Tasks endpoint, got status={status}, payload={payload!r}")
    print("Tasks HTTPS health probe passed with verified disposable TLS and HTTP 200.")


def require_down() -> None:
    status, _ = tasks_status()
    if status < 500:
        raise SystemExit(f"expected a server-side failure while Tasks is stopped, got status={status}")
    print(f"Tasks outage probe detected expected server-side failure status {status}.")


def ntfy_request(method: str, token: str | None, *, body: bytes | None = None, title: str | None = None):
    url = f"{NTFY_BASE_URL}/{TOPIC}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if title:
        headers["Title"] = title
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    return urllib.request.urlopen(request, timeout=10)


def publish(title: str, message: str) -> None:
    token = read_token(PUBLISHER_TOKEN_FILE)
    with ntfy_request("POST", token, body=message.encode("utf-8"), title=title) as response:
        if response.status not in (200, 201):
            raise SystemExit(f"unexpected ntfy publish status: {response.status}")
    print(f"Published sanitized transition: {title}")


def evaluate(expected: str) -> None:
    if expected == "down":
        require_down()
        publish(DOWN_TITLE, DOWN_MESSAGE)
        return
    if expected == "up":
        require_up()
        publish(UP_TITLE, UP_MESSAGE)
        return
    raise SystemExit(f"unsupported transition: {expected}")


def read_messages() -> list[dict]:
    token = read_token(SUBSCRIBER_TOKEN_FILE)
    query = urllib.parse.urlencode({"poll": "1", "since": "all"})
    request = urllib.request.Request(
        f"{NTFY_BASE_URL}/{TOPIC}/json?{query}",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        data = response.read().decode("utf-8")
    messages = []
    for line in data.splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("event") == "message":
            messages.append(event)
    return messages


def assert_empty() -> None:
    messages = read_messages()
    if messages:
        raise SystemExit(f"expected no cached alert messages, found {len(messages)}")
    print("No alert was emitted while Tasks was initially healthy.")


def assert_sequence(expected: list[str]) -> None:
    messages = read_messages()
    titles = [message.get("title") for message in messages]
    if titles != expected:
        raise SystemExit(f"unexpected alert title sequence: {titles!r}; expected {expected!r}")

    allowed_messages = {DOWN_MESSAGE, UP_MESSAGE}
    for message in messages:
        body = message.get("message", "")
        if body not in allowed_messages:
            raise SystemExit(f"unexpected alert body: {body!r}")
        serialized = json.dumps(message, sort_keys=True)
        forbidden_markers = (
            "Authorization",
            "Bearer ",
            "POSTGRES_PASSWORD",
            "DJANGO_SECRET_KEY",
            "sessionid",
            "csrftoken",
        )
        if any(marker in serialized for marker in forbidden_markers):
            raise SystemExit("notification payload contains a forbidden sensitive marker")
    print(f"Validated alert transition sequence: {titles!r}")


def expect_http_denial(callable_, description: str) -> None:
    try:
        callable_()
    except urllib.error.HTTPError as exc:
        if exc.code not in (401, 403):
            raise SystemExit(f"{description} returned unexpected status {exc.code}") from exc
        print(f"{description} correctly denied with HTTP {exc.code}.")
        return
    raise SystemExit(f"{description} unexpectedly succeeded")


def publisher_cannot_read() -> None:
    token = read_token(PUBLISHER_TOKEN_FILE)
    query = urllib.parse.urlencode({"poll": "1", "since": "all"})

    def call():
        request = urllib.request.Request(
            f"{NTFY_BASE_URL}/{TOPIC}/json?{query}",
            headers={"Authorization": f"Bearer {token}"},
            method="GET",
        )
        urllib.request.urlopen(request, timeout=10)

    expect_http_denial(call, "write-only monitor subscriber attempt")


def subscriber_cannot_publish() -> None:
    token = read_token(SUBSCRIBER_TOKEN_FILE)

    def call():
        with ntfy_request("POST", token, body=b"should-not-publish", title="denied"):
            pass

    expect_http_denial(call, "read-only subscriber publish attempt")


def anonymous_cannot_read() -> None:
    query = urllib.parse.urlencode({"poll": "1", "since": "all"})

    def call():
        request = urllib.request.Request(f"{NTFY_BASE_URL}/{TOPIC}/json?{query}", method="GET")
        urllib.request.urlopen(request, timeout=10)

    expect_http_denial(call, "anonymous alert subscription")


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("probe-up")
    subparsers.add_parser("assert-empty")
    evaluate_parser = subparsers.add_parser("evaluate")
    evaluate_parser.add_argument("state", choices=("down", "up"))
    sequence_parser = subparsers.add_parser("assert-sequence")
    sequence_parser.add_argument("states", nargs="+", choices=("down", "up"))
    subparsers.add_parser("publisher-cannot-read")
    subparsers.add_parser("subscriber-cannot-publish")
    subparsers.add_parser("anonymous-cannot-read")
    args = parser.parse_args()

    if args.command == "probe-up":
        require_up()
    elif args.command == "assert-empty":
        assert_empty()
    elif args.command == "evaluate":
        evaluate(args.state)
    elif args.command == "assert-sequence":
        mapping = {"down": DOWN_TITLE, "up": UP_TITLE}
        assert_sequence([mapping[state] for state in args.states])
    elif args.command == "publisher-cannot-read":
        publisher_cannot_read()
    elif args.command == "subscriber-cannot-publish":
        subscriber_cannot_publish()
    elif args.command == "anonymous-cannot-read":
        anonymous_cannot_read()
    else:
        raise SystemExit(f"unknown command: {args.command}")


if __name__ == "__main__":
    main()
