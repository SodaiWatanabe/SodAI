PYTHON ?= python3
BACKEND_VENV := backend/.venv
BACKEND_PYTHON := $(BACKEND_VENV)/bin/python
INFERENCE_VENV := inference/.venv
INFERENCE_PYTHON := $(INFERENCE_VENV)/bin/python
ENV_FILE ?= .env
PRODUCTION_ENV_FILE ?= .env.production
PRODUCTION_AUTH_ENV_FILE ?= auth/.env.production
PRODUCTION_BACKEND_ENV_FILE ?= backend/.env.production
PRODUCTION_FRONTEND_ENV_FILE ?= frontend/.env.production
COMPOSE ?= docker compose
COMPOSE_BASE = $(COMPOSE) --env-file $(ENV_FILE) -f compose.yaml
COMPOSE_DEV = $(COMPOSE_BASE) -f compose.dev.yaml
DEV_FRONTEND_HOST ?= 127.0.0.1
DEV_FRONTEND_PORT ?= 13200
DEV_AUTH_HOST ?= 127.0.0.1
DEV_AUTH_PORT ?= 13201
DEV_BACKEND_HOST ?= 127.0.0.1
DEV_BACKEND_PORT ?= 13202

.PHONY: install install-contracts install-auth install-backend install-frontend install-inference \
	dev-auth dev-backend dev-frontend dev-inference import-hina import-asuka1 \
	deploy-hina deploy-asuka1 \
	inference-status credits-grant credits-expire credits-audit human-rank test-inference-e2e \
	test-asuka1-e2e \
	infra-check-env infra-config production-config infra-up infra-up-internal infra-down infra-logs infra-ps \
	tunnel-up tunnel-down db-shell redis-cli db-backup db-restore \
	migrate migrate-auth migrate-app reinitialize-app-schema \
	test test-integration lint build check

install: install-auth install-backend install-frontend install-inference

install-auth:
	cd auth && npm install

install-contracts: $(BACKEND_VENV)/bin/python
	$(BACKEND_PYTHON) -m pip install -e packages/contracts

$(BACKEND_VENV)/bin/python:
	$(PYTHON) -m venv $(BACKEND_VENV)

install-backend: $(BACKEND_VENV)/bin/python
	$(BACKEND_PYTHON) -m pip install --upgrade pip 'setuptools>=78.1.1'
	$(BACKEND_PYTHON) -m pip install -e packages/contracts
	$(BACKEND_PYTHON) -m pip install -e 'backend[dev]'

install-frontend:
	cd frontend && npm install

install-inference:
	$(PYTHON) -m venv $(INFERENCE_VENV)
	$(INFERENCE_PYTHON) -m pip install --upgrade pip 'setuptools>=78.1.1'
	$(INFERENCE_PYTHON) -m pip install 'torch==2.5.1' --index-url https://download.pytorch.org/whl/cu121
	$(INFERENCE_PYTHON) -m pip install -e packages/contracts
	$(INFERENCE_PYTHON) -m pip install -e 'inference[dev]'

dev-auth:
	cd auth && AUTH_HOST=$(DEV_AUTH_HOST) AUTH_PORT=$(DEV_AUTH_PORT) npm run dev

dev-backend:
	cd backend && .venv/bin/uvicorn app.main:app --reload \
		--host $(DEV_BACKEND_HOST) --port $(DEV_BACKEND_PORT)

dev-frontend:
	cd frontend && npm run dev -- \
		--hostname $(DEV_FRONTEND_HOST) --port $(DEV_FRONTEND_PORT)

dev-inference: infra-check-env
	set -a; . ./$(ENV_FILE); set +a; exec env \
		$(if $(MODEL),SODAI_INFERENCE_MODEL="$(MODEL)") \
		$(if $(ARTIFACT_ID),SODAI_INFERENCE_ARTIFACT_ID="$(ARTIFACT_ID)") \
		$(if $(DEVICE),SODAI_INFERENCE_DEVICE="$(DEVICE)") \
		$(if $(HINA_ARTIFACT_ID),HINA_ARTIFACT_ID="$(HINA_ARTIFACT_ID)") \
		$(INFERENCE_VENV)/bin/sodai-inference

import-hina: infra-check-env
	@test -n "$(CHECKPOINT)" || { echo 'CHECKPOINT=/path/to/gpt_sft.pt を指定してください。' >&2; exit 1; }
	@test -n "$(TOKENIZER)" || { echo 'TOKENIZER=/path/to/tokenizer を指定してください。' >&2; exit 1; }
	set -a; . ./$(ENV_FILE); set +a; exec $(INFERENCE_VENV)/bin/sodai-import-hina \
		--checkpoint "$(CHECKPOINT)" \
		--tokenizer "$(TOKENIZER)" \
		$(if $(SOURCE_REPOSITORY),--source-repository "$(SOURCE_REPOSITORY)")

import-asuka1: infra-check-env
	@test -n "$(CHECKPOINT)" || { echo 'CHECKPOINT=/path/to/gpt_sft.pt を指定してください。' >&2; exit 1; }
	@test -n "$(TOKENIZER)" || { echo 'TOKENIZER=/path/to/tokenizer を指定してください。' >&2; exit 1; }
	set -a; . ./$(ENV_FILE); set +a; exec $(INFERENCE_VENV)/bin/sodai-import-asuka1 \
		--checkpoint "$(CHECKPOINT)" \
		--tokenizer "$(TOKENIZER)" \
		$(if $(SOURCE_REPOSITORY),--source-repository "$(SOURCE_REPOSITORY)")

deploy-hina: infra-check-env
	@test -n "$(ARTIFACT_ID)" || { echo 'ARTIFACT_ID=<artifact-id> を指定してください。' >&2; exit 1; }
	set -a; . ./$(ENV_FILE); set +a; exec $(INFERENCE_VENV)/bin/sodai-deploy-hina "$(ARTIFACT_ID)"

deploy-asuka1: infra-check-env
	@test -n "$(ARTIFACT_ID)" || { echo 'ARTIFACT_ID=<artifact-id> を指定してください。' >&2; exit 1; }
	set -a; . ./$(ENV_FILE); set +a; exec $(INFERENCE_VENV)/bin/sodai-deploy-asuka1 "$(ARTIFACT_ID)"

inference-status:
	cd backend && .venv/bin/python -m app.cli.inference_status

credits-grant:
	@test -n "$(USER_ID)" || { echo 'USER_ID=<uuid> を指定してください。' >&2; exit 1; }
	@test -n "$(AMOUNT)" || { echo 'AMOUNT=<最小クレジット単位> を指定してください。' >&2; exit 1; }
	@test -n "$(IDEMPOTENCY_KEY)" || { echo 'IDEMPOTENCY_KEY=<一意キー> を指定してください。' >&2; exit 1; }
	cd backend && .venv/bin/python -m app.cli.credits_grant \
		--user-id "$(USER_ID)" --amount "$(AMOUNT)" --idempotency-key "$(IDEMPOTENCY_KEY)" \
		$(if $(SOURCE_KIND),--source-kind "$(SOURCE_KIND)") \
		$(if $(EXPIRES_AT),--expires-at "$(EXPIRES_AT)")

credits-expire:
	cd backend && .venv/bin/python -m app.cli.credits_expire

credits-audit:
	cd backend && .venv/bin/python -m app.cli.credits_audit

human-rank:
	@test -n "$(USER_ID)" || { echo 'USER_ID=<uuid> を指定してください。' >&2; exit 1; }
	@test -n "$(RANK)" || { echo 'RANK=<level> を指定してください。' >&2; exit 1; }
	cd backend && .venv/bin/python -m app.cli.human_rank \
		--user-id "$(USER_ID)" --rank "$(RANK)"

test-inference-e2e: infra-check-env
	ENV_FILE="$(ENV_FILE)" ./infra/scripts/test-inference-e2e.sh

test-asuka1-e2e: infra-check-env
	MODEL=asuka-1 ENV_FILE="$(ENV_FILE)" ./infra/scripts/test-inference-e2e.sh

infra-check-env:
	@test -f "$(ENV_FILE)" || { \
		echo "$(ENV_FILE) がありません。.env.example をコピーして秘密値を設定してください。" >&2; \
		exit 1; \
	}
	@./infra/scripts/validate-env.sh "$(ENV_FILE)"

infra-config: infra-check-env
	$(COMPOSE_DEV) config --quiet

production-config:
	@./infra/scripts/validate-production-env.sh \
		"$(PRODUCTION_ENV_FILE)" \
		"$(PRODUCTION_AUTH_ENV_FILE)" \
		"$(PRODUCTION_BACKEND_ENV_FILE)" \
		"$(PRODUCTION_FRONTEND_ENV_FILE)"
	$(COMPOSE) --env-file "$(PRODUCTION_ENV_FILE)" -f compose.yaml config --quiet

# Host上で動くFastAPI/Next.jsから利用する開発構成。データポートは127.0.0.1限定。
infra-up: infra-check-env
	$(COMPOSE_DEV) up -d --wait postgres redis mailpit

# アプリもComposeネットワーク内で動かす構成。DB/Redisのホストポートは公開しない。
infra-up-internal: infra-check-env
	$(COMPOSE_BASE) up -d --wait postgres redis

infra-down: infra-check-env
	$(COMPOSE_DEV) down --remove-orphans

infra-logs: infra-check-env
	$(COMPOSE_DEV) logs -f postgres redis mailpit

infra-ps: infra-check-env
	$(COMPOSE_DEV) ps

tunnel-up: infra-check-env
	@./infra/scripts/validate-env.sh --require-tunnel "$(ENV_FILE)"
	$(COMPOSE_BASE) --profile tunnel up -d cloudflared

tunnel-down: infra-check-env
	$(COMPOSE_BASE) --profile tunnel stop cloudflared

db-shell: infra-check-env
	$(COMPOSE_BASE) exec postgres sh -ec 'exec psql --username "$$POSTGRES_USER" --dbname "$$POSTGRES_DB"'

redis-cli: infra-check-env
	$(COMPOSE_BASE) exec redis sh -ec 'REDISCLI_AUTH="$$REDIS_PASSWORD" exec redis-cli'

db-backup: infra-check-env
	ENV_FILE="$(abspath $(ENV_FILE))" ./infra/postgres/backup.sh

db-restore: infra-check-env
	@test -n "$(BACKUP)" || { echo 'BACKUP=/path/to/sodai.dump を指定してください。' >&2; exit 1; }
	ENV_FILE="$(abspath $(ENV_FILE))" ./infra/postgres/restore.sh "$(BACKUP)"

migrate: migrate-auth migrate-app

migrate-auth:
	cd auth && npm run migrate

migrate-app:
	cd backend && .venv/bin/alembic upgrade head

reinitialize-app-schema: infra-check-env
	ENV_FILE="$(abspath $(ENV_FILE))" sh ./infra/postgres/reinitialize-app-schema.sh
	$(MAKE) migrate-app

test:
	./infra/scripts/test-validate-production-env.sh
	cd auth && npm test
	$(BACKEND_PYTHON) -m pytest packages/contracts/tests
	cd backend && .venv/bin/pytest
	cd inference && .venv/bin/pytest
	cd frontend && npm test

test-integration: infra-check-env
	ENV_FILE="$(ENV_FILE)" ./infra/scripts/test-backend-integration.sh
	set -a; . ./$(ENV_FILE); set +a; cd inference && \
		SODAI_INTEGRATION_TESTS=1 .venv/bin/pytest tests/test_redis_integration.py

lint:
	cd auth && npm run lint && npm run typecheck
	$(BACKEND_PYTHON) -m ruff check packages/contracts
	cd backend && .venv/bin/ruff check .
	cd inference && .venv/bin/ruff check .
	cd frontend && npm run lint

build:
	cd auth && npm run build
	cd frontend && npm run build

check: test lint build
