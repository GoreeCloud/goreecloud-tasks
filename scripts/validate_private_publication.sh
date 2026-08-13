#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

COMPOSE_FILE="scripts/private_publication.compose.yml"
CADDYFILE="scripts/private_publication.Caddyfile"
PROJECT_NAME="goreecloud-tasks-private-publication-${GITHUB_RUN_ID:-local}-$$"
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

cat > .env <<EOF
TZ=America/Chicago
DJANGO_TIME_ZONE=America/Chicago
APP_SECRET_GID=${APP_SECRET_GID}
POSTGRES_DB=goreecloud_tasks_private_publication
POSTGRES_USER=goreecloud_tasks_private_publication
EOF

printf '%s\n' "$POSTGRES_SECRET" > secrets/postgres_password
printf '%s\n' "$DJANGO_SECRET" > secrets/django_secret_key
chmod 0640 secrets/postgres_password secrets/django_secret_key

printf 'Validating source-controlled publication pattern...\n'
grep -Fq 'tasks.goreecloud.com {' "$CADDYFILE"
grep -Fq '@netbird_client remote_ip 100.64.0.0/10' "$CADDYFILE"
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

expected_networks = {
    "db": {"backend"},
    "web": {"backend", "proxy"},
    "caddy": {"proxy", "approved_ingress", "unapproved_ingress"},
    "approved-client": {"approved_ingress"},
    "unapproved-client": {"unapproved_ingress"},
}
for service_name, expected in expected_networks.items():
    networks = services[service_name].get("networks", {})
    actual = set(networks if isinstance(networks, list) else networks.keys())
    if actual != expected:
        raise SystemExit(
            f"{service_name} network scope drifted: expected {sorted(expected)!r}, got {sorted(actual)!r}"
        )

caddy_image = services["caddy"].get("image", "")
if "caddy:2.11.4@sha256:844f60b64e4724a5aa8245e019dace0d3f199f7433ce6c57676cb30a920dbad9" not in caddy_image:
    raise SystemExit(f"unexpected disposable Caddy image: {caddy_image!r}")

print("Rendered Compose topology has no host-published ports and preserves the intended network boundaries.")
PY

printf 'Building Tasks and starting disposable PostgreSQL...\n'
"${compose[@]}" build web
"${compose[@]}" up --detach --wait db
"${compose[@]}" run --rm web python manage.py migrate --noinput

printf 'Starting Tasks, Caddy, and approved/unapproved client networks...\n'
"${compose[@]}" up --detach --wait web caddy approved-client unapproved-client
"${compose[@]}" exec -T caddy caddy validate --config /etc/caddy/Caddyfile

printf 'Verifying Caddy-to-Tasks Docker-only backend reachability...\n'
"${compose[@]}" exec -T caddy \
  curl --fail --silent --show-error \
  --header 'Host: tasks.goreecloud.com' \
  --header 'X-Forwarded-Proto: https' \
  http://goreecloud-tasks:8000/health/ \
  > "$WORK_DIR/caddy-backend-health.json"
python3 - "$WORK_DIR/caddy-backend-health.json" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)
if payload != {"status": "ok"}:
    raise SystemExit(f"unexpected direct backend health payload: {payload!r}")
PY

printf 'Validating approved private HTTPS behavior...\n'
"${compose[@]}" exec -T approved-client python /client.py approved
"${compose[@]}" exec -T approved-client python /client.py certificate
"${compose[@]}" exec -T approved-client python /client.py isolation

printf 'Validating denial from outside the synthetic NetBird range...\n'
"${compose[@]}" exec -T unapproved-client python /client.py denied
"${compose[@]}" exec -T unapproved-client python /client.py isolation

printf 'Inspecting runtime publication and Docker-network boundaries...\n'
python3 - "$PROJECT_NAME" "$COMPOSE_FILE" "$ROOT_DIR/.env" <<'PY'
import ipaddress
import json
import subprocess
import sys

project, compose_file, env_file = sys.argv[1:]
base = [
    "docker", "compose", "--project-name", project,
    "--env-file", env_file, "--file", compose_file,
]

expected_networks = {
    "db": {f"{project}_backend"},
    "web": {f"{project}_backend", f"{project}_proxy"},
    "caddy": {
        f"{project}_proxy",
        f"{project}_approved_ingress",
        f"{project}_unapproved_ingress",
    },
    "approved-client": {f"{project}_approved_ingress"},
    "unapproved-client": {f"{project}_unapproved_ingress"},
}
inspections = {}
for service_name, expected in expected_networks.items():
    container_id = subprocess.check_output(base + ["ps", "-q", service_name], text=True).strip()
    if not container_id:
        raise SystemExit(f"missing running container for {service_name}")
    inspection = json.loads(
        subprocess.check_output(["docker", "inspect", container_id], text=True)
    )[0]
    inspections[service_name] = inspection

    bindings = inspection["HostConfig"].get("PortBindings")
    if bindings not in ({}, None):
        raise SystemExit(f"{service_name} unexpectedly has host port bindings: {bindings!r}")

    actual_networks = set(inspection["NetworkSettings"]["Networks"])
    if actual_networks != expected:
        raise SystemExit(
            f"{service_name} runtime networks drifted: expected {sorted(expected)!r}, got {sorted(actual_networks)!r}"
        )

approved_ip = inspections["approved-client"]["NetworkSettings"]["Networks"][f"{project}_approved_ingress"]["IPAddress"]
unapproved_ip = inspections["unapproved-client"]["NetworkSettings"]["Networks"][f"{project}_unapproved_ingress"]["IPAddress"]
netbird_range = ipaddress.ip_network("100.64.0.0/10")
if ipaddress.ip_address(approved_ip) not in netbird_range:
    raise SystemExit(f"approved client is outside synthetic NetBird range: {approved_ip}")
if ipaddress.ip_address(unapproved_ip) in netbird_range:
    raise SystemExit(f"unapproved client unexpectedly falls inside NetBird range: {unapproved_ip}")

print("Runtime network memberships, source ranges, and host-port denial match the private-publication model.")
PY

"${compose[@]}" logs --no-color > "$WORK_DIR/stack.log"
for container_id in $("${compose[@]}" ps -q); do
  docker inspect "$container_id"
done > "$WORK_DIR/inspect.json"

for artifact in "$WORK_DIR/stack.log" "$WORK_DIR/inspect.json" "$WORK_DIR/compose.json"; do
  if grep -Fq "$POSTGRES_SECRET" "$artifact"; then
    echo "Disposable PostgreSQL secret leaked into $(basename "$artifact")." >&2
    exit 1
  fi
  if grep -Fq "$DJANGO_SECRET" "$artifact"; then
    echo "Disposable Django secret leaked into $(basename "$artifact")." >&2
    exit 1
  fi
done

if grep -Eq 'DisallowedHost|Invalid HTTP_HOST|CSRF verification failed' "$WORK_DIR/stack.log"; then
  echo "Application logs contain publication-path host or CSRF errors." >&2
  exit 1
fi

printf 'Private publication validation passed.\n'
printf '%s\n' \
  'Validated: exact tasks.goreecloud.com HTTPS route, TLS hostname, synthetic NetBird-range allow, non-NetBird 403 denial, X-Forwarded-For spoof resistance, application login boundary, Secure CSRF cookie, Docker-only Caddy backend reachability, direct client/backend isolation, PostgreSQL isolation, zero host-published backend ports, exact network membership, and secret/log minimization.'
printf '%s\n' \
  'Not validated here: real AdGuard Home DNS, real NetBird policy/group state, Porkbun DNS-01 issuance, publicly trusted production certificate, real Caddy host port ownership, host firewall state, or production deployment.'
