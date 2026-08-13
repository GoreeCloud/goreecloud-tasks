#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

COMPOSE_FILE="scripts/full_environment_recovery.compose.yml"
CONTRACT_FILE="scripts/tasks_full_environment_recovery_contract.json"
PROJECT_NAME="goreecloud-tasks-full-recovery-${GITHUB_RUN_ID:-local}-$$"
WORK_DIR="$(mktemp -d)"
RECOVERY_BUNDLE="$WORK_DIR/recovery-bundle"
RECOVERY_REPOSITORY="$RECOVERY_BUNDLE/postgresql"
HEARTBEAT_LOG="$WORK_DIR/backup-heartbeats.jsonl"
HEARTBEAT_PID=""
SECRETS_DIR_PREEXISTED=false
if [[ -d secrets ]]; then
  SECRETS_DIR_PREEXISTED=true
fi

fail() {
  printf 'full-environment recovery readiness failed: %s\n' "$1" >&2
  exit 1
}

if [[ -e .env ]]; then
  fail "repository .env already exists"
fi
for path in secrets/postgres_password secrets/django_secret_key; do
  if [[ -e "$path" ]]; then
    fail "protected source file already exists: $path"
  fi
done

compose=(docker compose --env-file "$ROOT_DIR/.env" --file "$COMPOSE_FILE")

cleanup() {
  set +e
  if [[ -n "$HEARTBEAT_PID" ]]; then
    kill "$HEARTBEAT_PID" >/dev/null 2>&1 || true
    wait "$HEARTBEAT_PID" >/dev/null 2>&1 || true
  fi
  if [[ -f .env ]]; then
    "${compose[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true
  else
    RECOVERY_PROJECT_NAME="$PROJECT_NAME" docker compose --file "$COMPOSE_FILE" down --volumes --remove-orphans >/dev/null 2>&1 || true
  fi
  rm -f .env secrets/postgres_password secrets/django_secret_key
  if [[ "$SECRETS_DIR_PREEXISTED" == false ]]; then
    rmdir secrets >/dev/null 2>&1 || true
  fi
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

mkdir -p "$RECOVERY_BUNDLE/secrets" "$RECOVERY_REPOSITORY" secrets
chmod 700 "$RECOVERY_BUNDLE" "$RECOVERY_BUNDLE/secrets" "$RECOVERY_REPOSITORY"
APP_SECRET_GID="$(id -g)"
POSTGRES_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
DJANGO_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"

cat > "$RECOVERY_BUNDLE/tasks.env" <<EOF
RECOVERY_PROJECT_NAME=${PROJECT_NAME}
TZ=America/Chicago
DJANGO_TIME_ZONE=America/Chicago
APP_SECRET_GID=${APP_SECRET_GID}
POSTGRES_DB=goreecloud_tasks_full_recovery
POSTGRES_USER=goreecloud_tasks_full_recovery
EOF
printf '%s\n' "$POSTGRES_SECRET" > "$RECOVERY_BUNDLE/secrets/postgres_password"
printf '%s\n' "$DJANGO_SECRET" > "$RECOVERY_BUNDLE/secrets/django_secret_key"
chmod 600 "$RECOVERY_BUNDLE/tasks.env" "$RECOVERY_BUNDLE/secrets/postgres_password" "$RECOVERY_BUNDLE/secrets/django_secret_key"

restore_working_configuration() {
  cp "$RECOVERY_BUNDLE/tasks.env" .env
  cp "$RECOVERY_BUNDLE/secrets/postgres_password" secrets/postgres_password
  cp "$RECOVERY_BUNDLE/secrets/django_secret_key" secrets/django_secret_key
  chmod 0600 .env
  chmod 0640 secrets/postgres_password secrets/django_secret_key
}

restore_working_configuration
set -a
# shellcheck disable=SC1091
source .env
set +a

printf 'Validating recovery contract and source-controlled topology...\n'
python3 -m json.tool "$CONTRACT_FILE" >/dev/null
python3 - "$CONTRACT_FILE" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    contract = json.load(handle)

required = {
    "source-available",
    "recovery-documentation-available",
    "configuration-recreated",
    "secrets-recreated",
    "clean-database-created",
    "database-restored",
    "application-semantics-validated",
    "private-publication-restored",
    "authentication-boundary-validated",
    "monitoring-health-restored",
    "backup-protection-resumed",
    "temporary-recovery-resources-cleaned",
}
stages = contract.get("required_stages", [])
if len(stages) != len(set(stages)):
    raise SystemExit("recovery contract contains duplicate required stages")
if set(stages) != required:
    raise SystemExit(f"recovery contract stage drift: {stages!r}")

unproven = set(contract.get("target_environment_evidence_not_proven_here", []))
for item in (
    "proxmox-vm-restore",
    "production-kopia-repository",
    "production-recovery-credentials",
    "production-adguard-home-private-dns",
    "production-netbird-policy",
    "production-caddy-host-listeners",
    "production-uptime-kuma-registration-and-notification-receipt",
    "independent-off-host-or-off-site-recovery-copy",
):
    if item not in unproven:
        raise SystemExit(f"target-environment limitation missing from recovery contract: {item}")

print("Recovery contract preserves all required stages and target-environment limitations.")
PY

"${compose[@]}" config --format json > "$WORK_DIR/compose.json"
python3 - "$WORK_DIR/compose.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    config = json.load(handle)

services = config["services"]
expected_networks = {
    "db": {"backend"},
    "web": {"backend", "proxy"},
    "caddy": {"proxy", "approved_ingress"},
    "approved-client": {"approved_ingress"},
}
if set(services) != set(expected_networks):
    raise SystemExit(f"unexpected recovery services: {sorted(services)!r}")
for name, expected in expected_networks.items():
    service = services[name]
    if service.get("ports"):
        raise SystemExit(f"{name} unexpectedly publishes host ports: {service['ports']!r}")
    networks = service.get("networks", {})
    actual = set(networks if isinstance(networks, list) else networks.keys())
    if actual != expected:
        raise SystemExit(f"{name} recovery network drift: expected {sorted(expected)!r}, got {sorted(actual)!r}")

web = services["web"]
if "no-new-privileges:true" not in web.get("security_opt", []):
    raise SystemExit("recovered web service lost no-new-privileges")
if set(web.get("cap_drop", [])) != {"ALL"}:
    raise SystemExit("recovered web service must drop all capabilities")

print("Recovery topology has no host-published ports and preserves required network/security boundaries.")
PY

printf 'Starting disposable backup heartbeat receiver...\n'
HEARTBEAT_PORT="$(python3 - <<'PY'
import socket
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
)"
python3 scripts/backup_operations_probe.py serve \
  --host 127.0.0.1 \
  --port "$HEARTBEAT_PORT" \
  --log "$HEARTBEAT_LOG" &
HEARTBEAT_PID=$!
python3 - "$HEARTBEAT_PORT" <<'PY'
import socket
import sys
import time

port = int(sys.argv[1])
for _ in range(50):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
            break
    except OSError:
        time.sleep(0.1)
else:
    raise SystemExit("backup heartbeat receiver did not become ready")
PY

printf 'Building candidate source and creating the pre-loss primary environment...\n'
"${compose[@]}" build web
"${compose[@]}" up --detach --wait db
"${compose[@]}" run --rm web python manage.py migrate --noinput
"${compose[@]}" run --rm web python scripts/backup_restore_fixture.py seed
"${compose[@]}" run --rm web python scripts/backup_restore_fixture.py snapshot > "$WORK_DIR/pre-loss-state.json"
"${compose[@]}" run --rm web python scripts/backup_restore_fixture.py assert

printf 'Creating a verified recovery point outside disposable primary volumes...\n'
BACKUP_REPOSITORY="$RECOVERY_REPOSITORY" \
BACKUP_RETENTION_COUNT=3 \
BACKUP_HEARTBEAT_URL="http://127.0.0.1:${HEARTBEAT_PORT}" \
BACKUP_COMPOSE_FILE="$COMPOSE_FILE" \
BACKUP_DATABASE="$POSTGRES_DB" \
  bash scripts/tasks_backup_job.sh

mapfile -t INITIAL_BACKUPS < <(find "$RECOVERY_REPOSITORY" -mindepth 1 -maxdepth 1 -type d ! -name '.*.partial' -printf '%f\n' | sort)
if (( ${#INITIAL_BACKUPS[@]} != 1 )); then
  fail "expected exactly one pre-loss recovery point, found ${#INITIAL_BACKUPS[@]}"
fi
INITIAL_BACKUP_ID="${INITIAL_BACKUPS[0]}"
INITIAL_BACKUP_DIR="$RECOVERY_REPOSITORY/$INITIAL_BACKUP_ID"
(
  cd "$INITIAL_BACKUP_DIR"
  sha256sum --check SHA256SUMS
)
"${compose[@]}" exec -T db pg_restore --list < "$INITIAL_BACKUP_DIR/tasks-postgresql.dump" >/dev/null

python3 - "$RECOVERY_BUNDLE/recovery-evidence.json" "$INITIAL_BACKUP_ID" "${GITHUB_SHA:-local}" <<'PY'
import json
import sys

path, backup_id, source_revision = sys.argv[1:]
record = {
    "schema": 1,
    "source_revision": source_revision,
    "database_recovery_point": backup_id,
    "configuration_source": "synthetic-independent-recovery-bundle",
    "secret_values_recorded": False,
    "production_activation_authorized": False,
}
with open(path, "w", encoding="utf-8") as handle:
    json.dump(record, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
chmod 600 "$RECOVERY_BUNDLE/recovery-evidence.json"

printf 'Simulating total disposable primary-environment loss...\n'
"${compose[@]}" down --volumes --remove-orphans
rm -f .env secrets/postgres_password secrets/django_secret_key
if [[ -e .env || -e secrets/postgres_password || -e secrets/django_secret_key ]]; then
  fail "working configuration survived simulated loss unexpectedly"
fi

printf 'Reconstructing configuration and secrets from the separate synthetic recovery bundle...\n'
restore_working_configuration
set -a
# shellcheck disable=SC1091
source .env
set +a

printf 'Creating a new empty PostgreSQL environment and proving the restore target is clean...\n'
"${compose[@]}" up --detach --wait db
TABLE_COUNT="$("${compose[@]}" exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT count(*) FROM pg_tables WHERE schemaname = 'public';")"
if [[ "$TABLE_COUNT" != "0" ]]; then
  fail "new recovery database was not empty before restoration: public table count=$TABLE_COUNT"
fi

printf 'Restoring the verified PostgreSQL recovery point into the clean environment...\n'
"${compose[@]}" exec -T db pg_restore \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --no-owner \
  --no-acl \
  --exit-on-error \
  < "$INITIAL_BACKUP_DIR/tasks-postgresql.dump"

printf 'Validating restored application state and semantics...\n'
"${compose[@]}" run --rm web python manage.py check
"${compose[@]}" run --rm web python manage.py migrate --check
"${compose[@]}" run --rm web python scripts/backup_restore_fixture.py snapshot > "$WORK_DIR/post-restore-state.json"
cmp "$WORK_DIR/pre-loss-state.json" "$WORK_DIR/post-restore-state.json"
"${compose[@]}" run --rm web python scripts/backup_restore_fixture.py assert

printf 'Restoring private publication and validating the recovered HTTPS/authentication boundary...\n'
"${compose[@]}" up --detach --wait web caddy approved-client
"${compose[@]}" exec -T caddy caddy validate --config /etc/caddy/Caddyfile
"${compose[@]}" exec -T approved-client python /client.py approved
"${compose[@]}" exec -T approved-client python /client.py certificate
"${compose[@]}" exec -T approved-client python /client.py isolation

printf 'Validating post-recovery health as the monitoring restoration checkpoint...\n'
"${compose[@]}" exec -T approved-client python /client.py approved > "$WORK_DIR/post-recovery-health.txt"
grep -Fq 'Approved private client assertions passed.' "$WORK_DIR/post-recovery-health.txt"

printf 'Proving backup protection can resume after the recovered service is operational...\n'
BACKUP_REPOSITORY="$RECOVERY_REPOSITORY" \
BACKUP_RETENTION_COUNT=3 \
BACKUP_HEARTBEAT_URL="http://127.0.0.1:${HEARTBEAT_PORT}" \
BACKUP_COMPOSE_FILE="$COMPOSE_FILE" \
BACKUP_DATABASE="$POSTGRES_DB" \
  bash scripts/tasks_backup_job.sh

mapfile -t FINAL_BACKUPS < <(find "$RECOVERY_REPOSITORY" -mindepth 1 -maxdepth 1 -type d ! -name '.*.partial' -printf '%f\n' | sort)
if (( ${#FINAL_BACKUPS[@]} != 2 )); then
  fail "expected original plus post-recovery recovery point, found ${#FINAL_BACKUPS[@]}"
fi
POST_RECOVERY_BACKUP_ID="${FINAL_BACKUPS[1]}"
if [[ "$POST_RECOVERY_BACKUP_ID" == "$INITIAL_BACKUP_ID" ]]; then
  fail "backup protection did not create a distinct post-recovery recovery point"
fi
POST_RECOVERY_BACKUP_DIR="$RECOVERY_REPOSITORY/$POST_RECOVERY_BACKUP_ID"
(
  cd "$POST_RECOVERY_BACKUP_DIR"
  sha256sum --check SHA256SUMS
)
"${compose[@]}" exec -T db pg_restore --list < "$POST_RECOVERY_BACKUP_DIR/tasks-postgresql.dump" >/dev/null
python3 scripts/backup_operations_probe.py evaluate \
  --repository "$RECOVERY_REPOSITORY" \
  --max-age-seconds 300 \
  > "$WORK_DIR/post-recovery-backup-state.json"
python3 - "$WORK_DIR/post-recovery-backup-state.json" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as handle:
    state = json.load(handle)
if state.get("state") != "healthy":
    raise SystemExit(f"post-recovery backup state is not healthy: {state!r}")
if state.get("recovery_points") != 2:
    raise SystemExit(f"unexpected post-recovery recovery-point count: {state!r}")
PY

printf 'Validating expected backup monitoring transitions...\n'
python3 scripts/backup_operations_probe.py events --log "$HEARTBEAT_LOG" > "$WORK_DIR/heartbeat-events.json"
python3 - "$WORK_DIR/heartbeat-events.json" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as handle:
    records = json.load(handle)
sequence = [record.get("event") for record in records]
if sequence != ["start", "success", "start", "success"]:
    raise SystemExit(f"unexpected recovery backup heartbeat sequence: {sequence!r}")
print("Pre-loss and post-recovery backup monitoring transitions are correct.")
PY

printf 'Inspecting recovered runtime boundaries and secret minimization...\n'
"${compose[@]}" logs --no-color > "$WORK_DIR/recovered-stack.log"
for service in db web caddy approved-client; do
  container_id="$("${compose[@]}" ps -q "$service")"
  [[ -n "$container_id" ]] || fail "missing recovered runtime container: $service"
  docker inspect "$container_id"
done > "$WORK_DIR/recovered-inspect.json"

python3 - "$WORK_DIR/recovered-inspect.json" "$PROJECT_NAME" <<'PY'
import json
import sys

path, project = sys.argv[1:]
with open(path, encoding="utf-8") as handle:
    inspections = []
    decoder = json.JSONDecoder()
    payload = handle.read()
    index = 0
    while index < len(payload):
        while index < len(payload) and payload[index].isspace():
            index += 1
        if index >= len(payload):
            break
        value, end = decoder.raw_decode(payload, index)
        inspections.extend(value)
        index = end

expected = {
    "db": {f"{project}_backend"},
    "web": {f"{project}_backend", f"{project}_proxy"},
    "caddy": {f"{project}_proxy", f"{project}_approved_ingress"},
    "approved-client": {f"{project}_approved_ingress"},
}
by_service = {}
for inspection in inspections:
    labels = inspection.get("Config", {}).get("Labels", {})
    service = labels.get("com.docker.compose.service")
    if service:
        by_service[service] = inspection

for service, expected_networks in expected.items():
    inspection = by_service.get(service)
    if inspection is None:
        raise SystemExit(f"missing runtime inspection for {service}")
    bindings = inspection.get("HostConfig", {}).get("PortBindings")
    if bindings not in ({}, None):
        raise SystemExit(f"{service} unexpectedly has host port bindings: {bindings!r}")
    actual = set(inspection["NetworkSettings"]["Networks"])
    if actual != expected_networks:
        raise SystemExit(f"{service} runtime network drift: expected {sorted(expected_networks)!r}, got {sorted(actual)!r}")

print("Recovered runtime has exact intended networks and no host-published service ports.")
PY

for artifact in \
  "$WORK_DIR/recovered-stack.log" \
  "$WORK_DIR/recovered-inspect.json" \
  "$WORK_DIR/compose.json" \
  "$WORK_DIR/heartbeat-events.json" \
  "$RECOVERY_BUNDLE/recovery-evidence.json"; do
  if grep -Fq "$POSTGRES_SECRET" "$artifact"; then
    fail "synthetic PostgreSQL secret leaked into $(basename "$artifact")"
  fi
  if grep -Fq "$DJANGO_SECRET" "$artifact"; then
    fail "synthetic Django secret leaked into $(basename "$artifact")"
  fi
done

if find "$RECOVERY_REPOSITORY" -type d -name '.*.partial' -print -quit | grep -q .; then
  fail "partial backup artifacts remained after recovery validation"
fi

printf 'Full-environment recovery readiness validation passed.\n'
printf '%s\n' \
  'Validated: independent synthetic recovery bundle availability, verified PostgreSQL recovery point, destructive loss of disposable primary volumes/configuration, clean database reconstruction, PostgreSQL restoration, exact Tasks state and authorization semantics, private HTTPS publication, TLS hostname, application login boundary, post-recovery health, resumed backup creation/monitoring/integrity, runtime isolation, and cleanup behavior.'
printf '%s\n' \
  'Not validated here: actual Proxmox VM recovery, dedicated backup server, production Kopia repository, real recovery credentials, AdGuard Home DNS, NetBird policy, Porkbun DNS-01/public TLS, host Caddy/firewall state, production Uptime Kuma notification receipt, production Manager/ntfy identities, off-host/off-site copy, or production deployment.'
