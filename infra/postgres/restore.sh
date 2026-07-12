#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  printf 'Usage: %s [--yes] BACKUP.dump\n' "$0" >&2
}

assume_yes=false
if [[ "${1:-}" == "--yes" ]]; then
  assume_yes=true
  shift
fi

if [[ $# -ne 1 ]]; then
  usage
  exit 2
fi

backup_input="$1"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
env_file="${ENV_FILE:-$repo_root/.env}"

if [[ ! -r "$backup_input" ]]; then
  printf 'Backup is not readable: %s\n' "$backup_input" >&2
  exit 1
fi

backup="$(realpath "$backup_input")"

if [[ ! -f "$env_file" ]]; then
  printf 'Environment file not found: %s\n' "$env_file" >&2
  exit 1
fi

if [[ -f "$backup.sha256" ]]; then
  (cd "$(dirname "$backup")" && sha256sum --check "$(basename "$backup").sha256")
else
  printf 'Warning: checksum file not found: %s.sha256\n' "$backup" >&2
fi

if [[ "$assume_yes" != true ]]; then
  printf 'This replaces the current sodai database contents. Type "restore sodai" to continue: '
  read -r confirmation
  if [[ "$confirmation" != "restore sodai" ]]; then
    printf 'Restore cancelled.\n' >&2
    exit 1
  fi
fi

compose=(docker compose --env-file "$env_file" -f "$repo_root/compose.yaml")

"${compose[@]}" exec -T postgres sh -eu -c \
  'exec pg_restore --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --clean --if-exists --exit-on-error --single-transaction' \
  <"$backup"

printf 'Restore completed from %s\n' "$backup"
