#!/usr/bin/env bash
set -Eeuo pipefail

require_tunnel=false
if [[ "${1:-}" == "--require-tunnel" ]]; then
  require_tunnel=true
  shift
fi

if [[ $# -ne 1 ]]; then
  printf 'Usage: %s [--require-tunnel] ENV_FILE\n' "$0" >&2
  exit 2
fi

env_file="$1"
if [[ ! -f "$env_file" ]]; then
  printf 'Environment file not found: %s\n' "$env_file" >&2
  exit 1
fi

read_value() {
  local key="$1"
  local line
  line="$(sed -n "s/^${key}=//p" "$env_file" | tail -n 1)"
  line="${line%$'\r'}"

  if [[ "$line" == \"*\" && "$line" == *\" ]]; then
    line="${line:1:${#line}-2}"
  elif [[ "$line" == \'*\' && "$line" == *\' ]]; then
    line="${line:1:${#line}-2}"
  fi

  printf '%s' "$line"
}

required=(
  POSTGRES_ADMIN_PASSWORD
  AUTH_DATABASE_PASSWORD
  APP_DATABASE_PASSWORD
  REDIS_PASSWORD
)

declare -A seen=()
for key in "${required[@]}"; do
  value="$(read_value "$key")"

  if [[ -z "$value" ]]; then
    printf '%s is missing or empty in %s\n' "$key" "$env_file" >&2
    exit 1
  fi

  if [[ "$value" == change-me-* || "$value" == replace-with-* || ${#value} -lt 24 ]]; then
    printf '%s must be replaced with a random value of at least 24 characters.\n' "$key" >&2
    exit 1
  fi

  if [[ -n "${seen[$value]:-}" ]]; then
    printf '%s must not reuse the same secret as %s.\n' "$key" "${seen[$value]}" >&2
    exit 1
  fi

  seen[$value]="$key"
done

if [[ "$require_tunnel" == true ]]; then
  tunnel_token="$(read_value CLOUDFLARE_TUNNEL_TOKEN)"
  if [[ -z "$tunnel_token" || "$tunnel_token" == change-me-* || "$tunnel_token" == replace-with-* ]]; then
    printf 'CLOUDFLARE_TUNNEL_TOKEN must be set before starting the tunnel.\n' >&2
    exit 1
  fi
fi
