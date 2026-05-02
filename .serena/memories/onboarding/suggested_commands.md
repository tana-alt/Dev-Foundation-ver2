# Suggested Commands
- `uv run ruff check .`
- `uv run mypy apps src tests`
- `uv run pytest`
- `uv run python -m src.services.verification.cli architecture`
- `uv run python -m src.services.verification.cli doc-freshness`
- `uv run python -m src.services.verification.cli dangerous-diff`
- App entrypoint is FastAPI under `apps/api/main.py`; frontend lives in `apps/web`.
