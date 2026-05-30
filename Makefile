UV ?= uv

.PHONY: help sync doctor lint format format-check typecheck test test-fast check-toolchain check-contracts check-doc-consistency check-hooks check-shell check-lanes check-hygiene check-secrets check-cd check-fast check-push check-required check-ci check-foundation

help:
	@printf '%s\n' \
		'Targets:' \
		'  make sync                  Install locked dev dependencies' \
		'  make doctor                Inspect local dev environment without changing it' \
		'  make lint                  Run ruff' \
		'  make format                Format supported files with ruff' \
		'  make format-check          Verify ruff formatting without changing files' \
		'  make typecheck             Run mypy' \
		'  make test                  Run pytest' \
		'  make test-fast             Run fast structural pytest smoke checks' \
		'  make check-toolchain       Report local toolchain versions' \
		'  make check-contracts       Run contract model tests' \
		'  make check-doc-consistency Run doc consistency tests' \
		'  make check-hooks           Run shell syntax checks on hooks/scripts' \
		'  make check-shell           Run ShellCheck on tracked shell hooks/scripts' \
		'  make check-lanes           Validate parallel lane-map templates and records' \
		'  make check-hygiene         Run repo hygiene guardrails' \
		'  make check-secrets         Run Gitleaks with redacted output' \
		'  make check-fast            Run fast local/push checks' \
		'  make check-push            Run pre-push gate; set FOUNDATION_FULL_PUSH=1 for full' \
		'  make check-required        Run required local checks' \
		'  make check-ci              Run full CI-equivalent checks' \
		'  make check-cd              Run deployment-readiness guard' \
		'  make check-foundation      Run the Foundation Robustness Gate'

sync:
	$(UV) sync --frozen --group dev

doctor:
	sh scripts/check-dev-environment.sh

lint:
	$(UV) run ruff check .

format:
	$(UV) run ruff format .

format-check:
	$(UV) run ruff format --check .

typecheck:
	$(UV) run mypy

test:
	$(UV) run pytest

test-fast:
	$(UV) run pytest -q tests/test_contract_models.py tests/test_extension_surface_integrity.py tests/test_system_design_integrity.py

check-toolchain:
	@git --version | sed 's/^/ok: /'
	@$(UV) --version | sed 's/^/ok: /'
	@python3 --version | sed 's/^/ok: /'
	@shellcheck --version | sed -n 's/^version: /ok: shellcheck /p' | head -n 1
	@gitleaks version | sed 's/^/ok: gitleaks /'

check-contracts:
	$(UV) run pytest tests/test_contract_models.py

check-doc-consistency:
	$(UV) run pytest tests/test_foundation_integrity.py -k "doc_consistency or work_contract_git_scope"

check-hooks:
	sh -n scripts/setup-agent-environment.sh
	sh -n scripts/check-agent-worktree-policy.sh
	sh -n scripts/check-dev-environment.sh
	sh -n scripts/check-repo-hygiene.sh
	sh -n scripts/check-secrets.sh
	sh -n scripts/check-shell-static-analysis.sh
	sh -n hooks/pre-commit
	sh -n hooks/pre-push

check-shell:
	sh scripts/check-shell-static-analysis.sh

check-lanes:
	$(UV) run python scripts/check-lane-map.py

check-hygiene:
	sh scripts/check-repo-hygiene.sh

check-secrets:
	sh scripts/check-secrets.sh

check-cd:
	$(UV) run pytest tests/test_foundation_integrity.py -k cd_readiness

check-fast: format-check lint check-hooks check-lanes test-fast

check-push:
	@if [ "$${FOUNDATION_FULL_PUSH:-0}" = "1" ]; then \
		$(MAKE) check-foundation; \
	else \
		$(MAKE) check-fast; \
	fi

check-required: format-check lint typecheck check-hooks check-shell check-hygiene check-secrets check-lanes test

check-ci: check-toolchain check-required check-cd

check-foundation: check-ci
