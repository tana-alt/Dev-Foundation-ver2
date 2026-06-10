UV ?= uv


.PHONY: help sync doctor lint format format-check typecheck test test-fast check-toolchain check-contracts check-doc-consistency check-hooks check-shell check-lanes check-workflow-state check-skill-routes check-context-scope check-result-envelope check-residual-risk-carryover check-review-convergence check-audit-provenance check-operational-scorecard check-agent-operational check-hygiene check-secrets check-cd check-frozen gate eval check-fast check-push check-required check-ci check-foundation

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
		'  make check-workflow-state  Validate Workflow Core state template' \
		'  make check-skill-routes    Validate operational skill routes and budgets' \
		'  make check-context-scope   Validate context-scope and budget records' \
		'  make check-result-envelope Validate checker result envelopes' \
		'  make check-residual-risk-carryover Validate residual-risk carryover records' \
		'  make check-review-convergence Validate review/fix/convergence records' \
		'  make check-audit-provenance Validate audit and source snapshot records' \
		'  make check-operational-scorecard Validate operational scorecard records' \
		'  make check-agent-operational Run legacy operational record checks' \
		'  make check-legacy-contracts Run archived heavy-contract compatibility checks' \
		'  make check-hygiene         Run repo hygiene guardrails' \
		'  make check-secrets         Run Gitleaks with redacted output' \
		'  make check-fast            Run fast local/push checks' \
		'  make check-push            Run pre-push gate; set FOUNDATION_FULL_PUSH=1 for full' \
		'  make check-required        Run required local checks' \
		'  make check-ci              Run full CI-equivalent checks' \
		'  make check-cd              Run deployment-readiness guard' \
		'  make check-frozen          Block staged edits to spec-frozen paths' \
		'  make gate                  Run the completion gate (re-runs checks, binds diff hash, writes evidence)' \
		'  make eval                  Run the eval suite and print harness signals' \
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
	$(UV) run pytest tests/test_contract_models.py tests/workflow_core

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

check-workflow-state:
	$(UV) run python scripts/check-workflow-state.py templates/workflow-core/state-record.yaml

check-skill-routes:
	$(UV) run python scripts/check-skill-routes.py

check-context-scope:
	$(UV) run python scripts/check-context-scope.py

check-result-envelope:
	$(UV) run python scripts/check-result-envelope.py

check-residual-risk-carryover:
	$(UV) run python scripts/check-residual-risk-carryover.py

check-review-convergence:
	$(UV) run python scripts/check-review-convergence.py

check-audit-provenance:
	$(UV) run python scripts/check-audit-provenance.py

check-operational-scorecard:
	$(UV) run python scripts/check-operational-scorecard.py

check-agent-operational: check-skill-routes check-context-scope check-result-envelope check-residual-risk-carryover check-review-convergence check-audit-provenance check-operational-scorecard

check-legacy-contracts: check-lanes check-agent-operational check-contracts

check-hygiene:
	sh scripts/check-repo-hygiene.sh

check-secrets:
	sh scripts/check-secrets.sh

check-cd:
	$(UV) run pytest tests/test_foundation_integrity.py -k cd_readiness

check-frozen:
	$(UV) run python scripts/check-frozen-paths.py

gate:
	$(UV) run python scripts/completion_gate.py

eval:
	$(UV) run python scripts/run_eval.py

check-fast: format-check lint check-hooks test-fast

check-push:
	@if [ "$${FOUNDATION_FULL_PUSH:-0}" = "1" ]; then \
		$(MAKE) check-foundation; \
	else \
		$(MAKE) check-fast; \
	fi

check-required: format-check lint typecheck check-hooks check-shell check-hygiene check-secrets test

check-ci: check-toolchain check-required check-cd

check-foundation: check-ci
