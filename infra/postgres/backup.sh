#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
env_file="${ENV_FILE:-$repo_root/.env}"
backup_dir="${BACKUP_DIR:-$repo_root/backups/postgres}"

if [[ ! -f "$env_file" ]]; then
  printf 'Environment file not found: %s\n' "$env_file" >&2
  exit 1
fi

mkdir -p "$backup_dir"
chmod 700 "$backup_dir"
umask 077

timestamp="$(date -u +'%Y%m%dT%H%M%SZ')"
backup="$backup_dir/sodai-$timestamp.dump"
temporary="$backup.partial"
compose=(docker compose --env-file "$env_file" -f "$repo_root/compose.yaml")

cleanup() {
  rm -f "$temporary"
}
trap cleanup EXIT

"${compose[@]}" exec -T postgres sh -eu -c \
  'exec pg_dump --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --format=custom' \
  >"$temporary"

mv "$temporary" "$backup"
(
  cd "$backup_dir"
  sha256sum "$(basename "$backup")" >"$(basename "$backup").sha256"
)

trap - EXIT
printf '%s\n' "$backup"
