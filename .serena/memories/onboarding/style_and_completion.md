# Style and Completion
- Python 3.12, strict typing, Ruff formatting with 100-char line length, double quotes, spaces, and strict mypy.
- Prefer small changes, no unrelated refactors, preserve canonical schemas and doc boundaries, and avoid destructive git operations.
- Completion checks commonly used in this repo: `uv run ruff check .`, `uv run mypy apps src tests`, `uv run pytest`, `uv run python -m src.services.verification.cli architecture`, `uv run python -m src.services.verification.cli doc-freshness`, `uv run python -m src.services.verification.cli dangerous-diff`.
