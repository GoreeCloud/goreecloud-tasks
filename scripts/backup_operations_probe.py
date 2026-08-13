#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def write_event(path: Path, event: str) -> None:
    record = {
        "event": event,
        "received_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def serve(args: argparse.Namespace) -> int:
    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/start":
                event = "start"
            elif self.path == "/fail":
                event = "fail"
            elif self.path == "/":
                event = "success"
            else:
                self.send_response(404)
                self.end_headers()
                return
            write_event(log_path, event)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"ok\n")

        def log_message(self, fmt: str, *values: object) -> None:
            return

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def complete_backups(repository: Path) -> list[Path]:
    return sorted(
        path
        for path in repository.iterdir()
        if path.is_dir() and not path.name.startswith(".") and (path / "manifest.json").is_file()
    )


def latest_created_epoch(repository: Path) -> float:
    backups = complete_backups(repository)
    if not backups:
        raise ValueError("no complete recovery point exists")
    manifest = json.loads((backups[-1] / "manifest.json").read_text(encoding="utf-8"))
    created_at = datetime.fromisoformat(manifest["created_at"].replace("Z", "+00:00"))
    return created_at.timestamp()


def evaluate(args: argparse.Namespace) -> int:
    repository = Path(args.repository)
    try:
        last_success = latest_created_epoch(repository)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"state": "unavailable", "detail": str(exc)}, sort_keys=True))
        return 2

    now = float(args.now_epoch if args.now_epoch is not None else time.time())
    age = max(0.0, now - last_success)
    state = "healthy" if age <= args.max_age_seconds else "late"
    print(json.dumps({
        "state": state,
        "age_seconds": int(age),
        "max_age_seconds": args.max_age_seconds,
        "recovery_points": len(complete_backups(repository)),
    }, sort_keys=True))
    return 0 if state == "healthy" else 3


def events(args: argparse.Namespace) -> int:
    path = Path(args.log)
    records = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
    print(json.dumps(records, sort_keys=True))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Disposable GoreeCloud Tasks backup operations probe")
    subparsers = parser.add_subparsers(dest="command", required=True)

    server_parser = subparsers.add_parser("serve")
    server_parser.add_argument("--host", default="127.0.0.1")
    server_parser.add_argument("--port", type=int, required=True)
    server_parser.add_argument("--log", required=True)
    server_parser.set_defaults(func=serve)

    eval_parser = subparsers.add_parser("evaluate")
    eval_parser.add_argument("--repository", required=True)
    eval_parser.add_argument("--max-age-seconds", type=int, required=True)
    eval_parser.add_argument("--now-epoch", type=float)
    eval_parser.set_defaults(func=evaluate)

    events_parser = subparsers.add_parser("events")
    events_parser.add_argument("--log", required=True)
    events_parser.set_defaults(func=events)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
