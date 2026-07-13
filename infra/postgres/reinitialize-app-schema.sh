#!/bin/sh
set -eu

repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
env_file=${ENV_FILE:-"$repository_root/.env"}

if [ "${CONFIRM_REINITIALIZE_APP_SCHEMA:-}" != "1" ]; then
  echo "app schemaの全データを削除します。実行するにはCONFIRM_REINITIALIZE_APP_SCHEMA=1を指定してください。" >&2
  exit 1
fi

docker compose \
  --env-file "$env_file" \
  -f "$repository_root/compose.yaml" \
  -f "$repository_root/compose.dev.yaml" \
  exec -T postgres sh -ec '
    psql \
      --username "$POSTGRES_USER" \
      --dbname "$POSTGRES_DB" \
      --set=ON_ERROR_STOP=1 \
      --command "DROP SCHEMA IF EXISTS app CASCADE; CREATE SCHEMA app AUTHORIZATION sodai_app; GRANT USAGE ON SCHEMA app TO sodai_app"
  '
