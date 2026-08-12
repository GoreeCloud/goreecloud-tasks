#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANAGER_REPO_DIR="${MANAGER_REPO_DIR:-${ROOT_DIR}/manager-source}"
COMPOSE_FILE="${ROOT_DIR}/scripts/manager_final_topology.compose.yml"
TMP_DIR="$(mktemp -d)"
SECRET_GID="${FINAL_TOPOLOGY_SECRET_GID:-20001}"
TOKEN_FILE="${TMP_DIR}/manager-api-token"
POSTGRES_PASSWORD_FILE="${TMP_DIR}/postgres-password"
DJANGO_SECRET_FILE="${TMP_DIR}/django-secret-key"
RESOLVED_COMPOSE="${TMP_DIR}/resolved-compose.yml"
INSPECT_JSON="${TMP_DIR}/container-inspect.json"
NETWORK_JSON="${TMP_DIR}/manager-tasks-network.json"
LOG_FILE="${TMP_DIR}/stack.log"
MANAGER_WEB_USERNAME="manager-final-topology-web"
MANAGER_WEB_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"

compose() {
  docker compose --project-directory "${ROOT_DIR}" -f "${COMPOSE_FILE}" "$@"
}

cleanup() {
  status=$?
  set +e
  if [[ ${status} -ne 0 ]]; then
    echo "--- final-topology container state ---" >&2
    compose ps >&2 2>/dev/null || true
    echo "--- final-topology logs ---" >&2
    compose logs --no-color >&2 2>/dev/null || true
  fi
  compose down --volumes --remove-orphans >/dev/null 2>&1 || true
  rm -rf "${TMP_DIR}"
  exit "${status}"
}
trap cleanup EXIT INT TERM

require_path() {
  if [[ ! -e "$1" ]]; then
    echo "Required path is missing: $1" >&2
    exit 1
  fi
}

wait_healthy() {
  local container="$1"
  local label="$2"
  for _ in $(seq 1 40); do
    status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${container}" 2>/dev/null || true)"
    if [[ "${status}" == "healthy" ]]; then
      return 0
    fi
    if [[ "${status}" == "exited" || "${status}" == "dead" || "${status}" == "unhealthy" ]]; then
      echo "${label} entered unexpected state: ${status}" >&2
      return 1
    fi
    sleep 2
  done
  echo "Timed out waiting for ${label} to become healthy." >&2
  return 1
}

require_path "${MANAGER_REPO_DIR}/Dockerfile"
require_path "${MANAGER_REPO_DIR}/integrations/tasks.py"
require_path "${COMPOSE_FILE}"
require_path "${ROOT_DIR}/scripts/manager_final_topology_assertions.py"
require_path "${ROOT_DIR}/scripts/manager_cross_app_fixture.py"

umask 027
python3 -c 'import secrets; print(secrets.token_urlsafe(48))' > "${TOKEN_FILE}"
python3 -c 'import secrets; print(secrets.token_urlsafe(32))' > "${POSTGRES_PASSWORD_FILE}"
python3 -c 'import secrets; print(secrets.token_urlsafe(48))' > "${DJANGO_SECRET_FILE}"
sudo chgrp "${SECRET_GID}" "${TOKEN_FILE}" "${POSTGRES_PASSWORD_FILE}" "${DJANGO_SECRET_FILE}"
chmod 640 "${TOKEN_FILE}" "${POSTGRES_PASSWORD_FILE}" "${DJANGO_SECRET_FILE}"

export FINAL_TOPOLOGY_SECRET_GID="${SECRET_GID}"
export FINAL_TOPOLOGY_MANAGER_TOKEN_SOURCE="${TOKEN_FILE}"
export FINAL_TOPOLOGY_POSTGRES_PASSWORD_SOURCE="${POSTGRES_PASSWORD_FILE}"
export FINAL_TOPOLOGY_DJANGO_SECRET_SOURCE="${DJANGO_SECRET_FILE}"

TOKEN_VALUE="$(<"${TOKEN_FILE}")"
compose config > "${RESOLVED_COMPOSE}"
if grep -Fq "${TOKEN_VALUE}" "${RESOLVED_COMPOSE}"; then
  echo "Resolved Compose output exposed the synthetic bearer token." >&2
  exit 1
fi

compose build
compose up -d db
wait_healthy goreecloud-tasks-final-db "Tasks PostgreSQL"

compose run --rm tasks python manage.py migrate --noinput
compose run --rm tasks python scripts/manager_cross_app_fixture.py seed
compose run --rm tasks python manage.py validate_manager_integration_identity \
  --username goreecloud-manager-integration \
  --require-membership

compose up -d tasks manager
wait_healthy goreecloud-tasks-final-web "GoreeCloud Tasks"
wait_healthy goreecloud-manager-final "GoreeCloud Manager"

compose exec -T -e MANAGER_WEB_PASSWORD="${MANAGER_WEB_PASSWORD}" manager python manage.py shell <<'PY'
import os
from django.contrib.auth import get_user_model

user_model = get_user_model()
user, _ = user_model.objects.get_or_create(username="manager-final-topology-web")
user.set_password(os.environ["MANAGER_WEB_PASSWORD"])
user.is_active = True
user.save()
PY

cd "${ROOT_DIR}"
compose cp scripts/manager_final_topology_assertions.py manager:/tmp/manager_final_topology_assertions.py

docker inspect \
  goreecloud-tasks-final-db \
  goreecloud-tasks-final-web \
  goreecloud-manager-final > "${INSPECT_JSON}"

docker network inspect manager-tasks > "${NETWORK_JSON}"

python3 - "${INSPECT_JSON}" "${NETWORK_JSON}" <<'PY'
import json
import sys
from pathlib import Path

containers = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
by_name = {item["Name"].lstrip("/"): item for item in containers}
expected = {
    "goreecloud-tasks-final-db": {"goreecloud-tasks-final-backend"},
    "goreecloud-tasks-final-web": {"goreecloud-tasks-final-backend", "manager-tasks"},
    "goreecloud-manager-final": {"goreecloud-manager-final-internal", "manager-tasks"},
}
assert set(by_name) == set(expected), set(by_name)

secret_path = "/run/secrets/goreecloud_tasks_manager_api_token"
for name, networks in expected.items():
    item = by_name[name]
    actual_networks = set(item["NetworkSettings"]["Networks"])
    assert actual_networks == networks, (name, actual_networks)
    bindings = item["HostConfig"].get("PortBindings") or {}
    assert not any(value for value in bindings.values()), (name, bindings)

for name in ("goreecloud-tasks-final-web", "goreecloud-manager-final"):
    mounts = [mount for mount in by_name[name]["Mounts"] if mount["Destination"] == secret_path]
    assert len(mounts) == 1, (name, mounts)
    assert mounts[0]["RW"] is False, (name, mounts[0])

web_aliases = by_name["goreecloud-tasks-final-web"]["NetworkSettings"]["Networks"]["manager-tasks"].get("Aliases") or []
assert "goreecloud-tasks" in web_aliases, web_aliases
assert "goreecloud-tasks-final-db" not in by_name["goreecloud-manager-final"]["NetworkSettings"]["Networks"]

def env_map(item):
    result = {}
    for entry in item["Config"].get("Env") or []:
        key, _, value = entry.partition("=")
        result[key] = value
    return result

tasks_env = env_map(by_name["goreecloud-tasks-final-web"])
manager_env = env_map(by_name["goreecloud-manager-final"])
assert not tasks_env.get("TASKS_MANAGER_API_TOKEN")
assert tasks_env["TASKS_MANAGER_API_TOKEN_FILE"] == secret_path
assert not manager_env.get("TASKS_ACCESS_TOKEN")
assert manager_env["TASKS_ACCESS_TOKEN_FILE"] == secret_path
assert manager_env["TASKS_API_URL"] == "http://goreecloud-tasks:8000"

network = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))[0]
members = {entry["Name"] for entry in (network.get("Containers") or {}).values()}
assert members == {"goreecloud-tasks-final-web", "goreecloud-manager-final"}, members
assert network.get("Internal") is True

print("Container topology, network membership, alias, host-port, and secret-mount checks passed.")
PY

for service in tasks manager; do
  compose exec -T "${service}" sh -c '
    set -eu
    secret=/run/secrets/goreecloud_tasks_manager_api_token
    test -r "$secret"
    test "$(stat -c %a "$secret")" = "640"
    test "$(stat -c %g "$secret")" = "20001"
    id -G | tr " " "\n" | grep -qx "20001"
  '
done

compose exec -T manager python - <<'PY'
import socket

assert socket.gethostbyname("goreecloud-tasks")
try:
    socket.getaddrinfo("db", 5432)
except socket.gaierror:
    pass
else:
    raise SystemExit("Manager unexpectedly resolved the Tasks PostgreSQL service.")
print("Manager can resolve the approved Tasks alias and cannot resolve the Tasks database service.")
PY

compose exec -T \
  -e MANAGER_WEB_USERNAME="${MANAGER_WEB_USERNAME}" \
  -e MANAGER_WEB_PASSWORD="${MANAGER_WEB_PASSWORD}" \
  manager python /tmp/manager_final_topology_assertions.py healthy

compose exec -T tasks python scripts/manager_cross_app_fixture.py revoke
compose exec -T \
  -e MANAGER_WEB_USERNAME="${MANAGER_WEB_USERNAME}" \
  -e MANAGER_WEB_PASSWORD="${MANAGER_WEB_PASSWORD}" \
  manager python /tmp/manager_final_topology_assertions.py revoked

compose exec -T tasks python scripts/manager_cross_app_fixture.py seed
compose exec -T tasks python manage.py validate_manager_integration_identity \
  --username goreecloud-manager-integration \
  --require-membership
compose exec -T \
  -e MANAGER_WEB_USERNAME="${MANAGER_WEB_USERNAME}" \
  -e MANAGER_WEB_PASSWORD="${MANAGER_WEB_PASSWORD}" \
  manager python /tmp/manager_final_topology_assertions.py restored

compose logs --no-color > "${LOG_FILE}"
if grep -Fq "${TOKEN_VALUE}" "${LOG_FILE}"; then
  echo "Container logs exposed the synthetic bearer token." >&2
  exit 1
fi
if grep -Eiq 'Authorization:[[:space:]]*Bearer|Bearer[[:space:]]+[A-Za-z0-9_-]{20,}' "${LOG_FILE}"; then
  echo "Container logs appear to contain an Authorization bearer value." >&2
  exit 1
fi
if grep -Fq 'MANAGER-E2E-SENSITIVE-DESCRIPTION-MUST-NOT-LEAK' "${LOG_FILE}" || \
   grep -Fq 'MANAGER-E2E-SENSITIVE-COMMENT-MUST-NOT-LEAK' "${LOG_FILE}"; then
  echo "Container logs exposed deliberately sensitive synthetic task content." >&2
  exit 1
fi

echo "Disposable production-pattern GoreeCloud Tasks -> Manager topology validation passed."
