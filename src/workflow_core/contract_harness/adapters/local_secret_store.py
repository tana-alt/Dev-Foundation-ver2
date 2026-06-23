from __future__ import annotations

import secrets
from pathlib import Path


class LocalSecretStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def get_or_create_token(self, name: str, *, prefix: str) -> str:
        path = self.root / name
        if path.is_file():
            return path.read_text(encoding="utf-8").strip()
        token = f"{prefix}_{secrets.token_urlsafe(32)}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(token + "\n", encoding="utf-8")
        path.chmod(0o600)
        return token
