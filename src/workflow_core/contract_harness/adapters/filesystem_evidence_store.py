from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from workflow_core.contract_harness.domain.models import ArtifactRef, StrictModel
from workflow_core.contract_harness.hashing import canonical_json, sha256_bytes


class FilesystemEvidenceStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def put_bytes(self, data: bytes, media_type: str) -> ArtifactRef:
        sha256 = sha256_bytes(data)
        path = self.path_for(sha256)
        if not path.is_file():
            self._write_atomic(path, data)
        return ArtifactRef(
            sha256=sha256,
            media_type=media_type,
            size_bytes=len(data),
            storage_uri=str(path),
        )

    def put_json(
        self,
        data: StrictModel | dict[str, Any],
        media_type: str = "application/json",
    ) -> ArtifactRef:
        payload = data.model_dump(mode="json") if isinstance(data, StrictModel) else data
        return self.put_bytes(canonical_json(payload).encode("utf-8"), media_type)

    def get_bytes(self, sha256: str) -> bytes:
        return self.path_for(sha256).read_bytes()

    def get_json(self, sha256: str) -> dict[str, Any]:
        data = json.loads(self.get_bytes(sha256).decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("evidence object must be a JSON object")
        return data

    def exists(self, sha256: str) -> bool:
        return self.path_for(sha256).is_file()

    def path_for(self, sha256: str) -> Path:
        hex_digest = _hex_digest(sha256)
        return self.root / hex_digest[:2] / hex_digest

    def _write_atomic(self, path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.parent / f".{path.name}.tmp.{os.getpid()}"
        with tmp.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _hex_digest(sha256: str) -> str:
    return sha256.removeprefix("sha256:")
