#!/bin/sh
set -eu

: "${POSTGRES_DB:?POSTGRES_DB must be set}"
: "${POSTGRES_USER:?POSTGRES_USER must be set}"
: "${SODAI_AUTH_DB_PASSWORD:?SODAI_AUTH_DB_PASSWORD must be set}"
: "${SODAI_APP_DB_PASSWORD:?SODAI_APP_DB_PASSWORD must be set}"

psql \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --set=ON_ERROR_STOP=1 \
  --set=db_name="$POSTGRES_DB" \
  --set=auth_password="$SODAI_AUTH_DB_PASSWORD" \
  --set=app_password="$SODAI_APP_DB_PASSWORD" <<'SQL'
REVOKE ALL ON DATABASE :"db_name" FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

CREATE ROLE sodai_auth LOGIN PASSWORD :'auth_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE sodai_app LOGIN PASSWORD :'app_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;

CREATE SCHEMA auth AUTHORIZATION sodai_auth;
CREATE SCHEMA app AUTHORIZATION sodai_app;

GRANT CONNECT ON DATABASE :"db_name" TO sodai_auth, sodai_app;
GRANT USAGE ON SCHEMA auth TO sodai_auth;
GRANT USAGE ON SCHEMA app TO sodai_app;

ALTER ROLE sodai_auth IN DATABASE :"db_name" SET search_path = auth, public;
ALTER ROLE sodai_app IN DATABASE :"db_name" SET search_path = app, public;

COMMENT ON SCHEMA auth IS 'Authentication provider data owned by the self-hosted Better Auth role.';
COMMENT ON SCHEMA app IS 'Provider-neutral SodAI application data owned by the FastAPI role.';
SQL
