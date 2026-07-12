PYTHON ?= python3
BACKEND_VENV := backend/.venv
BACKEND_PYTHON := $(BACKEND_VENV)/bin/python
ENV_FILE ?= .env
COMPOSE ?= docker compose
COMPOSE_BASE = $(COMPOSE) --env-file $(ENV_FILE) -f compose.yaml
COMPOSE_DEV = $(COMPOSE_BASE) -f compose.dev.yaml

.PHONY: install install-backend install-frontend \
	dev-backend dev-frontend \
	infra-check-env infra-config infra-up infra-up-internal infra-down infra-logs infra-ps \
	tunnel-up tunnel-down db-shell redis-cli db-backup db-restore \
	migrate migrate-auth migrate-app \
	test lint build check

install: install-backend install-frontend

install-backend:
	$(PYTHON) -m venv $(BACKEND_VENV)
	$(BACKEND_PYTHON) -m pip install --upgrade pip 'setuptools>=78.1.1'
	$(BACKEND_PYTHON) -m pip install -e 'backend[dev]'

install-frontend:
	cd frontend && npm install

dev-backend:
	cd backend && .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

dev-frontend:
	cd frontend && npm run dev

infra-check-env:
	@test -f "$(ENV_FILE)" || { \
		echo "$(ENV_FILE) がありません。.env.example をコピーして秘密値を設定してください。" >&2; \
		exit 1; \
	}
	@./infra/scripts/validate-env.sh "$(ENV_FILE)"

infra-config: infra-check-env
	$(COMPOSE_DEV) config --quiet

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
	cd frontend && npm run auth:migrate

migrate-app:
	cd backend && .venv/bin/alembic upgrade head

test:
	cd backend && .venv/bin/pytest

lint:
	cd backend && .venv/bin/ruff check .
	cd frontend && npm run lint

build:
	cd frontend && npm run build

check: test lint build
