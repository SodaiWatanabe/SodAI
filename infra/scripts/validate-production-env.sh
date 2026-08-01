#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 4 ]]; then
  printf 'Usage: %s ROOT_ENV AUTH_ENV BACKEND_ENV FRONTEND_ENV\n' "$0" >&2
  exit 2
fi

root_env="$1"
auth_env="$2"
backend_env="$3"
frontend_env="$4"
canonical_origin="https://app.sodai.me"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for env_file in "$root_env" "$auth_env" "$backend_env" "$frontend_env"; do
  if [[ ! -f "$env_file" ]]; then
    printf 'Production environment file not found: %s\n' "$env_file" >&2
    exit 1
  fi
done

"$script_dir/validate-env.sh" --require-tunnel "$root_env"

read_value() {
  local env_file="$1"
  local key="$2"
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

fail() {
  printf '%s\n' "$1" >&2
  exit 1
}

require_value() {
  local env_file="$1"
  local key="$2"
  local value
  value="$(read_value "$env_file" "$key")"
  [[ -n "$value" ]] || fail "$key is required in $env_file."
}

require_equal() {
  local env_file="$1"
  local key="$2"
  local expected="$3"
  local value
  value="$(read_value "$env_file" "$key")"
  [[ "$value" == "$expected" ]] || fail "$key must be $expected in $env_file."
}

require_non_placeholder() {
  local env_file="$1"
  local key="$2"
  local value
  value="$(read_value "$env_file" "$key")"
  [[ -n "$value" ]] || fail "$key is required in $env_file."
  case "$value" in
    *change-me*|*replace-with*) fail "$key contains a placeholder in $env_file." ;;
  esac
}

require_secret() {
  local env_file="$1"
  local key="$2"
  local minimum_length="$3"
  local value
  require_non_placeholder "$env_file" "$key"
  value="$(read_value "$env_file" "$key")"
  (( ${#value} >= minimum_length )) || fail "$key must be at least $minimum_length characters in $env_file."
}

require_database_password_match() {
  local service_env="$1"
  local url_key="$2"
  local password_key="$3"
  local database_url
  local credentials
  local url_password
  local expected_password
  database_url="$(read_value "$service_env" "$url_key")"
  expected_password="$(read_value "$root_env" "$password_key")"
  credentials="${database_url#*://}"
  credentials="${credentials%%@*}"
  [[ "$credentials" == *:* ]] || fail "$url_key must contain database credentials in $service_env."
  url_password="${credentials#*:}"
  [[ "$url_password" == "$expected_password" ]] || \
    fail "$url_key must use $password_key from $root_env."
}

require_origin() {
  local env_file="$1"
  local key="$2"
  local value
  value="$(read_value "$env_file" "$key")"
  [[ "$value" =~ ^https?://[^/?#]+$ ]] || fail "$key must be an absolute origin without a path in $env_file."
}

require_absolute_url() {
  local env_file="$1"
  local key="$2"
  local value
  value="$(read_value "$env_file" "$key")"
  [[ "$value" =~ ^https?://[^/?#]+(/[^?#]*)?$ ]] || fail "$key must be an absolute HTTP URL in $env_file."
}

require_internal_origin() {
  local env_file="$1"
  local key="$2"
  local value
  require_origin "$env_file" "$key"
  value="$(read_value "$env_file" "$key")"
  [[ "$value" != *"sodai.me"* ]] || fail "$key must use an internal service address in $env_file."
}

require_equal "$root_env" SODAI_PUBLIC_ORIGIN "$canonical_origin"
require_value "$root_env" SODAI_IMAGE_TAG
image_tag="$(read_value "$root_env" SODAI_IMAGE_TAG)"
[[ "$image_tag" =~ ^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$ ]] || \
  fail "SODAI_IMAGE_TAG must be a valid container image tag in $root_env."

require_non_placeholder "$auth_env" AUTH_DATABASE_URL
require_database_password_match "$auth_env" AUTH_DATABASE_URL AUTH_DATABASE_PASSWORD
require_secret "$auth_env" BETTER_AUTH_SECRET 32
require_equal "$auth_env" BETTER_AUTH_URL "$canonical_origin"
require_equal "$auth_env" BETTER_AUTH_TRUSTED_ORIGINS "$canonical_origin"
require_equal "$auth_env" AUTH_TRUSTED_CLIENT_IP_HEADER cf-connecting-ip
require_equal "$auth_env" AUTH_EMAIL_DELIVERY smtp
require_non_placeholder "$auth_env" AUTH_EMAIL_FROM
auth_email_from="$(read_value "$auth_env" AUTH_EMAIL_FROM)"
[[ "$auth_email_from" == *"@auth.sodai.me"* ]] || \
  fail "AUTH_EMAIL_FROM must use the verified auth.sodai.me domain in $auth_env."
require_equal "$auth_env" AUTH_SMTP_HOST smtp.resend.com
require_equal "$auth_env" AUTH_SMTP_PORT 465
require_equal "$auth_env" AUTH_SMTP_SECURE true
require_equal "$auth_env" AUTH_SMTP_USER resend
require_secret "$auth_env" AUTH_SMTP_PASSWORD 16

google_client_id="$(read_value "$auth_env" GOOGLE_CLIENT_ID)"
google_client_secret="$(read_value "$auth_env" GOOGLE_CLIENT_SECRET)"
if [[ -n "$google_client_id" || -n "$google_client_secret" ]]; then
  [[ -n "$google_client_id" && -n "$google_client_secret" ]] || \
    fail "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must both be set or both be omitted in $auth_env."
  require_non_placeholder "$auth_env" GOOGLE_CLIENT_ID
  require_secret "$auth_env" GOOGLE_CLIENT_SECRET 16
fi

require_equal "$backend_env" APP_ENV production
require_equal "$backend_env" FRONTEND_ORIGIN "$canonical_origin"
require_equal "$backend_env" GUEST_COOKIE_SECURE true
require_non_placeholder "$backend_env" DATABASE_URL
require_database_password_match "$backend_env" DATABASE_URL APP_DATABASE_PASSWORD
require_non_placeholder "$backend_env" REDIS_URL
require_equal "$backend_env" AUTH_ISSUER "$canonical_origin"
require_equal "$backend_env" AUTH_AUDIENCE "$canonical_origin"
require_absolute_url "$backend_env" AUTH_JWKS_URL
backend_jwks_url="$(read_value "$backend_env" AUTH_JWKS_URL)"
[[ "$backend_jwks_url" != *"sodai.me"* ]] || \
  fail "AUTH_JWKS_URL must use the internal Auth service address in $backend_env."

require_equal "$frontend_env" NEXT_PUBLIC_API_BASE_URL "$canonical_origin"
require_internal_origin "$frontend_env" SODAI_API_BASE_URL
require_internal_origin "$frontend_env" AUTH_SERVICE_URL

printf 'Production environment contract is valid for %s.\n' "$canonical_origin"
