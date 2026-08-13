#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_KEY="${GITHUB_RUN_ID:-local}-$$"
export COMPOSE_PROJECT_NAME="goreecloud-tasks-runtime-preflight-${RUN_KEY}"
SECRET_GID=20001
CI_GROUP_NAME="goreecloud-tasks-ci-${$}"
WORK_DIR="$(mktemp -d)"
CREATED_GROUP=false
CREATED_ENV=false
CREATED_SECRETS=false

fail() {
  printf 'runtime security preflight validation failed: %s\n' "$1" >&2
  exit 1
}

cleanup() {
  docker compose down --volumes --remove-orphans >/dev/null 2>&1 || true
  if [[ "$CREATED_ENV" == "true" ]]; then
    rm -f .env
  fi
  if [[ "$CREATED_SECRETS" == "true" ]]; then
    rm -f secrets/django_secret_key secrets/postgres_password
    rmdir secrets >/dev/null 2>&1 || true
  fi
  rm -rf "$WORK_DIR"
  if [[ "$CREATED_GROUP" == "true" ]]; then
    sudo groupdel "$CI_GROUP_NAME" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

[[ ! -e .env ]] || fail "refusing to overwrite an existing .env"
[[ ! -e secrets/django_secret_key && ! -e secrets/postgres_password ]] || fail "refusing to overwrite existing secret files"

if ! getent group "$SECRET_GID" >/dev/null; then
  sudo groupadd --gid "$SECRET_GID" "$CI_GROUP_NAME"
  CREATED_GROUP=true
fi

cp .env.example .env
cat >> .env <<'EOF'
DJANGO_DEBUG=false
APP_PORT=18086
APP_SECRET_GID=20001
EOF
chmod 600 .env
CREATED_ENV=true

mkdir -p secrets
chmod 700 secrets
printf '%s\n' 'ci-only-runtime-preflight-django-value' > secrets/django_secret_key
printf '%s\n' 'ci-only-runtime-preflight-postgres-value' > secrets/postgres_password
sudo chgrp "$SECRET_GID" secrets/django_secret_key secrets/postgres_password
chmod 640 secrets/django_secret_key secrets/postgres_password
CREATED_SECRETS=true

OWNER_UID="$(id -u)"

printf '%s\n' 'Running metadata-only host preflight against disposable CI files...'
PREFLIGHT_ENV_PATH="$ROOT_DIR/.env" \
PREFLIGHT_SECRET_DIR="$ROOT_DIR/secrets" \
PREFLIGHT_DJANGO_SECRET_PATH="$ROOT_DIR/secrets/django_secret_key" \
PREFLIGHT_POSTGRES_SECRET_PATH="$ROOT_DIR/secrets/postgres_password" \
PREFLIGHT_SECRET_OWNER_UID="$OWNER_UID" \
PREFLIGHT_SECRET_GID="$SECRET_GID" \
PREFLIGHT_APP_SECRET_GID="$SECRET_GID" \
bash scripts/check_target_runtime_preflight.sh

printf '%s\n' 'Proving the metadata checker fails closed on broad secret permissions...'
chmod 644 secrets/django_secret_key
if PREFLIGHT_ENV_PATH="$ROOT_DIR/.env" \
  PREFLIGHT_SECRET_DIR="$ROOT_DIR/secrets" \
  PREFLIGHT_DJANGO_SECRET_PATH="$ROOT_DIR/secrets/django_secret_key" \
  PREFLIGHT_POSTGRES_SECRET_PATH="$ROOT_DIR/secrets/postgres_password" \
  PREFLIGHT_SECRET_OWNER_UID="$OWNER_UID" \
  PREFLIGHT_SECRET_GID="$SECRET_GID" \
  PREFLIGHT_APP_SECRET_GID="$SECRET_GID" \
  bash scripts/check_target_runtime_preflight.sh >/dev/null 2>&1; then
  fail "metadata checker accepted a world-readable secret"
fi
chmod 640 secrets/django_secret_key

printf '%s\n' 'Proving the metadata checker fails closed on application/file GID drift...'
if PREFLIGHT_ENV_PATH="$ROOT_DIR/.env" \
  PREFLIGHT_SECRET_DIR="$ROOT_DIR/secrets" \
  PREFLIGHT_DJANGO_SECRET_PATH="$ROOT_DIR/secrets/django_secret_key" \
  PREFLIGHT_POSTGRES_SECRET_PATH="$ROOT_DIR/secrets/postgres_password" \
  PREFLIGHT_SECRET_OWNER_UID="$OWNER_UID" \
  PREFLIGHT_SECRET_GID="$SECRET_GID" \
  PREFLIGHT_APP_SECRET_GID=20002 \
  bash scripts/check_target_runtime_preflight.sh >/dev/null 2>&1; then
  fail "metadata checker accepted APP_SECRET_GID drift"
fi

printf '%s\n' 'Validating source-level container and build-context controls...'
grep -qx '.env' .dockerignore || fail ".dockerignore does not exclude .env"
grep -qx 'secrets/' .dockerignore || fail ".dockerignore does not exclude secrets/"
grep -Eq '^FROM .+@sha256:[0-9a-f]{64}$' Dockerfile || fail "Dockerfile base image is not digest-pinned"
grep -qx 'USER goreecloud' Dockerfile || fail "application image does not select the non-root goreecloud user"
grep -q 'no-new-privileges:true' compose.yml || fail "web service does not set no-new-privileges"
grep -A2 'cap_drop:' compose.yml | grep -q 'ALL' || fail "web service does not drop all Linux capabilities"
grep -q 'internal: true' compose.yml || fail "backend network is not declared internal"

printf '%s\n' 'Rendering Compose configuration without secret-value expansion...'
docker compose config > "$WORK_DIR/compose.rendered.yml"
for marker in ci-only-runtime-preflight-django-value ci-only-runtime-preflight-postgres-value; do
  if grep -Fq "$marker" "$WORK_DIR/compose.rendered.yml"; then
    fail "resolved Compose output contains a secret value"
  fi
done

printf '%s\n' 'Building the application image and starting the disposable PostgreSQL runtime...'
docker compose build web
docker compose up -d db
for _ in $(seq 1 30); do
  if docker compose exec -T db sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
docker compose exec -T db sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1 || fail "PostgreSQL did not become ready"

docker compose run --rm web python manage.py migrate --noinput
printf '%s\n' 'Starting the web container and validating live runtime controls...'
docker compose up -d web
for _ in $(seq 1 30); do
  if curl --fail --silent --show-error http://127.0.0.1:18086/health/ >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
curl --fail --silent --show-error http://127.0.0.1:18086/health/ >/dev/null || fail "web health endpoint did not become ready"

WEB_ID="$(docker compose ps -q web)"
DB_ID="$(docker compose ps -q db)"
[[ -n "$WEB_ID" && -n "$DB_ID" ]] || fail "could not resolve disposable container IDs"
docker inspect "$WEB_ID" "$DB_ID" > "$WORK_DIR/runtime.inspect.json"

python - "$WORK_DIR/runtime.inspect.json" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as handle:
    web, db = json.load(handle)

def fail(message):
    raise SystemExit(message)

if web["Config"].get("User") != "goreecloud":
    fail("web container is not configured for the goreecloud user")
if web["HostConfig"].get("Privileged"):
    fail("web container is privileged")
if db["HostConfig"].get("Privileged"):
    fail("database container is privileged")
if "no-new-privileges:true" not in (web["HostConfig"].get("SecurityOpt") or []):
    fail("web container is missing no-new-privileges")
if "ALL" not in (web["HostConfig"].get("CapDrop") or []):
    fail("web container does not drop all capabilities")
for label, container in (("web", web), ("database", db)):
    host = container["HostConfig"]
    if host.get("NetworkMode") == "host":
        fail(f"{label} container uses host networking")
    if host.get("PidMode") == "host":
        fail(f"{label} container uses the host PID namespace")
    if host.get("IpcMode") == "host":
        fail(f"{label} container uses the host IPC namespace")
    for mount in container.get("Mounts", []):
        if mount.get("Source") == "/var/run/docker.sock" or mount.get("Destination") == "/var/run/docker.sock":
            fail(f"{label} container has Docker socket access")

web_bindings = web["HostConfig"].get("PortBindings") or {}
for binding in web_bindings.get("8000/tcp") or []:
    if binding.get("HostIp") not in {"127.0.0.1", "::1"}:
        fail("development web binding is broader than loopback")
if db["HostConfig"].get("PortBindings"):
    fail("database container has a host port binding")

expected_destinations = {
    "/run/secrets/django_secret_key",
    "/run/secrets/postgres_password",
}
web_mounts = {mount.get("Destination"): mount for mount in web.get("Mounts", [])}
for destination in expected_destinations:
    mount = web_mounts.get(destination)
    if not mount:
        fail(f"web secret mount is missing: {destination}")
    if mount.get("RW"):
        fail(f"web secret mount is writable: {destination}")
PY

[[ "$(docker network inspect "${COMPOSE_PROJECT_NAME}_backend" --format '{{.Internal}}')" == "true" ]] || fail "runtime backend network is not internal"

docker compose exec -T web sh -eu -c '
  test "$(id -u)" = 10001
  id -G | tr " " "\n" | grep -qx "$1"
  for secret in /run/secrets/django_secret_key /run/secrets/postgres_password; do
    test -r "$secret"
    ! test -w "$secret"
    test "$(stat -c %a "$secret")" = 640
    test "$(stat -c %g "$secret")" = "$1"
  done
' sh "$SECRET_GID" || fail "non-root application secret-access boundary is incorrect"

for marker in ci-only-runtime-preflight-django-value ci-only-runtime-preflight-postgres-value; do
  if grep -Fq "$marker" "$WORK_DIR/runtime.inspect.json"; then
    fail "docker inspect output contains a secret value"
  fi
done

printf '%s\n' 'Runtime security preflight validation passed.'
printf '%s\n' 'Validated: metadata-only target checker, fail-closed permission/GID drift, build-context exclusion, digest-pinned base image, non-root UID 10001, supplementary secret GID, read-only 0640 secret mounts, no-new-privileges, capability drop, no privileged/host namespace/Docker-socket access, internal database networking, database host-port denial, loopback-only development web binding, migration success, and live health.'
