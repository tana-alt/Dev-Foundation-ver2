from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def hash_json(data: Any) -> str:
    return sha256_text(canonical_json(data))


def file_hash(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def directory_hash(path: Path) -> str:
    if not path.exists():
        return hash_json([])
    entries = [
        {"path": str(file.relative_to(path)).replace("\\", "/"), "sha256": file_hash(file)}
        for file in sorted(path.rglob("*"))
        if file.is_file()
    ]
    return hash_json(entries)
