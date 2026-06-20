from __future__ import annotations

from typing import Any, Protocol

from workflow_core.contract_harness.domain.models import ArtifactRef, StateEvent, WorkflowPhase


class StateStore(Protocol):
    def append_event(
        self,
        *,
        task_id: str,
        candidate_id: str | None,
        event_type: str,
        from_phase: WorkflowPhase | str | None,
        to_phase: WorkflowPhase | str,
        payload: dict[str, Any],
        actor: str,
    ) -> StateEvent: ...

    def record_artifact(
        self,
        *,
        task_id: str,
        artifact_type: str,
        ref: ArtifactRef,
        compatibility_path: str | None = None,
    ) -> None: ...

    def current_phase(self, task_id: str) -> WorkflowPhase | None: ...

    def current_event_sha256(self, task_id: str) -> str | None: ...

    def verify_integrity(self) -> dict[str, Any]: ...

    def create_session(
        self,
        *,
        session_id: str,
        task_id: str | None,
        role: str,
        agent_id: str,
        capabilities: list[str],
        token_hash: str,
        created_at: str,
        expires_at: str | None,
    ) -> None: ...

    def get_session(self, session_id: str) -> dict[str, Any] | None: ...

    def list_sessions(self) -> list[dict[str, Any]]: ...

    def revoke_session(self, session_id: str) -> bool: ...

    def request_effect(
        self,
        *,
        effect_type: str,
        task_id: str,
        candidate_id: str | None,
        idempotency_key: str,
        payload: dict[str, Any],
        requested_event_sha256: str | None,
    ) -> dict[str, Any]: ...

    def get_effect(self, effect_id: str) -> dict[str, Any] | None: ...

    def get_effect_by_idempotency_key(self, idempotency_key: str) -> dict[str, Any] | None: ...

    def update_effect(
        self,
        effect_id: str,
        *,
        status: str,
        external_ref: str | None = None,
        observed_hash: str | None = None,
        result_event_sha256: str | None = None,
        last_error: str | None = None,
        increment_attempt: bool = False,
    ) -> dict[str, Any]: ...

    def list_effects(self, statuses: list[str] | None = None) -> list[dict[str, Any]]: ...
