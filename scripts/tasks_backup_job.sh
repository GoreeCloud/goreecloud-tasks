#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

fail() {
  printf 'tasks backup job failed: %s\n' "$1" >&2
  exit 1
}

: "${BACKUP_REPOSITORY:?BACKUP_REPOSITORY is required}"
: "${BACKUP_RETENTION_COUNT:?BACKUP_RETENTION_COUNT is required}"
: "${BACKUP_HEARTBEAT_URL:?BACKUP_HEARTBEAT_URL is required}"

COMPOSE_FILE="${BACKUP_COMPOSE_FILE:-compose.yml}"
DB_SERVICE="${BACKUP_DB_SERVICE:-db}"
BACKUP_DATABASE="${BACKUP_DATABASE:-}"
LOCK_FILE="${BACKUP_LOCK_FILE:-${BACKUP_REPOSITORY}/.tasks-backup.lock}"

if [[ ! "$BACKUP_RETENTION_COUNT" =~ ^[1-9][0-9]*$ ]]; then
  fail "BACKUP_RETENTION_COUNT must be a positive integer"
fi
if [[ "$BACKUP_HEARTBEAT_URL" != http://127.0.0.1:* && "$BACKUP_HEARTBEAT_URL" != https://* ]]; then
  fail "BACKUP_HEARTBEAT_URL must use HTTPS except for disposable loopback validation"
fi

for command_name in docker curl sha256sum flock python; do
  command -v "$command_name" >/dev/null 2>&1 || fail "required command is unavailable: $command_name"
done

mkdir -p "$BACKUP_REPOSITORY"
chmod 700 "$BACKUP_REPOSITORY" 2>/dev/null || true

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  fail "another Tasks backup job is already running"
fi

heartbeat() {
  local suffix="$1"
  curl --fail --silent --show-error \
    --connect-timeout 3 \
    --max-time 10 \
    --retry 2 \
    --retry-delay 1 \
    "${BACKUP_HEARTBEAT_URL}${suffix}" >/dev/null
}

BACKUP_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$-${RANDOM}"
PARTIAL_DIR="${BACKUP_REPOSITORY}/.${BACKUP_ID}.partial"
FINAL_DIR="${BACKUP_REPOSITORY}/${BACKUP_ID}"
DUMP_FILE="${PARTIAL_DIR}/tasks-postgresql.dump"
CHECKSUM_FILE="${PARTIAL_DIR}/SHA256SUMS"
MANIFEST_FILE="${PARTIAL_DIR}/manifest.json"
BACKUP_FINALIZED=false

cleanup_partial() {
  if [[ "$BACKUP_FINALIZED" != "true" ]]; then
    rm -rf "$PARTIAL_DIR"
  fi
}
trap cleanup_partial EXIT

printf '%s\n' 'Tasks backup: sending start heartbeat.'
heartbeat "/start" || fail "start heartbeat failed"

mkdir -m 700 "$PARTIAL_DIR"

if [[ -z "$BACKUP_DATABASE" ]]; then
  BACKUP_DATABASE="$(docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" sh -eu -c 'printf %s "$POSTGRES_DB"')"
fi

printf '%s\n' 'Tasks backup: creating PostgreSQL custom-format dump.'
if ! docker compose -f "$COMPOSE_FILE" exec -T -e BACKUP_DATABASE="$BACKUP_DATABASE" "$DB_SERVICE" sh -eu -c \
  'pg_dump -U "$POSTGRES_USER" -d "$BACKUP_DATABASE" --format=custom --no-owner --no-acl' \
  > "$DUMP_FILE"; then
  heartbeat "/fail" || true
  fail "PostgreSQL dump failed"
fi

if [[ ! -s "$DUMP_FILE" ]]; then
  heartbeat "/fail" || true
  fail "PostgreSQL dump is empty"
fi

printf '%s\n' 'Tasks backup: validating dump readability.'
if ! docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" pg_restore --list < "$DUMP_FILE" >/dev/null; then
  heartbeat "/fail" || true
  fail "pg_restore could not enumerate the dump"
fi

(
  cd "$PARTIAL_DIR"
  sha256sum tasks-postgresql.dump > SHA256SUMS
)

CREATED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python - "$MANIFEST_FILE" "$BACKUP_ID" "$CREATED_AT" "$BACKUP_DATABASE" <<'PY'
import json
import sys

path, backup_id, created_at, database = sys.argv[1:]
manifest = {
    "schema": 1,
    "backup_id": backup_id,
    "created_at": created_at,
    "database": database,
    "format": "postgresql-custom",
    "dump": "tasks-postgresql.dump",
    "checksum": "SHA256SUMS",
    "integrity_check": "pg_restore --list",
}
with open(path, "w", encoding="utf-8") as handle:
    json.dump(manifest, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
chmod 600 "$DUMP_FILE" "$CHECKSUM_FILE" "$MANIFEST_FILE"

mv "$PARTIAL_DIR" "$FINAL_DIR"
BACKUP_FINALIZED=true

printf '%s\n' 'Tasks backup: applying configured recovery-point retention.'
mapfile -t COMPLETE_BACKUPS < <(
  find "$BACKUP_REPOSITORY" -mindepth 1 -maxdepth 1 -type d \
    ! -name '.*.partial' -printf '%f\n' | sort
)
if (( ${#COMPLETE_BACKUPS[@]} > BACKUP_RETENTION_COUNT )); then
  REMOVE_COUNT=$(( ${#COMPLETE_BACKUPS[@]} - BACKUP_RETENTION_COUNT ))
  for backup_name in "${COMPLETE_BACKUPS[@]:0:REMOVE_COUNT}"; do
    rm -rf -- "${BACKUP_REPOSITORY}/${backup_name}"
  done
fi

printf '%s\n' 'Tasks backup: sending success heartbeat.'
if ! heartbeat ""; then
  fail "backup completed but success heartbeat failed"
fi

printf 'Tasks backup completed successfully: %s\n' "$BACKUP_ID"
