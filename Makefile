UV ?= uv

.PHONY: sync lint format typecheck test check-contracts check-cd check-required

sync:
	$(UV) sync --frozen --group dev

lint:
	$(UV) run ruff check .

format:
	$(UV) run ruff format .

typecheck:
	$(UV) run mypy

test:
	$(UV) run pytest

check-contracts:
	$(UV) run pytest tests/test_contract_models.py

check-cd:
	$(UV) run pytest tests/test_foundation_integrity.py -k cd_readiness

check-required: lint typecheck test
