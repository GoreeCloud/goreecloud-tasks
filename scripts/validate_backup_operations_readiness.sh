#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export COMPOSE_PROJECT_NAME="goreecloud-tasks-backup-ops-${GITHUB_RUN_ID:-local}"
WORK_DIR="$(mktemp -d)"
BACKUP_REPOSITORY="$WORK_DIR/independent-repository"
HEARTBEAT_LOG="$WORK_DIR/heartbeat-events.jsonl"
HEARTBEAT_PORT=19092
HEARTBEAT_PID=""
CREATED_ENV=false
CREATED_DJANGO_SECRET=false
CREATED_POSTGRES_SECRET=false

cleanup() {
  docker compose down --volumes --remove-orphans >/dev/null 2>&1 || true
  if [[ -n "$HEARTBEAT_PID" ]]; then
    kill "$HEARTBEAT_PID" >/dev/null 2>&1 || true
    wait "$HEARTBEAT_PID" >/dev/null 2>&1 || true
  fi
  [[ "$CREATED_ENV" == "true" ]] && rm -f .env
  [[ "$CREATED_DJANGO_SECRET" == "true" ]] && rm -f secrets/django_secret_key
  [[ "$CREATED_POSTGRES_SECRET" == "true" ]] && rm -f secrets/postgres_password
  rmdir secrets >/dev/null 2>&1 || true
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

fail() {
  printf 'backup operations readiness validation failed: %s\n' "$1" >&2
  exit 1
}

[[ ! -e .env ]] || fail "refusing to overwrite an existing .env"
[[ ! -e secrets/django_secret_key && ! -e secrets/postgres_password ]] || fail "refusing to overwrite existing development secret files"

cp .env.example .env
CREATED_ENV=true
printf '\nDJANGO_DEBUG=false\nAPP_PORT=18085\n' >> .env
chmod 600 .env
mkdir -p secrets
DJANGO_SECRET='ci-only-backup-ops-django-secret'
POSTGRES_SECRET='ci-only-backup-ops-postgres-password'
printf '%s\n' "$DJANGO_SECRET" > secrets/django_secret_key
printf '%s\n' "$POSTGRES_SECRET" > secrets/postgres_password
CREATED_DJANGO_SECRET=true
CREATED_POSTGRES_SECRET=true
sudo chgrp 20001 secrets/django_secret_key secrets/postgres_password
chmod 640 secrets/django_secret_key secrets/postgres_password
mkdir -m 700 "$BACKUP_REPOSITORY"

bash -n scripts/tasks_backup_job.sh
python -m py_compile scripts/backup_operations_probe.py
docker compose config --quiet

python scripts/backup_operations_probe.py serve --host 127.0.0.1 --port "$HEARTBEAT_PORT" --log "$HEARTBEAT_LOG" &
HEARTBEAT_PID=$!
for _ in $(seq 1 20); do
  curl --silent --output /dev/null "http://127.0.0.1:${HEARTBEAT_PORT}/ready" && break
  sleep 0.25
done
kill -0 "$HEARTBEAT_PID" >/dev/null 2>&1 || fail "disposable heartbeat receiver did not start"

docker compose build
docker compose up -d db
ready=false
for _ in $(seq 1 30); do
  if docker compose exec -T db sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 1
done
[[ "$ready" == "true" ]] || fail "PostgreSQL did not become ready"

docker compose run --rm web python manage.py migrate --noinput
docker compose run --rm web python scripts/backup_restore_fixture.py seed
docker compose run --rm web python scripts/backup_restore_fixture.py assert

run_backup() {
  BACKUP_REPOSITORY="$BACKUP_REPOSITORY" \
  BACKUP_RETENTION_COUNT=3 \
  BACKUP_HEARTBEAT_URL="http://127.0.0.1:${HEARTBEAT_PORT}" \
  BACKUP_LOCK_FILE="$WORK_DIR/tasks-backup.lock" \
  BACKUP_DATABASE="${1:-}" \
  bash scripts/tasks_backup_job.sh
}

for _ in 1 2 3 4; do
  run_backup
  sleep 1
done

mapfile -t RETAINED_BACKUPS < <(find "$BACKUP_REPOSITORY" -mindepth 1 -maxdepth 1 -type d ! -name '.*.partial' -printf '%f\n' | sort)
[[ "${#RETAINED_BACKUPS[@]}" -eq 3 ]] || fail "retention did not preserve exactly three recovery points"
for backup_name in "${RETAINED_BACKUPS[@]}"; do
  backup_dir="$BACKUP_REPOSITORY/$backup_name"
  [[ -s "$backup_dir/tasks-postgresql.dump" ]] || fail "empty retained dump"
  [[ -s "$backup_dir/manifest.json" ]] || fail "missing retained manifest"
  [[ -s "$backup_dir/SHA256SUMS" ]] || fail "missing checksum manifest"
  (cd "$backup_dir" && sha256sum --check --status SHA256SUMS) || fail "checksum validation failed"
  docker compose exec -T db pg_restore --list < "$backup_dir/tasks-postgresql.dump" >/dev/null || fail "dump readability failed"
done

BEFORE_FAILURE="$(printf '%s\n' "${RETAINED_BACKUPS[@]}")"
if run_backup "goreecloud_tasks_missing_database"; then
  fail "forced backup failure unexpectedly succeeded"
fi
mapfile -t AFTER_FAILURE_BACKUPS < <(find "$BACKUP_REPOSITORY" -mindepth 1 -maxdepth 1 -type d ! -name '.*.partial' -printf '%f\n' | sort)
AFTER_FAILURE="$(printf '%s\n' "${AFTER_FAILURE_BACKUPS[@]}")"
[[ "$BEFORE_FAILURE" == "$AFTER_FAILURE" ]] || fail "failed backup changed valid recovery points"
if find "$BACKUP_REPOSITORY" -mindepth 1 -maxdepth 1 -type d -name '.*.partial' | grep -q .; then
  fail "failed backup left a partial recovery point"
fi

LATEST_MANIFEST="$BACKUP_REPOSITORY/${AFTER_FAILURE_BACKUPS[-1]}/manifest.json"
LATEST_EPOCH="$(python - "$LATEST_MANIFEST" <<'PY'
import json, sys
from datetime import datetime
m=json.load(open(sys.argv[1], encoding='utf-8'))
print(datetime.fromisoformat(m['created_at'].replace('Z','+00:00')).timestamp())
PY
)"
python scripts/backup_operations_probe.py evaluate --repository "$BACKUP_REPOSITORY" --max-age-seconds 3600 --now-epoch "$(python -c "print(float('$LATEST_EPOCH')+3599)")" | grep -q '"state": "healthy"' || fail "fresh backup not healthy"
if python scripts/backup_operations_probe.py evaluate --repository "$BACKUP_REPOSITORY" --max-age-seconds 3600 --now-epoch "$(python -c "print(float('$LATEST_EPOCH')+3601)")" > "$WORK_DIR/late.json"; then
  fail "missed-run simulation unexpectedly healthy"
fi
grep -q '"state": "late"' "$WORK_DIR/late.json" || fail "missed-run state was not late"

sleep 1
run_backup
mapfile -t RECOVERED_BACKUPS < <(find "$BACKUP_REPOSITORY" -mindepth 1 -maxdepth 1 -type d ! -name '.*.partial' -printf '%f\n' | sort)
[[ "${#RECOVERED_BACKUPS[@]}" -eq 3 ]] || fail "retention changed after recovery"

EVENTS_JSON="$(python scripts/backup_operations_probe.py events --log "$HEARTBEAT_LOG")"
python - "$EVENTS_JSON" <<'PY'
import json, sys
events=[x['event'] for x in json.loads(sys.argv[1])]
expected=[]
for _ in range(4): expected += ['start','success']
expected += ['start','fail','start','success']
if events != expected: raise SystemExit(f'unexpected heartbeat sequence: {events!r}')
PY
if grep -R --binary-files=without-match -F "$DJANGO_SECRET" "$BACKUP_REPOSITORY" "$HEARTBEAT_LOG" >/dev/null 2>&1; then fail "Django secret leaked"; fi
if grep -R --binary-files=without-match -F "$POSTGRES_SECRET" "$BACKUP_REPOSITORY" "$HEARTBEAT_LOG" >/dev/null 2>&1; then fail "PostgreSQL secret leaked"; fi

LATEST_BACKUP="$BACKUP_REPOSITORY/${RECOVERED_BACKUPS[-1]}/tasks-postgresql.dump"
docker compose exec -T db sh -eu -c 'dropdb --force -U "$POSTGRES_USER" "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" -O "$POSTGRES_USER" "$POSTGRES_DB"'
docker compose exec -T db sh -eu -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-acl --exit-on-error' < "$LATEST_BACKUP"
docker compose run --rm web python manage.py check
docker compose run --rm web python manage.py migrate --check
docker compose run --rm web python scripts/backup_restore_fixture.py assert
docker compose up -d web
healthy=false
for _ in $(seq 1 30); do
  if curl --fail --silent --show-error http://127.0.0.1:18085/health/ >/dev/null; then healthy=true; break; fi
  sleep 2
done
[[ "$healthy" == "true" ]] || fail "application did not become healthy after restore"

printf '%s\n' 'Backup operations readiness validation passed.'
printf '%s\n' 'Validated repeated native dumps, integrity, retention, failure preservation, heartbeat transitions, missed-run classification, recovery, clean-database restoration, authorization semantics, and live health.'
