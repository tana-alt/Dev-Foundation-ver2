UV := uv

.PHONY: sync lint format typecheck test check-architecture check-doc-freshness check-dangerous-diff check-harness-runtime check-required check-repo-profiles run knowledge-up knowledge-plugin-build knowledge-plugin-install onyx-local-prepare onyx-local-up onyx-local-down onyx-local-status compose-up compose-up-codex compose-down compose-codex-version

ONYX_DOCKER_DIR ?= $(HOME)/Desktop/onyx/deployment/docker_compose
ONYX_LOCAL_HOST_PORT ?= 3001
BRIDGE_PORT ?= 8011
BRIDGE_DATABASE_URL ?= sqlite+pysqlite:///./knowledge-bridge.sqlite3

sync:
	$(UV) sync --group dev

lint:
	$(UV) run ruff check .

format:
	$(UV) run ruff format .

typecheck:
	$(UV) run mypy apps src tests

test:
	$(UV) run pytest

check-architecture:
	$(UV) run python -m src.services.verification.cli architecture

check-doc-freshness:
	$(UV) run python -m src.services.verification.cli doc-freshness

check-dangerous-diff:
	$(UV) run python -m src.services.verification.cli dangerous-diff

check-harness-runtime:
	$(UV) run python -m src.services.verification.cli harness-runtime

check-repo-profiles:
	$(UV) run python scripts/repo_profiles/check_profile_contracts.py

check-required:
	$(MAKE) lint
	$(MAKE) typecheck
	$(MAKE) test
	$(MAKE) check-architecture
	$(MAKE) check-doc-freshness
	$(MAKE) check-dangerous-diff
	$(MAKE) check-repo-profiles

run:
	env DATABASE_URL="$(BRIDGE_DATABASE_URL)" \
		$(UV) run uvicorn apps.api.main:app --host 0.0.0.0 --port $(BRIDGE_PORT) --reload

knowledge-up:
	env DATABASE_URL="$(BRIDGE_DATABASE_URL)" \
		$(UV) run uvicorn apps.api.main:app --host 127.0.0.1 --port $(BRIDGE_PORT) --reload

knowledge-plugin-build:
	cd apps/obsidian-plugin && npm install && npm run build

knowledge-plugin-install:
	cd apps/obsidian-plugin && npm install && npm run install:sample-vault

onyx-local-prepare:
	./scripts/onyx/setup_local.sh "$(ONYX_DOCKER_DIR)" "$(ONYX_LOCAL_HOST_PORT)"

onyx-local-up: onyx-local-prepare
	docker compose \
		--project-name onyx-local \
		-f "$(ONYX_DOCKER_DIR)/docker-compose.yml" \
		-f "$(PWD)/scripts/onyx/docker-compose.port-3001.yml" \
		up -d --wait

onyx-local-down:
	docker compose \
		--project-name onyx-local \
		-f "$(ONYX_DOCKER_DIR)/docker-compose.yml" \
		-f "$(PWD)/scripts/onyx/docker-compose.port-3001.yml" \
		down

onyx-local-status:
	@echo "Multica UI:  http://127.0.0.1:3000"
	@echo "Onyx UI:     http://127.0.0.1:$(ONYX_LOCAL_HOST_PORT)"
	@echo "Onyx API:    http://127.0.0.1:$(ONYX_LOCAL_HOST_PORT)/api"
	@echo "Bridge API:  http://127.0.0.1:$(BRIDGE_PORT)"
	@echo "Bridge DB:   $(BRIDGE_DATABASE_URL)"

compose-up:
	docker compose up --build

compose-up-codex:
	@test -n "$(CODEX_HOST_AUTH_FILE)" || (echo "Set CODEX_HOST_AUTH_FILE to your auth.json path." && exit 1)
	@test -f "$(CODEX_HOST_AUTH_FILE)" || (echo "Missing auth file: $(CODEX_HOST_AUTH_FILE)" && exit 1)
	docker compose -f docker-compose.yml -f docker-compose.codex-auth.yml up --build

compose-codex-version:
	@test -n "$(CODEX_HOST_AUTH_FILE)" || (echo "Set CODEX_HOST_AUTH_FILE to your auth.json path." && exit 1)
	@test -f "$(CODEX_HOST_AUTH_FILE)" || (echo "Missing auth file: $(CODEX_HOST_AUTH_FILE)" && exit 1)
	docker compose -f docker-compose.yml -f docker-compose.codex-auth.yml run --rm --no-deps api codex --version

compose-down:
	docker compose down --volumes
