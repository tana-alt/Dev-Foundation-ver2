from __future__ import annotations

from typing import Any, Protocol

from workflow_core.contract_harness.domain.models import ArtifactRef, StrictModel


class EvidenceStore(Protocol):
    def put_bytes(self, data: bytes, media_type: str) -> ArtifactRef: ...

    def put_json(
        self,
        data: StrictModel | dict[str, Any],
        media_type: str = "application/json",
    ) -> ArtifactRef: ...

    def get_bytes(self, sha256: str) -> bytes: ...

    def get_json(self, sha256: str) -> dict[str, Any]: ...

    def exists(self, sha256: str) -> bool: ...
