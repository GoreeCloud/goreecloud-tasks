#!/usr/bin/env bash
set -euo pipefail

fail() {
  printf 'target runtime preflight failed: %s\n' "$1" >&2
  exit 1
}

require_env() {
  local name="$1"
  [[ -n "${!name:-}" ]] || fail "required preflight input is unset: $name"
}

require_mode() {
  local path="$1" expected="$2" actual
  actual="$(stat -c '%a' "$path")"
  [[ "$actual" == "$expected" ]] || fail "$path mode is $actual; expected $expected"
}

require_owner() {
  local path="$1" expected="$2" actual
  actual="$(stat -c '%u' "$path")"
  [[ "$actual" == "$expected" ]] || fail "$path owner UID is $actual; expected $expected"
}

require_group() {
  local path="$1" expected="$2" actual
  actual="$(stat -c '%g' "$path")"
  [[ "$actual" == "$expected" ]] || fail "$path group GID is $actual; expected $expected"
}

require_secret_file() {
  local path="$1"
  [[ -f "$path" ]] || fail "required secret file is missing: $path"
  [[ ! -L "$path" ]] || fail "secret file must not be a symbolic link: $path"
  require_mode "$path" 640
  require_owner "$path" "$PREFLIGHT_SECRET_OWNER_UID"
  require_group "$path" "$PREFLIGHT_SECRET_GID"
}

for command_name in docker stat getent; do
  command -v "$command_name" >/dev/null 2>&1 || fail "required command is unavailable: $command_name"
done

require_env PREFLIGHT_ENV_PATH
require_env PREFLIGHT_SECRET_DIR
require_env PREFLIGHT_DJANGO_SECRET_PATH
require_env PREFLIGHT_POSTGRES_SECRET_PATH
require_env PREFLIGHT_SECRET_OWNER_UID
require_env PREFLIGHT_SECRET_GID
require_env PREFLIGHT_APP_SECRET_GID

[[ "$PREFLIGHT_SECRET_OWNER_UID" =~ ^[0-9]+$ ]] || fail "PREFLIGHT_SECRET_OWNER_UID must be numeric"
[[ "$PREFLIGHT_SECRET_GID" =~ ^[0-9]+$ ]] || fail "PREFLIGHT_SECRET_GID must be numeric"
[[ "$PREFLIGHT_APP_SECRET_GID" =~ ^[0-9]+$ ]] || fail "PREFLIGHT_APP_SECRET_GID must be numeric"
[[ "$PREFLIGHT_SECRET_GID" == "$PREFLIGHT_APP_SECRET_GID" ]] || fail "configured application secret GID does not match inspected file GID"

[[ -f "$PREFLIGHT_ENV_PATH" ]] || fail "environment file is missing: $PREFLIGHT_ENV_PATH"
[[ ! -L "$PREFLIGHT_ENV_PATH" ]] || fail "environment file must not be a symbolic link"
[[ -d "$PREFLIGHT_SECRET_DIR" ]] || fail "secret directory is missing: $PREFLIGHT_SECRET_DIR"
[[ ! -L "$PREFLIGHT_SECRET_DIR" ]] || fail "secret directory must not be a symbolic link"

require_mode "$PREFLIGHT_ENV_PATH" 600
require_owner "$PREFLIGHT_ENV_PATH" "$PREFLIGHT_SECRET_OWNER_UID"
require_mode "$PREFLIGHT_SECRET_DIR" 700
require_owner "$PREFLIGHT_SECRET_DIR" "$PREFLIGHT_SECRET_OWNER_UID"
require_secret_file "$PREFLIGHT_DJANGO_SECRET_PATH"
require_secret_file "$PREFLIGHT_POSTGRES_SECRET_PATH"

getent passwd "$PREFLIGHT_SECRET_OWNER_UID" >/dev/null || fail "secret owner UID does not resolve to a host account"
getent group "$PREFLIGHT_SECRET_GID" >/dev/null || fail "secret GID does not resolve to a host group"

engine_version="$(docker version --format '{{.Server.Version}}')"
compose_version="$(docker compose version --short)"
[[ -n "$engine_version" ]] || fail "Docker Engine server version could not be read"
[[ -n "$compose_version" ]] || fail "Docker Compose version could not be read"

printf '%s\n' 'Target runtime metadata preflight passed.'
printf 'Docker Engine: %s\n' "$engine_version"
printf 'Docker Compose: %s\n' "$compose_version"
printf 'Secret owner UID: %s\n' "$PREFLIGHT_SECRET_OWNER_UID"
printf 'Secret group GID: %s\n' "$PREFLIGHT_SECRET_GID"
printf 'Environment mode: %s\n' "$(stat -c '%a' "$PREFLIGHT_ENV_PATH")"
printf 'Secret directory mode: %s\n' "$(stat -c '%a' "$PREFLIGHT_SECRET_DIR")"
printf '%s\n' 'Validated file metadata without reading or printing configuration or secret contents.'
