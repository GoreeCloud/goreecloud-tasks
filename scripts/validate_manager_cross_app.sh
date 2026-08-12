#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANAGER_REPO_DIR="${MANAGER_REPO_DIR:-${ROOT_DIR}/manager-source}"
TASKS_PYTHON="${TASKS_PYTHON:-${ROOT_DIR}/.venv-tasks/bin/python}"
MANAGER_PYTHON="${MANAGER_PYTHON:-${ROOT_DIR}/.venv-manager/bin/python}"
TASKS_PORT="${TASKS_PORT:-18000}"
MANAGER_PORT="${MANAGER_PORT:-18090}"
TMP_DIR="$(mktemp -d)"
TASKS_LOG="${TMP_DIR}/tasks.log"
MANAGER_LOG="${TMP_DIR}/manager.log"
TASKS_PID=""
MANAGER_PID=""

MANAGER_API_TOKEN="manager-e2e-ci-token-0123456789abcdef0123456789abcdef"
MANAGER_WEB_USERNAME="manager-e2e-web"
MANAGER_WEB_PASSWORD="manager-e2e-web-password"

cleanup() {
  status=$?
  set +e

  if [[ -n "${MANAGER_PID}" ]]; then
    kill "${MANAGER_PID}" 2>/dev/null || true
    wait "${MANAGER_PID}" 2>/dev/null || true
  fi
  if [[ -n "${TASKS_PID}" ]]; then
    kill "${TASKS_PID}" 2>/dev/null || true
    wait "${TASKS_PID}" 2>/dev/null || true
  fi

  if [[ ${status} -ne 0 ]]; then
    echo "--- GoreeCloud Tasks server log ---" >&2
    cat "${TASKS_LOG}" >&2 2>/dev/null || true
    echo "--- GoreeCloud Manager server log ---" >&2
    cat "${MANAGER_LOG}" >&2 2>/dev/null || true
  fi

  rm -f "${ROOT_DIR}/db.sqlite3"
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

wait_for_url() {
  local url="$1"
  local label="$2"
  for _ in $(seq 1 30); do
    if curl --fail --silent --show-error "${url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo "Timed out waiting for ${label}: ${url}" >&2
  return 1
}

require_path "${MANAGER_REPO_DIR}/manage.py"
require_path "${MANAGER_REPO_DIR}/integrations/tasks.py"
require_path "${TASKS_PYTHON}"
require_path "${MANAGER_PYTHON}"

rm -f "${ROOT_DIR}/db.sqlite3"

export DJANGO_SECRET_KEY="manager-e2e-tasks-django-secret-not-for-production"
export DJANGO_DEBUG="true"
export DJANGO_ALLOWED_HOSTS="127.0.0.1,localhost"
export DJANGO_SECURE_COOKIES="false"
export DATABASE_ENGINE="sqlite"
export TASKS_MANAGER_API_ENABLED="true"
export TASKS_MANAGER_API_USERNAME="goreecloud-manager-integration"
export TASKS_MANAGER_API_TOKEN="${MANAGER_API_TOKEN}"
export TASKS_MANAGER_API_TOKEN_FILE=""
export TASKS_MANAGER_API_MAX_TASKS="100"

cd "${ROOT_DIR}"
"${TASKS_PYTHON}" manage.py migrate --noinput
"${TASKS_PYTHON}" scripts/manager_cross_app_fixture.py seed
"${TASKS_PYTHON}" manage.py validate_manager_integration_identity \
  --username goreecloud-manager-integration \
  --require-membership
"${TASKS_PYTHON}" manage.py runserver "127.0.0.1:${TASKS_PORT}" --noreload >"${TASKS_LOG}" 2>&1 &
TASKS_PID=$!
wait_for_url "http://127.0.0.1:${TASKS_PORT}/health/" "GoreeCloud Tasks"

export DJANGO_SECRET_KEY="manager-e2e-manager-django-secret-not-for-production"
export DJANGO_DEBUG="true"
export DJANGO_ALLOWED_HOSTS="127.0.0.1,localhost"
export DJANGO_DB_PATH="${TMP_DIR}/manager.sqlite3"
export TASKS_ENABLED="true"
export TASKS_API_URL="http://127.0.0.1:${TASKS_PORT}"
export TASKS_ACCESS_TOKEN="${MANAGER_API_TOKEN}"
export TASKS_ACCESS_TOKEN_FILE=""
export TASKS_TIMEOUT_SECONDS="5"
export MANAGER_BASE_URL="http://127.0.0.1:${MANAGER_PORT}"
export MANAGER_WEB_USERNAME
export MANAGER_WEB_PASSWORD

cd "${MANAGER_REPO_DIR}"
"${MANAGER_PYTHON}" manage.py migrate --noinput
"${MANAGER_PYTHON}" manage.py shell -c \
  "from django.contrib.auth import get_user_model; u,_=get_user_model().objects.get_or_create(username='${MANAGER_WEB_USERNAME}'); u.set_password('${MANAGER_WEB_PASSWORD}'); u.is_active=True; u.save()"
"${MANAGER_PYTHON}" manage.py runserver "127.0.0.1:${MANAGER_PORT}" --noreload >"${MANAGER_LOG}" 2>&1 &
MANAGER_PID=$!
wait_for_url "http://127.0.0.1:${MANAGER_PORT}/healthz/" "GoreeCloud Manager"

cd "${ROOT_DIR}"
PYTHONPATH="${MANAGER_REPO_DIR}" "${MANAGER_PYTHON}" scripts/manager_cross_app_assertions.py healthy

# The integration principal is a normal Viewer. Revocation must remove future visibility
# immediately without changing the bearer token or Manager configuration.
export DJANGO_SECRET_KEY="manager-e2e-tasks-django-secret-not-for-production"
"${TASKS_PYTHON}" scripts/manager_cross_app_fixture.py revoke
export DJANGO_SECRET_KEY="manager-e2e-manager-django-secret-not-for-production"

PYTHONPATH="${MANAGER_REPO_DIR}" "${MANAGER_PYTHON}" scripts/manager_cross_app_assertions.py revoked

echo "Disposable GoreeCloud Tasks and Manager cross-application validation passed."
