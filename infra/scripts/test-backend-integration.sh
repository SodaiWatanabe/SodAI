#!/bin/sh
set -eu

repository_root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
cd "$repository_root"

env_file=${ENV_FILE:-.env}
test -f "$env_file" || {
  echo "$env_file がありません。" >&2
  exit 1
}

set -a
. "./$env_file"
set +a

run_id=$(backend/.venv/bin/python -c 'import uuid; print(uuid.uuid4().hex[:12])')
database_name="sodai_integration_$run_id"

database_url=$(backend/.venv/bin/python - "$database_name" <<'PY'
import os
import sys
from sqlalchemy.engine import make_url

sys.path.insert(0, "backend")
from app.core.config import get_settings

database_name = sys.argv[1]
if not database_name.startswith("sodai_integration_"):
    raise SystemExit("unsafe integration database name")
url = make_url(get_settings().database_url)
if url.host not in {"127.0.0.1", "localhost", "::1"}:
    raise SystemExit("integration PostgreSQL must use the local development endpoint")
if (url.port or 13203) != int(os.getenv("POSTGRES_PORT", "13203")):
    raise SystemExit("integration PostgreSQL port must match the development endpoint")
print(url.set(database=database_name).render_as_string(hide_password=False))
PY
)

cleanup() {
  exit_code=$?
  trap - EXIT INT TERM
  docker compose --env-file "$env_file" -f compose.yaml -f compose.dev.yaml \
    exec -T -e INTEGRATION_DB="$database_name" postgres sh -ec '
      psql --username "$POSTGRES_USER" --dbname postgres --set=ON_ERROR_STOP=1 \
        --set=db_name="$INTEGRATION_DB" <<SQL
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :'"'"'db_name'"'"';
DROP DATABASE IF EXISTS :"db_name";
SQL
    ' >/dev/null 2>&1 || true
  exit "$exit_code"
}
trap cleanup EXIT INT TERM

docker compose --env-file "$env_file" -f compose.yaml -f compose.dev.yaml \
  exec -T -e INTEGRATION_DB="$database_name" postgres sh -ec '
    psql --username "$POSTGRES_USER" --dbname postgres --set=ON_ERROR_STOP=1 \
      --set=db_name="$INTEGRATION_DB" <<SQL
CREATE DATABASE :"db_name";
SQL
    psql --username "$POSTGRES_USER" --dbname "$INTEGRATION_DB" --set=ON_ERROR_STOP=1 \
      --set=db_name="$INTEGRATION_DB" <<SQL
REVOKE ALL ON DATABASE :"db_name" FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
CREATE SCHEMA app AUTHORIZATION sodai_app;
GRANT CONNECT ON DATABASE :"db_name" TO sodai_app;
GRANT USAGE ON SCHEMA app TO sodai_app;
SQL
  ' >/dev/null

(cd backend && DATABASE_URL="$database_url" .venv/bin/alembic upgrade 20260715_0005)
DATABASE_URL="$database_url" \
SODAI_HUMAN_STANDARD_MIGRATION_TEST=prepare \
backend/.venv/bin/pytest -q backend/tests/test_human_standard_migration.py
(cd backend && DATABASE_URL="$database_url" .venv/bin/alembic upgrade 20260731_0009)
DATABASE_URL="$database_url" \
SODAI_HUMAN_STANDARD_MIGRATION_TEST=verify \
backend/.venv/bin/pytest -q backend/tests/test_human_standard_migration.py
DATABASE_URL="$database_url" \
SODAI_EARNED_EXPIRATION_MIGRATION_TEST=prepare \
backend/.venv/bin/pytest -q backend/tests/test_earned_expiration_migration.py
(cd backend && DATABASE_URL="$database_url" .venv/bin/alembic upgrade head)
(cd backend && DATABASE_URL="$database_url" .venv/bin/alembic check)
DATABASE_URL="$database_url" \
SODAI_EARNED_EXPIRATION_MIGRATION_TEST=verify \
backend/.venv/bin/pytest -q backend/tests/test_earned_expiration_migration.py

(cd backend && DATABASE_URL="$database_url" .venv/bin/alembic downgrade 20260713_0002)
(cd backend && DATABASE_URL="$database_url" .venv/bin/alembic upgrade head)
(cd backend && DATABASE_URL="$database_url" .venv/bin/alembic check)
DATABASE_URL="$database_url" \
SODAI_CREDIT_BACKFILL_TEST=1 \
backend/.venv/bin/pytest -q backend/tests/test_credit_migration_backfill.py

DATABASE_URL="$database_url" \
SODAI_MODEL_ROOT="$repository_root/backend/tests/fixtures/models" \
SODAI_INTEGRATION_TESTS=1 \
backend/.venv/bin/pytest -q \
  backend/tests/test_platform_integration.py \
  backend/tests/test_evaluation_integration.py \
  backend/tests/test_human_integration.py \
  backend/tests/test_credit_integration.py
