#!/usr/bin/env bash
set -Eeuo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
validator="$repository_root/infra/scripts/validate-production-env.sh"
fixture_dir="$(mktemp -d)"
trap 'rm -rf "$fixture_dir"' EXIT

root_env="$fixture_dir/root.env"
auth_env="$fixture_dir/auth.env"
backend_env="$fixture_dir/backend.env"
frontend_env="$fixture_dir/frontend.env"

write_valid_fixtures() {
  cat >"$root_env" <<'EOF'
POSTGRES_ADMIN_PASSWORD=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
AUTH_DATABASE_PASSWORD=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
APP_DATABASE_PASSWORD=cccccccccccccccccccccccccccccccc
REDIS_PASSWORD=dddddddddddddddddddddddddddddddd
CLOUDFLARE_TUNNEL_TOKEN=eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee
EOF

  cat >"$auth_env" <<'EOF'
BETTER_AUTH_URL=https://app.sodai.me
BETTER_AUTH_TRUSTED_ORIGINS=https://app.sodai.me
AUTH_DATABASE_URL=postgresql://sodai_auth:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb@postgres:5432/sodai
BETTER_AUTH_SECRET=ffffffffffffffffffffffffffffffff
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
AUTH_TRUSTED_CLIENT_IP_HEADER=cf-connecting-ip
AUTH_EMAIL_DELIVERY=smtp
AUTH_EMAIL_FROM=SodAI <no-reply@sodai.me>
AUTH_SMTP_HOST=smtp.sodai-mail.invalid
AUTH_SMTP_PORT=465
AUTH_SMTP_SECURE=true
AUTH_SMTP_USER=smtp-user
AUTH_SMTP_PASSWORD=gggggggggggggggggggggggggggggggg
EOF

  cat >"$backend_env" <<'EOF'
APP_ENV=production
FRONTEND_ORIGIN=https://app.sodai.me
GUEST_COOKIE_SECURE=true
DATABASE_URL=postgresql+asyncpg://sodai_app:cccccccccccccccccccccccccccccccc@postgres:5432/sodai
REDIS_URL=redis://redis:6379/0
AUTH_ISSUER=https://app.sodai.me
AUTH_AUDIENCE=https://app.sodai.me
AUTH_JWKS_URL=http://auth:13201/api/auth/jwks
EOF

  cat >"$frontend_env" <<'EOF'
NEXT_PUBLIC_API_BASE_URL=https://app.sodai.me
SODAI_API_BASE_URL=http://backend:13202
AUTH_SERVICE_URL=http://auth:13201
EOF
}

expect_failure() {
  if "$validator" "$root_env" "$auth_env" "$backend_env" "$frontend_env" >/dev/null 2>&1; then
    printf 'Expected production validation to fail: %s\n' "$1" >&2
    exit 1
  fi
}

write_valid_fixtures
"$validator" "$root_env" "$auth_env" "$backend_env" "$frontend_env" >/dev/null

sed -i 's#BETTER_AUTH_URL=https://app.sodai.me#BETTER_AUTH_URL=https://sodai.me#' "$auth_env"
expect_failure "apex domain used as the auth origin"

write_valid_fixtures
sed -i 's/GUEST_COOKIE_SECURE=true/GUEST_COOKIE_SECURE=false/' "$backend_env"
expect_failure "insecure guest cookie"

write_valid_fixtures
sed -i 's#NEXT_PUBLIC_API_BASE_URL=https://app.sodai.me#NEXT_PUBLIC_API_BASE_URL=https://api.sodai.me#' "$frontend_env"
expect_failure "cross-origin browser API"

write_valid_fixtures
sed -i 's#SODAI_API_BASE_URL=http://backend:13202#SODAI_API_BASE_URL=https://api.sodai.me#' "$frontend_env"
expect_failure "public hostname used for internal service discovery"

write_valid_fixtures
sed -i 's/AUTH_DATABASE_PASSWORD=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/AUTH_DATABASE_PASSWORD=hhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhh/' "$root_env"
expect_failure "database password mismatch"

write_valid_fixtures
sed -i 's/AUTH_SMTP_PASSWORD=gggggggggggggggggggggggggggggggg/AUTH_SMTP_PASSWORD=change-me/' "$auth_env"
expect_failure "SMTP placeholder"

printf 'Production environment validation tests passed.\n'
