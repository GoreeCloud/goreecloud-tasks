#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

COMPOSE_FILE="scripts/monitoring_alert.compose.yml"
CADDYFILE="scripts/monitoring_alert.Caddyfile"
MONITOR_CONTRACT="scripts/tasks_uptime_kuma_monitor.json"
PROJECT_NAME="goreecloud-tasks-monitoring-alert-${GITHUB_RUN_ID:-local}-$$"
WORK_DIR="$(mktemp -d)"
SECRETS_DIR_PREEXISTED=false
if [[ -d secrets ]]; then
  SECRETS_DIR_PREEXISTED=true
fi

if [[ -e .env ]]; then
  echo "Refusing to run: repository .env already exists." >&2
  exit 1
fi
for path in secrets/postgres_password secrets/django_secret_key; do
  if [[ -e "$path" ]]; then
    echo "Refusing to run: protected source file already exists: $path" >&2
    exit 1
  fi
done

export MONITORING_WORK_DIR="$WORK_DIR"
compose=(docker compose --project-name "$PROJECT_NAME" --env-file "$ROOT_DIR/.env" --file "$COMPOSE_FILE")

cleanup() {
  set +e
  if [[ -f .env ]]; then
    "${compose[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true
  fi
  rm -f .env secrets/postgres_password secrets/django_secret_key
  if [[ "$SECRETS_DIR_PREEXISTED" == false ]]; then
    rmdir secrets >/dev/null 2>&1 || true
  fi
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

mkdir -p secrets
APP_SECRET_GID="$(id -g)"
POSTGRES_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
DJANGO_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"

random_token() {
  python3 - <<'PY'
import secrets
import string
alphabet = string.ascii_lowercase + string.digits
print("tk_" + "".join(secrets.choice(alphabet) for _ in range(29)))
PY
}

PUBLISHER_TOKEN="$(random_token)"
SUBSCRIBER_TOKEN="$(random_token)"

cat > .env <<EOF_ENV
TZ=America/Chicago
DJANGO_TIME_ZONE=America/Chicago
APP_SECRET_GID=${APP_SECRET_GID}
POSTGRES_DB=goreecloud_tasks_monitoring_alert
POSTGRES_USER=goreecloud_tasks_monitoring_alert
EOF_ENV

printf '%s\n' "$POSTGRES_SECRET" > secrets/postgres_password
printf '%s\n' "$DJANGO_SECRET" > secrets/django_secret_key
printf '%s\n' "$PUBLISHER_TOKEN" > "$WORK_DIR/ntfy-publisher-token"
printf '%s\n' "$SUBSCRIBER_TOKEN" > "$WORK_DIR/ntfy-subscriber-token"
chmod 0640 secrets/postgres_password secrets/django_secret_key
chmod 0444 "$WORK_DIR/ntfy-publisher-token" "$WORK_DIR/ntfy-subscriber-token"

TEST_PASSWORD_HASH='$2a$10$YLiO8U21sX1uhZamTLJXHuxgVC0Z/GKISibrKCLohPgtG7yIxSk4C'
cat > "$WORK_DIR/ntfy-server.yml" <<EOF_NTFY
listen-http: ":80"
cache-file: "/var/lib/ntfy/cache.db"
cache-duration: "1h"
auth-file: "/var/lib/ntfy/auth.db"
auth-default-access: "deny-all"
enable-login: true
require-login: true
enable-signup: false
auth-users:
  - "uptime-kuma-ci:${TEST_PASSWORD_HASH}:user"
  - "uptime-subscriber-ci:${TEST_PASSWORD_HASH}:user"
auth-access:
  - "uptime-kuma-ci:goreecloud-uptime:write-only"
  - "uptime-subscriber-ci:goreecloud-uptime:read-only"
auth-tokens:
  - "uptime-kuma-ci:${PUBLISHER_TOKEN}:Disposable Uptime Kuma publisher"
  - "uptime-subscriber-ci:${SUBSCRIBER_TOKEN}:Disposable Uptime subscriber"
EOF_NTFY
chmod 0444 "$WORK_DIR/ntfy-server.yml"

printf 'Validating source-controlled monitoring contract...\n'
python3 - "$MONITOR_CONTRACT" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    contract = json.load(handle)

if contract.get("state") != "proposed-not-provisioned":
    raise SystemExit("monitor contract must not claim production provisioning")
monitor = contract["monitor"]
if monitor.get("name") != "GoreeCloud Tasks":
    raise SystemExit("unexpected monitor name")
if monitor.get("url") != "https://tasks.goreecloud.com/health/":
    raise SystemExit("monitor must target the private HTTPS health endpoint")
if monitor.get("interval_seconds") != 60:
    raise SystemExit("monitor interval must match the approved 60-second Uptime Kuma pattern")
if monitor.get("accepted_status_codes") != [200]:
    raise SystemExit("monitor must require HTTP 200")
if monitor.get("tls_verification_required") is not True:
    raise SystemExit("TLS verification must remain required")
source = contract["source_identity"]
if source.get("container") != "uptime-kuma" or source.get("ipv4") != "172.19.0.50":
    raise SystemExit("monitor source identity drifted from the documented Uptime Kuma proxy identity")
notification = contract["notification"]
if notification.get("service_identity") != "uptime-kuma":
    raise SystemExit("notification publisher identity drifted")
if notification.get("permission") != "write-only":
    raise SystemExit("Uptime Kuma publisher must remain write-only")
if notification.get("internal_server_url") != "http://ntfy:80":
    raise SystemExit("Uptime Kuma must use the approved internal ntfy endpoint")
if notification.get("topic") != "goreecloud-uptime":
    raise SystemExit("unexpected Uptime Kuma topic")
if contract["limitations"].get("production_monitor_registered") is not False:
    raise SystemExit("contract must not claim a real monitor exists")
print("Monitoring contract preserves the approved endpoint, source identity, and least-privilege notification boundary.")
PY

grep -Fq 'tasks.goreecloud.com {' "$CADDYFILE"
grep -Fq '@approved_client remote_ip 100.64.0.0/10 172.19.0.50' "$CADDYFILE"
grep -Fq 'reverse_proxy goreecloud-tasks:8000' "$CADDYFILE"
grep -Fq 'respond "Forbidden" 403' "$CADDYFILE"
grep -Fq 'tls internal' "$CADDYFILE"

"${compose[@]}" config --format json > "$WORK_DIR/compose.json"
python3 - "$WORK_DIR/compose.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    config = json.load(handle)
services = config["services"]

for name, service in services.items():
    if service.get("ports"):
        raise SystemExit(f"{name} unexpectedly publishes a host port: {service['ports']!r}")

expected = {
    "db": {"backend"},
    "web": {"backend", "proxy"},
    "caddy": {"proxy"},
    "ntfy": {"proxy"},
    "monitor": {"proxy"},
    "subscriber": {"proxy"},
}
for service_name, wanted in expected.items():
    networks = services[service_name].get("networks", {})
    actual = set(networks if isinstance(networks, list) else networks.keys())
    if actual != wanted:
        raise SystemExit(f"{service_name} network scope drifted: expected {sorted(wanted)!r}, got {sorted(actual)!r}")

monitor_ip = services["monitor"]["networks"]["proxy"].get("ipv4_address")
if monitor_ip != "172.19.0.50":
    raise SystemExit(f"unexpected disposable Uptime Kuma source identity: {monitor_ip!r}")
print("Rendered monitoring topology has no host-published ports and preserves the intended service/network scope.")
PY

printf 'Building Tasks and starting disposable PostgreSQL...\n'
"${compose[@]}" build web
"${compose[@]}" up --detach --wait db
"${compose[@]}" run --rm web python manage.py migrate --noinput

printf 'Starting Tasks, Caddy, ntfy, and isolated monitoring clients...\n'
"${compose[@]}" up --detach --wait web caddy
"${compose[@]}" up --detach ntfy monitor subscriber
"${compose[@]}" exec -T caddy caddy validate --config /etc/caddy/Caddyfile

for attempt in $(seq 1 30); do
  if "${compose[@]}" exec -T monitor python - <<'PY' >/dev/null 2>&1
import urllib.request
urllib.request.urlopen("http://ntfy/v1/health", timeout=3)
PY
  then
    break
  fi
  if [[ "$attempt" -eq 30 ]]; then
    "${compose[@]}" logs --no-color ntfy || true
    echo "Disposable ntfy did not become healthy." >&2
    exit 1
  fi
  sleep 1
done

printf 'Verifying healthy HTTPS monitoring path and no false-positive alert...\n'
"${compose[@]}" exec -T monitor python /client.py probe-up
"${compose[@]}" exec -T subscriber python /client.py assert-empty

printf 'Verifying least-privilege ntfy alert permissions...\n'
"${compose[@]}" exec -T monitor python /client.py publisher-cannot-read
"${compose[@]}" exec -T subscriber python /client.py subscriber-cannot-publish
"${compose[@]}" exec -T subscriber python /client.py anonymous-cannot-read

printf 'Simulating a Tasks outage and requiring a DOWN alert...\n'
"${compose[@]}" stop web
"${compose[@]}" exec -T monitor python /client.py evaluate down
"${compose[@]}" exec -T subscriber python /client.py assert-sequence down

printf 'Restoring Tasks and requiring a recovery alert...\n'
"${compose[@]}" up --detach --wait web
"${compose[@]}" exec -T monitor python /client.py evaluate up
"${compose[@]}" exec -T subscriber python /client.py assert-sequence down up

printf 'Inspecting runtime source identity and exposure boundaries...\n'
python3 - "$PROJECT_NAME" "$COMPOSE_FILE" "$ROOT_DIR/.env" <<'PY'
import json
import subprocess
import sys

project, compose_file, env_file = sys.argv[1:]
base = ["docker", "compose", "--project-name", project, "--env-file", env_file, "--file", compose_file]
expected_networks = {
    "db": {f"{project}_backend"},
    "web": {f"{project}_backend", f"{project}_proxy"},
    "caddy": {f"{project}_proxy"},
    "ntfy": {f"{project}_proxy"},
    "monitor": {f"{project}_proxy"},
    "subscriber": {f"{project}_proxy"},
}
inspections = {}
for service_name, wanted in expected_networks.items():
    container_id = subprocess.check_output(base + ["ps", "-q", service_name], text=True).strip()
    if not container_id:
        raise SystemExit(f"missing running container for {service_name}")
    inspection = json.loads(subprocess.check_output(["docker", "inspect", container_id], text=True))[0]
    inspections[service_name] = inspection
    bindings = inspection["HostConfig"].get("PortBindings")
    if bindings not in ({}, None):
        raise SystemExit(f"{service_name} unexpectedly has host port bindings: {bindings!r}")
    actual_networks = set(inspection["NetworkSettings"]["Networks"])
    if actual_networks != wanted:
        raise SystemExit(f"{service_name} runtime networks drifted: expected {sorted(wanted)!r}, got {sorted(actual_networks)!r}")

monitor_ip = inspections["monitor"]["NetworkSettings"]["Networks"][f"{project}_proxy"]["IPAddress"]
if monitor_ip != "172.19.0.50":
    raise SystemExit(f"runtime monitor identity drifted: {monitor_ip!r}")
print("Runtime source identity, network membership, and zero-host-port boundaries are correct.")
PY

"${compose[@]}" logs --no-color > "$WORK_DIR/stack.log"
for container_id in $("${compose[@]}" ps -q); do
  docker inspect "$container_id"
done > "$WORK_DIR/inspect.json"

for artifact in "$WORK_DIR/stack.log" "$WORK_DIR/inspect.json" "$WORK_DIR/compose.json"; do
  for secret in "$POSTGRES_SECRET" "$DJANGO_SECRET" "$PUBLISHER_TOKEN" "$SUBSCRIBER_TOKEN"; do
    if grep -Fq "$secret" "$artifact"; then
      echo "Disposable secret leaked into $(basename "$artifact")." >&2
      exit 1
    fi
  done
done

if grep -Eq 'DisallowedHost|Invalid HTTP_HOST|CSRF verification failed' "$WORK_DIR/stack.log"; then
  echo "Application logs contain monitoring-path host or CSRF errors." >&2
  exit 1
fi

printf 'Monitoring and alert-delivery readiness validation passed.\n'
printf '%s\n' \
  'Validated: proposed Uptime Kuma monitor contract, exact private HTTPS /health/ path, documented 172.19.0.50 monitoring source identity, Caddy allowlist behavior, real disposable ntfy write-only publisher/read-only subscriber ACLs, healthy no-alert behavior, detected outage -> DOWN notification, recovery -> RECOVERED notification, no host-published service ports, runtime network scope, and secret/log minimization.'
printf '%s\n' \
  'Not validated here: creation of a real Uptime Kuma monitor, live production Caddy allowlist change, actual target-host source IP observation, real Vaultwarden token installation, real administrative subscriber receipt, independent out-of-band alerting, or production deployment.'
