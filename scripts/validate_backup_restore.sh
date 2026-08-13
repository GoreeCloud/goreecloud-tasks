#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export COMPOSE_PROJECT_NAME="goreecloud-tasks-backup-restore-${GITHUB_RUN_ID:-local}"

WORK_DIR="$(mktemp -d)"
BACKUP_FILE="$WORK_DIR/goreecloud-tasks.dump"
BEFORE_SNAPSHOT="$WORK_DIR/before.json"
AFTER_SNAPSHOT="$WORK_DIR/after.json"
CREATED_ENV=false
CREATED_DJANGO_SECRET=false
CREATED_POSTGRES_SECRET=false

cleanup() {
  docker compose down --volumes --remove-orphans >/dev/null 2>&1 || true

  if [[ "$CREATED_ENV" == "true" ]]; then
    rm -f .env
  fi
  if [[ "$CREATED_DJANGO_SECRET" == "true" ]]; then
    rm -f secrets/django_secret_key
  fi
  if [[ "$CREATED_POSTGRES_SECRET" == "true" ]]; then
    rm -f secrets/postgres_password
  fi
  rmdir secrets >/dev/null 2>&1 || true
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

fail() {
  printf 'backup-restore validation failed: %s\n' "$1" >&2
  exit 1
}

if [[ -e .env ]]; then
  fail "refusing to overwrite an existing .env; run this only in an isolated checkout"
fi
if [[ -e secrets/django_secret_key || -e secrets/postgres_password ]]; then
  fail "refusing to overwrite existing development secret files"
fi

cp .env.example .env
CREATED_ENV=true
printf '\nDJANGO_DEBUG=false\nAPP_PORT=18081\n' >> .env
chmod 600 .env

mkdir -p secrets
printf '%s\n' 'ci-only-backup-restore-django-secret' > secrets/django_secret_key
CREATED_DJANGO_SECRET=true
printf '%s\n' 'ci-only-backup-restore-postgres-password' > secrets/postgres_password
CREATED_POSTGRES_SECRET=true
sudo chgrp 20001 secrets/django_secret_key secrets/postgres_password
chmod 640 secrets/django_secret_key secrets/postgres_password

printf '%s\n' 'Validating isolated Compose configuration...'
docker compose config --quiet

printf '%s\n' 'Building the GoreeCloud Tasks application image...'
docker compose build

printf '%s\n' 'Starting disposable PostgreSQL...'
docker compose up -d db

ready=false
for _ in $(seq 1 30); do
  if docker compose exec -T db sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 1
done
if [[ "$ready" != "true" ]]; then
  docker compose ps
  docker compose logs db
  fail "PostgreSQL did not become ready"
fi

printf '%s\n' 'Applying migrations and creating the synthetic recovery fixture...'
docker compose run --rm web python manage.py migrate --noinput
docker compose run --rm web python scripts/backup_restore_fixture.py seed
docker compose run --rm web python scripts/backup_restore_fixture.py assert
docker compose run --rm web python scripts/backup_restore_fixture.py snapshot > "$BEFORE_SNAPSHOT"

printf '%s\n' 'Creating a real PostgreSQL custom-format dump...'
docker compose exec -T db sh -eu -c \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-acl' \
  > "$BACKUP_FILE"

if [[ ! -s "$BACKUP_FILE" ]]; then
  fail "pg_dump produced an empty backup file"
fi

docker compose exec -T db pg_restore --list < "$BACKUP_FILE" >/dev/null

printf '%s\n' 'Simulating database loss by replacing the disposable database...'
docker compose stop web >/dev/null 2>&1 || true
docker compose exec -T db sh -eu -c \
  'dropdb --force -U "$POSTGRES_USER" "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" -O "$POSTGRES_USER" "$POSTGRES_DB"'

TABLE_COUNT="$(docker compose exec -T db sh -eu -c \
  'psql -At -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname = '\''public'\'';"' \
  | tr -d '[:space:]')"
if [[ "$TABLE_COUNT" != "0" ]]; then
  fail "replacement database was not empty before restore"
fi

printf '%s\n' 'Restoring the PostgreSQL dump into the clean database...'
docker compose exec -T db sh -eu -c \
  'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-acl --exit-on-error' \
  < "$BACKUP_FILE"

printf '%s\n' 'Validating restored schema and exact synthetic application state...'
docker compose run --rm web python manage.py check
docker compose run --rm web python manage.py migrate --check
docker compose run --rm web python scripts/backup_restore_fixture.py snapshot > "$AFTER_SNAPSHOT"

if ! cmp --silent "$BEFORE_SNAPSHOT" "$AFTER_SNAPSHOT"; then
  python - "$BEFORE_SNAPSHOT" "$AFTER_SNAPSHOT" <<'PY'
import json
import sys

before = json.load(open(sys.argv[1], encoding="utf-8"))
after = json.load(open(sys.argv[2], encoding="utf-8"))
for key in sorted(set(before) | set(after)):
    if before.get(key) != after.get(key):
        print(f"Restored snapshot differs in section: {key}", file=sys.stderr)
PY
  fail "normalized application state changed across PostgreSQL restoration"
fi

docker compose run --rm web python scripts/backup_restore_fixture.py assert

printf '%s\n' 'Starting the restored web application and validating live health...'
docker compose up -d web
healthy=false
for _ in $(seq 1 30); do
  if curl --fail --silent --show-error http://127.0.0.1:18081/health/ >/dev/null; then
    healthy=true
    break
  fi
  sleep 2
done
if [[ "$healthy" != "true" ]]; then
  docker compose ps
  docker compose logs web db
  fail "restored application did not become healthy"
fi

printf '%s\n' 'PostgreSQL backup/restoration validation passed.'
printf '%s\n' 'Validated: real pg_dump/pg_restore, clean-target recovery, exact normalized state, authentication, authorization, history, operational metadata, notifications, reminders, migrations, and live health.'
