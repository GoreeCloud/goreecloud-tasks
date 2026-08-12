#!/usr/bin/env bash
set -euo pipefail

# Isolated ntfy integration validation for GoreeCloud Tasks.
# This script creates only disposable CI identities, ACLs, and tokens.
# It never connects to or modifies the production GoreeCloud ntfy service.

NTFY_IMAGE="${NTFY_VALIDATION_IMAGE:-binwiederhier/ntfy:v2.26.3@sha256:081b53dbb20674fcfe05fdb4eb8af9036a2645ef979543d16f7f80803af467b1}"
NTFY_PORT="${NTFY_VALIDATION_PORT:-18080}"
CONTAINER_NAME="goreecloud-tasks-ntfy-validation-${GITHUB_RUN_ID:-local}-$$"
TOPIC="goreecloud-tasks-validation-user"
OTHER_TOPIC="goreecloud-tasks-validation-other"
WORKDIR="$(mktemp -d)"

cleanup() {
  docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
  rm -rf "${WORKDIR}"
}
trap cleanup EXIT

random_token() {
  python - <<'PY'
import secrets
import string

alphabet = string.ascii_lowercase + string.digits
print("tk_" + "".join(secrets.choice(alphabet) for _ in range(29)))
PY
}

PUBLISHER_TOKEN="$(random_token)"
SUBSCRIBER_TOKEN="$(random_token)"
OUTSIDER_TOKEN="$(random_token)"

# The bcrypt hash below is the public example hash from ntfy's own documentation.
# Password authentication is never used in this validation. Runtime-random access
# tokens are the only credentials used by the test process.
TEST_PASSWORD_HASH='$2a$10$YLiO8U21sX1uhZamTLJXHuxgVC0Z/GKISibrKCLohPgtG7yIxSk4C'

cat >"${WORKDIR}/server.yml" <<EOF
listen-http: ":80"
cache-file: "/var/lib/ntfy/cache.db"
cache-duration: "1h"
auth-file: "/var/lib/ntfy/auth.db"
auth-default-access: "deny-all"
enable-login: true
require-login: true
enable-signup: false
auth-users:
  - "tasks-ci-publisher:${TEST_PASSWORD_HASH}:user"
  - "tasks-ci-subscriber:${TEST_PASSWORD_HASH}:user"
  - "tasks-ci-outsider:${TEST_PASSWORD_HASH}:user"
auth-access:
  - "tasks-ci-publisher:goreecloud-tasks-*:write-only"
  - "tasks-ci-subscriber:${TOPIC}:read-only"
  - "tasks-ci-outsider:${OTHER_TOPIC}:read-only"
auth-tokens:
  - "tasks-ci-publisher:${PUBLISHER_TOKEN}:GoreeCloud Tasks CI publisher"
  - "tasks-ci-subscriber:${SUBSCRIBER_TOKEN}:GoreeCloud Tasks CI subscriber"
  - "tasks-ci-outsider:${OUTSIDER_TOKEN}:GoreeCloud Tasks CI outsider"
EOF
chmod 0444 "${WORKDIR}/server.yml"

docker run --detach --rm \
  --name "${CONTAINER_NAME}" \
  --publish "127.0.0.1:${NTFY_PORT}:80" \
  --user "1001:1001" \
  --security-opt no-new-privileges:true \
  --cap-drop ALL \
  --tmpfs "/var/lib/ntfy:rw,nosuid,nodev,noexec,size=64m,uid=1001,gid=1001,mode=0700" \
  --volume "${WORKDIR}/server.yml:/etc/ntfy/server.yml:ro" \
  "${NTFY_IMAGE}" \
  serve >/dev/null

for attempt in $(seq 1 30); do
  if curl --fail --silent --show-error \
    "http://127.0.0.1:${NTFY_PORT}/v1/health" >/dev/null; then
    break
  fi
  if [[ "${attempt}" -eq 30 ]]; then
    docker logs "${CONTAINER_NAME}" || true
    echo "Disposable ntfy server did not become healthy." >&2
    exit 1
  fi
  sleep 1
done

export DJANGO_SECRET_KEY="ci-only-ntfy-live-validation-key"
export DJANGO_DEBUG="false"
export DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1,testserver"
export DATABASE_ENGINE="sqlite"
export NTFY_BASE_URL="http://127.0.0.1:${NTFY_PORT}"
export NTFY_ACCESS_TOKEN="${PUBLISHER_TOKEN}"
export NTFY_VALIDATION_SUBSCRIBER_TOKEN="${SUBSCRIBER_TOKEN}"
export NTFY_VALIDATION_OUTSIDER_TOKEN="${OUTSIDER_TOKEN}"
export NTFY_VALIDATION_TOPIC="${TOPIC}"
export NTFY_VALIDATION_LIVE="1"
export TASKS_BASE_URL=""

python manage.py test tests.test_ntfy_live_integration --verbosity 2
