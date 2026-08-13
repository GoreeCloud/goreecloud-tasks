#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_KEY="${GITHUB_RUN_ID:-local}-$$"
export COMPOSE_PROJECT_NAME="goreecloud-tasks-upgrade-rollback-${RUN_KEY}"

WORK_DIR="$(mktemp -d)"
BASE_DIR="$WORK_DIR/base-source"
PRE_UPGRADE_DUMP="$WORK_DIR/pre-upgrade.dump"
BASELINE_SNAPSHOT="$WORK_DIR/baseline.json"
UPGRADED_SNAPSHOT="$WORK_DIR/upgraded.json"
ROLLED_BACK_SNAPSHOT="$WORK_DIR/rolled-back.json"
BASELINE_IMAGE_TAG="goreecloud-tasks-upgrade-baseline:${RUN_KEY}"
BASE_SERVICE_IMAGE="${COMPOSE_PROJECT_NAME}-web:latest"
CREATED_TARGET_ENV=false
CREATED_TARGET_DJANGO_SECRET=false
CREATED_TARGET_POSTGRES_SECRET=false
WORKTREE_ADDED=false

fail() {
  printf 'upgrade-rollback validation failed: %s\n' "$1" >&2
  exit 1
}

compose_for() {
  local checkout_dir="$1"
  shift
  docker compose \
    -p "$COMPOSE_PROJECT_NAME" \
    --project-directory "$checkout_dir" \
    --env-file "$checkout_dir/.env" \
    -f "$checkout_dir/compose.yml" \
    "$@"
}

cleanup() {
  compose_for "$ROOT_DIR" down --volumes --remove-orphans >/dev/null 2>&1 || true
  if [[ "$WORKTREE_ADDED" == "true" && -d "$BASE_DIR" ]]; then
    compose_for "$BASE_DIR" down --volumes --remove-orphans >/dev/null 2>&1 || true
  fi
  docker image rm "$BASELINE_IMAGE_TAG" >/dev/null 2>&1 || true

  if [[ "$CREATED_TARGET_ENV" == "true" ]]; then
    rm -f "$ROOT_DIR/.env"
  fi
  if [[ "$CREATED_TARGET_DJANGO_SECRET" == "true" ]]; then
    rm -f "$ROOT_DIR/secrets/django_secret_key"
  fi
  if [[ "$CREATED_TARGET_POSTGRES_SECRET" == "true" ]]; then
    rm -f "$ROOT_DIR/secrets/postgres_password"
  fi
  rmdir "$ROOT_DIR/secrets" >/dev/null 2>&1 || true

  if [[ "$WORKTREE_ADDED" == "true" ]]; then
    git worktree remove --force "$BASE_DIR" >/dev/null 2>&1 || true
  fi
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

prepare_checkout() {
  local checkout_dir="$1"
  cp "$checkout_dir/.env.example" "$checkout_dir/.env"
  printf '\nDJANGO_DEBUG=false\nAPP_PORT=18083\n' >> "$checkout_dir/.env"
  chmod 600 "$checkout_dir/.env"

  mkdir -p "$checkout_dir/secrets"
  printf '%s\n' 'ci-only-upgrade-rollback-django-secret' > "$checkout_dir/secrets/django_secret_key"
  printf '%s\n' 'ci-only-upgrade-rollback-postgres-password' > "$checkout_dir/secrets/postgres_password"
  sudo chgrp 20001 "$checkout_dir/secrets/django_secret_key" "$checkout_dir/secrets/postgres_password"
  chmod 640 "$checkout_dir/secrets/django_secret_key" "$checkout_dir/secrets/postgres_password"
}

wait_for_postgres() {
  local checkout_dir="$1"
  local ready=false
  for _ in $(seq 1 30); do
    if compose_for "$checkout_dir" exec -T db sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1; then
      ready=true
      break
    fi
    sleep 1
  done
  if [[ "$ready" != "true" ]]; then
    compose_for "$checkout_dir" ps
    compose_for "$checkout_dir" logs db
    fail "PostgreSQL did not become ready"
  fi
}

wait_for_health() {
  local checkout_dir="$1"
  local phase="$2"
  local healthy=false
  for _ in $(seq 1 30); do
    if curl --fail --silent --show-error http://127.0.0.1:18083/health/ >/dev/null 2>&1; then
      healthy=true
      break
    fi
    sleep 2
  done
  if [[ "$healthy" != "true" ]]; then
    compose_for "$checkout_dir" ps
    compose_for "$checkout_dir" logs web db
    fail "$phase application did not become healthy"
  fi
}

snapshot_with_baseline_fixture() {
  local checkout_dir="$1"
  local output_file="$2"
  compose_for "$checkout_dir" run --rm \
    -v "$BASE_DIR/scripts/backup_restore_fixture.py:/app/scripts/upgrade_rollback_baseline_fixture.py:ro" \
    web python scripts/upgrade_rollback_baseline_fixture.py snapshot > "$output_file"
}

assert_with_baseline_fixture() {
  local checkout_dir="$1"
  compose_for "$checkout_dir" run --rm \
    -v "$BASE_DIR/scripts/backup_restore_fixture.py:/app/scripts/upgrade_rollback_baseline_fixture.py:ro" \
    web python scripts/upgrade_rollback_baseline_fixture.py assert
}

if [[ -e "$ROOT_DIR/.env" ]]; then
  fail "refusing to overwrite an existing .env; run this only in an isolated checkout"
fi
if [[ -e "$ROOT_DIR/secrets/django_secret_key" || -e "$ROOT_DIR/secrets/postgres_password" ]]; then
  fail "refusing to overwrite existing development secret files"
fi

TARGET_REF="${UPGRADE_TARGET_REF:-$(git rev-parse HEAD)}"
BASE_REF="${UPGRADE_BASE_REF:-}"
if [[ -z "$BASE_REF" || "$BASE_REF" =~ ^0+$ ]]; then
  BASE_REF="$(git rev-parse "${TARGET_REF}^")"
fi

if ! git cat-file -e "${TARGET_REF}^{commit}" 2>/dev/null; then
  fail "target revision $TARGET_REF is not available in the checkout"
fi
if ! git cat-file -e "${BASE_REF}^{commit}" 2>/dev/null; then
  fail "baseline revision $BASE_REF is not available; CI must check out full history"
fi
if [[ "$(git rev-parse "$BASE_REF")" == "$(git rev-parse "$TARGET_REF")" ]]; then
  fail "baseline and target revisions must be different"
fi

printf 'Upgrade baseline: %s\n' "$(git rev-parse "$BASE_REF")"
printf 'Upgrade target:   %s\n' "$(git rev-parse "$TARGET_REF")"

git worktree add --detach "$BASE_DIR" "$BASE_REF" >/dev/null
WORKTREE_ADDED=true

if [[ ! -f "$BASE_DIR/scripts/backup_restore_fixture.py" ]]; then
  fail "baseline revision does not contain scripts/backup_restore_fixture.py"
fi
if [[ ! -f "$ROOT_DIR/scripts/backup_restore_fixture.py" ]]; then
  fail "target revision does not contain scripts/backup_restore_fixture.py"
fi

prepare_checkout "$BASE_DIR"
prepare_checkout "$ROOT_DIR"
CREATED_TARGET_ENV=true
CREATED_TARGET_DJANGO_SECRET=true
CREATED_TARGET_POSTGRES_SECRET=true

printf '%s\n' 'Validating baseline Compose configuration...'
compose_for "$BASE_DIR" config --quiet

printf '%s\n' 'Building the previous accepted application revision...'
compose_for "$BASE_DIR" build web
BASE_IMAGE_ID="$(compose_for "$BASE_DIR" images -q web | head -n 1)"
if [[ -z "$BASE_IMAGE_ID" ]]; then
  fail "could not resolve the baseline web image"
fi
docker image tag "$BASE_IMAGE_ID" "$BASELINE_IMAGE_TAG"

printf '%s\n' 'Starting PostgreSQL and creating baseline application state...'
compose_for "$BASE_DIR" up -d db
wait_for_postgres "$BASE_DIR"
compose_for "$BASE_DIR" run --rm web python manage.py migrate --noinput
compose_for "$BASE_DIR" run --rm web python scripts/backup_restore_fixture.py seed
compose_for "$BASE_DIR" run --rm web python scripts/backup_restore_fixture.py assert
compose_for "$BASE_DIR" run --rm web python scripts/backup_restore_fixture.py snapshot > "$BASELINE_SNAPSHOT"

printf '%s\n' 'Creating the pre-upgrade PostgreSQL rollback point...'
compose_for "$BASE_DIR" exec -T db sh -eu -c \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-acl' \
  > "$PRE_UPGRADE_DUMP"
if [[ ! -s "$PRE_UPGRADE_DUMP" ]]; then
  fail "pre-upgrade pg_dump produced an empty rollback artifact"
fi
compose_for "$BASE_DIR" exec -T db pg_restore --list < "$PRE_UPGRADE_DUMP" >/dev/null
PRE_UPGRADE_SHA256="$(sha256sum "$PRE_UPGRADE_DUMP" | awk '{print $1}')"

printf '%s\n' 'Starting the baseline application and verifying health before upgrade...'
compose_for "$BASE_DIR" up -d --force-recreate web
wait_for_health "$BASE_DIR" "baseline"
compose_for "$BASE_DIR" stop web >/dev/null

printf '%s\n' 'Building and applying the candidate revision against the existing baseline database...'
compose_for "$ROOT_DIR" config --quiet
compose_for "$ROOT_DIR" build web
TARGET_IMAGE_ID="$(compose_for "$ROOT_DIR" images -q web | head -n 1)"
if [[ -z "$TARGET_IMAGE_ID" ]]; then
  fail "could not resolve the target web image"
fi
if [[ "$TARGET_IMAGE_ID" == "$BASE_IMAGE_ID" ]]; then
  printf '%s\n' 'Target image is content-identical to the baseline image; continuing compatibility validation.'
fi
compose_for "$ROOT_DIR" run --rm web python manage.py migrate --noinput
compose_for "$ROOT_DIR" run --rm web python manage.py check
compose_for "$ROOT_DIR" run --rm web python manage.py migrate --check

printf '%s\n' 'Validating that pre-upgrade application state remains intact after upgrade...'
assert_with_baseline_fixture "$ROOT_DIR"
snapshot_with_baseline_fixture "$ROOT_DIR" "$UPGRADED_SNAPSHOT"
if ! cmp --silent "$BASELINE_SNAPSHOT" "$UPGRADED_SNAPSHOT"; then
  fail "baseline application state changed unexpectedly across the candidate upgrade"
fi
compose_for "$ROOT_DIR" run --rm web python scripts/backup_restore_fixture.py assert

printf '%s\n' 'Starting the upgraded application and verifying live health...'
compose_for "$ROOT_DIR" up -d --force-recreate web
wait_for_health "$ROOT_DIR" "upgraded"
compose_for "$ROOT_DIR" stop web >/dev/null

if [[ "$(sha256sum "$PRE_UPGRADE_DUMP" | awk '{print $1}')" != "$PRE_UPGRADE_SHA256" ]]; then
  fail "the pre-upgrade rollback artifact changed during upgrade validation"
fi

printf '%s\n' 'Executing rollback by restoring the pre-upgrade database and previous application image...'
compose_for "$ROOT_DIR" exec -T db sh -eu -c \
  'dropdb --force -U "$POSTGRES_USER" "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" -O "$POSTGRES_USER" "$POSTGRES_DB"'
compose_for "$ROOT_DIR" exec -T db sh -eu -c \
  'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-acl --exit-on-error' \
  < "$PRE_UPGRADE_DUMP"
docker image tag "$BASELINE_IMAGE_TAG" "$BASE_SERVICE_IMAGE"

printf '%s\n' 'Validating the rolled-back revision against the restored database...'
compose_for "$BASE_DIR" run --rm web python manage.py check
compose_for "$BASE_DIR" run --rm web python manage.py migrate --check
compose_for "$BASE_DIR" run --rm web python scripts/backup_restore_fixture.py assert
compose_for "$BASE_DIR" run --rm web python scripts/backup_restore_fixture.py snapshot > "$ROLLED_BACK_SNAPSHOT"
if ! cmp --silent "$BASELINE_SNAPSHOT" "$ROLLED_BACK_SNAPSHOT"; then
  fail "application state did not return exactly to the pre-upgrade baseline after rollback"
fi

printf '%s\n' 'Starting the rolled-back application and verifying live health...'
compose_for "$BASE_DIR" up -d --force-recreate web
wait_for_health "$BASE_DIR" "rolled-back"

printf '%s\n' 'Upgrade and rollback validation passed.'
printf '%s\n' 'Validated: previous accepted revision, real pre-upgrade PostgreSQL backup, candidate migrations and health, exact preservation of baseline user/task state, immutable rollback artifact, database restore, previous-image restart, migration consistency, authorization semantics, and exact post-rollback state.'
