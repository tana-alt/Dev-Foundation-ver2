UV ?= uv

.PHONY: help sync sync-data sync-crypto sync-research sync-screening sync-baseline sync-nautilus sync-hft sync-hummingbot-api sync-monitoring sync-notebooks sync-performance sync-reporting doctor lint format typecheck test check-toolchain check-quant-runtime check-quant-data check-quant-research check-quant-nautilus check-quant-hft check-quant-hummingbot-api check-contracts check-doc-consistency check-hooks check-shell check-hygiene check-secrets check-cd check-required check-foundation

help:
	@printf '%s\n' \
		'Targets:' \
		'  make sync                  Install locked dev dependencies' \
		'  make sync-data             Install locked data dependencies' \
		'  make sync-crypto           Install locked crypto data dependencies' \
		'  make sync-research         Install locked research dependencies' \
		'  make sync-screening        Install locked screening dependencies' \
		'  make sync-baseline         Install locked baseline engine dependencies' \
		'  make sync-nautilus         Install locked NautilusTrader dependencies' \
		'  make sync-hft              Install locked HFT dependencies' \
		'  make sync-hummingbot-api   Install locked Hummingbot API-boundary dependencies' \
		'  make sync-monitoring       Install locked monitoring dependencies' \
		'  make sync-notebooks        Install locked notebook dependencies' \
		'  make sync-performance      Install locked profiling dependencies' \
		'  make sync-reporting        Install locked reporting dependencies' \
		'  make doctor                Inspect local dev environment without changing it' \
		'  make lint                  Run ruff' \
		'  make format                Format supported files with ruff' \
		'  make typecheck             Run mypy' \
		'  make test                  Run pytest' \
		'  make check-toolchain       Report local toolchain versions' \
		'  make check-quant-runtime   Smoke import runtime CLI/config packages' \
		'  make check-quant-data      Smoke import data and crypto data packages' \
		'  make check-quant-research  Smoke import research packages' \
		'  make check-quant-nautilus  Smoke import NautilusTrader package' \
		'  make check-quant-hft       Smoke import HftBacktest package' \
		'  make check-quant-hummingbot-api Smoke import Hummingbot API-boundary package' \
		'  make check-contracts       Run contract model tests' \
		'  make check-doc-consistency Run doc consistency tests' \
		'  make check-hooks           Run shell syntax checks on hooks/scripts' \
		'  make check-shell           Run ShellCheck on tracked shell hooks/scripts' \
		'  make check-hygiene         Run repo hygiene guardrails' \
		'  make check-secrets         Run Gitleaks with redacted output' \
		'  make check-required        Run required local checks' \
		'  make check-cd              Run deployment-readiness guard' \
		'  make check-foundation      Run the Foundation Robustness Gate'

sync:
	$(UV) sync --frozen --group dev

sync-data:
	$(UV) sync --frozen --group dev --group data

sync-crypto:
	$(UV) sync --frozen --group dev --group crypto-data

sync-research:
	$(UV) sync --frozen --group dev --group research

sync-screening:
	$(UV) sync --frozen --group dev --group screening

sync-baseline:
	$(UV) sync --frozen --group dev --group baseline

sync-nautilus:
	$(UV) sync --frozen --group dev --group nautilus

sync-hft:
	$(UV) sync --frozen --group dev --group hft

sync-hummingbot-api:
	$(UV) sync --frozen --group dev --group hummingbot-api

sync-monitoring:
	$(UV) sync --frozen --group dev --group monitoring

sync-notebooks:
	$(UV) sync --frozen --group dev --group notebooks

sync-performance:
	$(UV) sync --frozen --group dev --group performance

sync-reporting:
	$(UV) sync --frozen --group dev --group reporting

doctor:
	sh scripts/check-dev-environment.sh

lint:
	$(UV) run ruff check .

format:
	$(UV) run ruff format .

typecheck:
	$(UV) run mypy

test:
	$(UV) run pytest

check-toolchain:
	@git --version | sed 's/^/ok: /'
	@$(UV) --version | sed 's/^/ok: /'
	@python3 --version | sed 's/^/ok: /'
	@shellcheck --version | sed -n 's/^version: /ok: shellcheck /p' | head -n 1
	@gitleaks version | sed 's/^/ok: gitleaks /'

check-quant-runtime:
	$(UV) run --frozen --group dev python -c "import pydantic, pydantic_settings, rich, typer; print('quant runtime imports: passed')"

check-quant-data:
	$(UV) run --frozen --group crypto-data python -c "import aiohttp, ccxt, duckdb, numpy, orjson, pandas, pandera, polars, pyarrow, websockets; print('quant data imports: passed')"

check-quant-research:
	$(UV) run --frozen --group research python -c "import cvxpy, mlflow, optuna, scipy, sklearn, statsmodels; print('quant research imports: passed')"

check-quant-nautilus:
	$(UV) run --frozen --group nautilus python -c "import nautilus_trader; print('nautilus import: passed')"

check-quant-hft:
	$(UV) run --frozen --group hft python -c "import hftbacktest; print('hftbacktest import: passed')"

check-quant-hummingbot-api:
	$(UV) run --frozen --group hummingbot-api python -c "import httpx; print('hummingbot api boundary imports: passed')"

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

check-hygiene:
	sh scripts/check-repo-hygiene.sh

check-secrets:
	sh scripts/check-secrets.sh

check-cd:
	$(UV) run pytest tests/test_foundation_integrity.py -k cd_readiness

check-required: lint typecheck check-hooks check-shell check-hygiene check-secrets test

check-foundation: check-toolchain check-required check-cd
