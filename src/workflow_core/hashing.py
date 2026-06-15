"""Canonical-JSON hashing shared by the AB evaluation pipeline.

config_hash, policy_hash, and env_fingerprint (Plan-N0002 R1/R12/R13) must be
reproducible across processes, so they all hash the same canonical form:
sorted keys, compact separators, UTF-8.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def canonical_json(data: Any) -> str:
    """Serialize to the canonical form used for every pipeline hash."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_hash(data: Any) -> str:
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
