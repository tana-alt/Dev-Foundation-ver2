from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from workflow_core.contract_harness.domain.capabilities import (
    ROLE_CAPABILITIES,
    Capability,
    Session,
)
from workflow_core.contract_harness.ports.state_store import StateStore


class CapabilityError(RuntimeError):
    code = "unauthorized"


class UnauthorizedError(CapabilityError):
    code = "unauthorized"


class ForbiddenError(CapabilityError):
    code = "forbidden"


class CapabilityService:
    def __init__(self, store: StateStore) -> None:
        self.store = store

    def create_session(
        self,
        *,
        role: str,
        agent_id: str,
        task_id: str | None,
        expires_at: str | None = None,
    ) -> tuple[Session, str]:
        if role not in ROLE_CAPABILITIES:
            raise ValueError(f"unknown role: {role}")
        session_id = f"sess_{uuid4().hex}"
        token = f"ftok_{secrets.token_urlsafe(32)}"
        created_at = _utc_now()
        capabilities = sorted(cap.value for cap in ROLE_CAPABILITIES[role])
        self.store.create_session(
            session_id=session_id,
            task_id=task_id,
            role=role,
            agent_id=agent_id,
            capabilities=capabilities,
            token_hash=hash_token(token),
            created_at=created_at,
            expires_at=expires_at,
        )
        session = Session(
            session_id=session_id,
            task_id=task_id,
            role=role,
            agent_id=agent_id,
            capabilities=[Capability(item) for item in capabilities],
            token_hash=hash_token(token),
            created_at=created_at,
            expires_at=expires_at,
        )
        return session, token

    def authorize(
        self,
        *,
        session_id: str | None,
        token: str | None,
        required: Capability,
    ) -> Session:
        session = self.authenticate(session_id=session_id, token=token)
        if Capability.ADMIN not in session.capabilities and required not in session.capabilities:
            raise ForbiddenError(f"session lacks capability: {required.value}")
        return session

    def authenticate(self, *, session_id: str | None, token: str | None) -> Session:
        if not session_id or not token:
            raise UnauthorizedError("session_id and capability_token are required")
        row = self.store.get_session(session_id)
        if row is None:
            raise UnauthorizedError("unknown session")
        session = _session_from_row(row)
        if session.status != "active":
            raise UnauthorizedError(f"session is {session.status}")
        if session.expires_at and session.expires_at <= _utc_now():
            raise UnauthorizedError("session is expired")
        if session.token_hash != hash_token(token):
            raise UnauthorizedError("invalid capability token")
        return session

    def revoke_session(self, session_id: str) -> bool:
        return self.store.revoke_session(session_id)

    def list_sessions(self) -> list[dict[str, Any]]:
        return [
            {key: value for key, value in row.items() if key != "token_hash"}
            for row in self.store.list_sessions()
        ]


def hash_token(token: str) -> str:
    return "sha256:" + hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_actor(session: Session | None) -> str:
    if session is None:
        return "daemon"
    return f"{session.role}:{session.agent_id}"


def _session_from_row(row: dict[str, Any]) -> Session:
    return Session(
        session_id=str(row["session_id"]),
        task_id=str(row["task_id"]) if row.get("task_id") is not None else None,
        role=str(row["role"]),
        agent_id=str(row["agent_id"]),
        capabilities=[Capability(str(item)) for item in row.get("capabilities", [])],
        token_hash=str(row["token_hash"]),
        status=str(row["status"]),
        created_at=str(row["created_at"]),
        expires_at=str(row["expires_at"]) if row.get("expires_at") is not None else None,
    )


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
