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

run_id=$(backend/.venv/bin/python -c 'import uuid; print(uuid.uuid4().hex)')
database_name="sodai_e2e_$(printf '%s' "$run_id" | cut -c1-12)"
namespace="sodai:e2e:$run_id:inference"

database_url=$(backend/.venv/bin/python - "$database_name" <<'PY'
import os
import sys
from sqlalchemy.engine import make_url
from urllib.parse import urlparse

sys.path.insert(0, "backend")
from app.core.config import get_settings

database_name = sys.argv[1]
if not database_name.startswith("sodai_e2e_"):
    raise SystemExit("unsafe E2E database name")
settings = get_settings()
url = make_url(settings.database_url)
local_hosts = {"127.0.0.1", "localhost", "::1"}
if url.host not in local_hosts or (url.port or 13203) != int(os.getenv("POSTGRES_PORT", "13203")):
    raise SystemExit("E2E PostgreSQL must use the local development endpoint")
redis = urlparse(settings.redis_url)
if redis.hostname not in local_hosts or (redis.port or 13204) != int(
    os.getenv("REDIS_PORT", "13204")
):
    raise SystemExit("E2E Redis must use the local development endpoint")
url = url.set(database=database_name)
print(url.render_as_string(hide_password=False))
PY
)

device=${HINA_E2E_DEVICE:-cuda:0}
inference/.venv/bin/python - "$device" <<'PY'
import sys

import torch

device = torch.device(sys.argv[1])
if device.type != "cuda" or not torch.cuda.is_available():
    raise SystemExit("Hina GPU E2E requires an available CUDA device")
index = device.index if device.index is not None else torch.cuda.current_device()
if index < 0 or index >= torch.cuda.device_count():
    raise SystemExit(f"CUDA device index is unavailable: {index}")
print(f"Hina GPU E2E device: cuda:{index} ({torch.cuda.get_device_name(index)})")
PY

worker_log=$(mktemp -t sodai-hina-e2e.XXXXXX.log)
worker_pid=""

cleanup() {
  exit_code=$?
  trap - EXIT INT TERM
  if test -n "$worker_pid" && kill -0 "$worker_pid" 2>/dev/null; then
    kill "$worker_pid" 2>/dev/null || true
    wait "$worker_pid" 2>/dev/null || true
  fi
  INFERENCE_NAMESPACE="$namespace" inference/.venv/bin/python <<'PY' || true
import asyncio
import os

from redis.asyncio import Redis


async def cleanup() -> None:
    redis = Redis.from_url(
        os.getenv("REDIS_URL", "redis://127.0.0.1:13204/0"),
        password=os.getenv("REDIS_PASSWORD") or None,
        decode_responses=True,
    )
    try:
        cursor = 0
        pattern = f"{os.environ['INFERENCE_NAMESPACE']}:*"
        while True:
            cursor, keys = await redis.scan(cursor, match=pattern, count=500)
            if keys:
                await redis.delete(*keys)
            if cursor == 0:
                break
    finally:
        await redis.aclose()


asyncio.run(cleanup())
PY
  docker compose --env-file "$env_file" -f compose.yaml -f compose.dev.yaml \
    exec -T -e E2E_DB="$database_name" postgres sh -ec '
      psql --username "$POSTGRES_USER" --dbname postgres --set=ON_ERROR_STOP=1 \
        --set=db_name="$E2E_DB" <<"SQL"
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :'"'"'db_name'"'"';
DROP DATABASE IF EXISTS :"db_name";
SQL
    ' >/dev/null 2>&1 || true
  if test "$exit_code" -ne 0; then
    echo "Hina E2E worker log:" >&2
    tail -n 120 "$worker_log" >&2 || true
  fi
  rm -f "$worker_log"
  exit "$exit_code"
}
trap cleanup EXIT INT TERM

docker compose --env-file "$env_file" -f compose.yaml -f compose.dev.yaml \
  exec -T -e E2E_DB="$database_name" postgres sh -ec '
    psql --username "$POSTGRES_USER" --dbname postgres --set=ON_ERROR_STOP=1 \
      --set=db_name="$E2E_DB" <<"SQL"
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :'"'"'db_name'"'"';
DROP DATABASE IF EXISTS :"db_name";
CREATE DATABASE :"db_name";
SQL
    psql --username "$POSTGRES_USER" --dbname "$E2E_DB" --set=ON_ERROR_STOP=1 \
      --set=db_name="$E2E_DB" <<"SQL"
REVOKE ALL ON DATABASE :"db_name" FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
CREATE SCHEMA app AUTHORIZATION sodai_app;
GRANT CONNECT ON DATABASE :"db_name" TO sodai_app;
GRANT USAGE ON SCHEMA app TO sodai_app;
SQL
  ' >/dev/null

(cd backend && DATABASE_URL="$database_url" .venv/bin/alembic upgrade head)

artifact_id=$(backend/.venv/bin/python <<'PY'
import sys

sys.path.insert(0, "backend")
from app.core.config import get_settings
from app.services.inference.deployment import ModelDeploymentRegistry

settings = get_settings()
print(ModelDeploymentRegistry(settings.model_root).resolve("hina").artifact_id)
PY
)

INFERENCE_NAMESPACE="$namespace" \
HINA_ARTIFACT_ID="$artifact_id" \
HINA_DEVICE="$device" \
INFERENCE_CONSUMER_NAME="e2e-$run_id" \
inference/.venv/bin/sodai-inference >"$worker_log" 2>&1 &
worker_pid=$!

INFERENCE_NAMESPACE="$namespace" HINA_ARTIFACT_ID="$artifact_id" \
inference/.venv/bin/python - "$worker_pid" <<'PY'
import asyncio
import os
import sys
from pathlib import Path

from redis.asyncio import Redis
from sodai_contracts.inference import InferenceNamespace


async def wait_until_ready() -> None:
    redis = Redis.from_url(
        os.getenv("REDIS_URL", "redis://127.0.0.1:13204/0"),
        password=os.getenv("REDIS_PASSWORD") or None,
        decode_responses=True,
    )
    namespace = InferenceNamespace(os.environ["INFERENCE_NAMESPACE"])
    readiness_key = namespace.worker_readiness("hina", os.environ["HINA_ARTIFACT_ID"])
    worker_pid = sys.argv[1]
    try:
        for _ in range(600):
            if await redis.exists(readiness_key):
                return
            if not Path(f"/proc/{worker_pid}").exists():
                raise SystemExit(f"Hina E2E worker {worker_pid} exited before readiness")
            await asyncio.sleep(0.25)
    finally:
        await redis.aclose()
    raise SystemExit(f"Hina E2E worker {worker_pid} did not become ready")


asyncio.run(wait_until_ready())
PY

DATABASE_URL="$database_url" \
INFERENCE_NAMESPACE="$namespace" \
HINA_E2E_DEVICE_USED="$device" \
SODAI_GPU_E2E=1 \
backend/.venv/bin/pytest -q backend/tests/test_hina_gpu_e2e.py
