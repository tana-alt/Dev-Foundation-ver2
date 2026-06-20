from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow_core.contract_harness.application.pr_service import check_local_pr, create_local_pr
from workflow_core.contract_harness.application.services import state_store
from workflow_core.contract_harness.domain.models import WorkflowPhase
from workflow_core.contract_harness.hashing import file_hash
from workflow_core.contract_harness.land import land_task
from workflow_core.contract_harness.ports.state_store import StateStore
from workflow_core.contract_harness.push import push_task
from workflow_core.contract_harness.runtime_paths import task_dir

PENDING_STATUSES = ["requested", "running", "needs_reconcile"]


class OutboxService:
    def __init__(self, root: Path, store: StateStore) -> None:
        self.root = root
        self.store = store

    def request_effect(
        self,
        *,
        effect_type: str,
        task_id: str,
        candidate_id: str | None,
        idempotency_key: str,
        payload: dict[str, Any],
        requested_event_sha256: str | None,
    ) -> dict[str, Any]:
        effect = self.store.request_effect(
            effect_type=effect_type,
            task_id=task_id,
            candidate_id=candidate_id,
            idempotency_key=idempotency_key,
            payload=payload,
            requested_event_sha256=requested_event_sha256,
        )
        if effect["status"] == "succeeded":
            return {"status": "reused", "effect": effect}
        return self.run_effect(str(effect["effect_id"]))

    def run_effect(self, effect_id: str) -> dict[str, Any]:
        effect = self.store.get_effect(effect_id)
        if effect is None:
            raise ValueError(f"effect not found: {effect_id}")
        if effect["status"] == "succeeded":
            return {"status": "reused", "effect": effect}
        observed = self._observe_existing(effect)
        if observed is not None:
            updated = self.store.update_effect(
                effect_id,
                status="succeeded",
                external_ref=_external_ref(observed),
                observed_hash=_observed_hash(observed),
                result_event_sha256=_current_event_sha(self.store, str(effect["task_id"])),
                last_error=None,
            )
            return {
                "status": "succeeded",
                "effect": updated,
                "result": observed,
                "exit_code": 0,
                "recovered": True,
            }
        self.store.update_effect(effect_id, status="running", increment_attempt=True)
        try:
            result, exit_code = self._execute(effect)
        except Exception as exc:
            failed = self.store.update_effect(
                effect_id,
                status="failed",
                last_error=str(exc),
            )
            return {"status": "failed", "effect": failed, "error": str(exc), "exit_code": 1}
        status = "succeeded" if exit_code == 0 else "failed"
        updated = self.store.update_effect(
            effect_id,
            status=status,
            external_ref=_external_ref(result),
            observed_hash=_observed_hash(result),
            result_event_sha256=_current_event_sha(self.store, str(effect["task_id"])),
            last_error=None if exit_code == 0 else str(result.get("reason") or "effect_failed"),
        )
        return {
            "status": status,
            "effect": updated,
            "result": result,
            "exit_code": exit_code,
        }

    def resume(self) -> dict[str, Any]:
        effects = self.store.list_effects(PENDING_STATUSES)
        results = [self.run_effect(str(effect["effect_id"])) for effect in effects]
        return {
            "resumed": len(results),
            "results": results,
        }

    def status(self) -> dict[str, Any]:
        return {
            "effects": self.store.list_effects(
                ["requested", "running", "failed", "needs_reconcile"]
            )
        }

    def _execute(self, effect: dict[str, Any]) -> tuple[dict[str, Any], int]:
        effect_type = str(effect["effect_type"])
        task_id = str(effect["task_id"])
        if effect_type == "create_pr":
            return create_local_pr(self.root, task_id)
        if effect_type == "pr_checks":
            return check_local_pr(self.root, task_id)
        if effect_type == "merge_local":
            return land_task(self.root, task_id)
        if effect_type == "complete_task":
            return complete_local_task(self.root, task_id)
        if effect_type == "push_remote":
            return push_task(self.root, task_id)
        raise ValueError(f"unknown effect_type: {effect_type}")

    def _observe_existing(self, effect: dict[str, Any]) -> dict[str, Any] | None:
        task_id = str(effect["task_id"])
        effect_type = str(effect["effect_type"])
        candidates = {
            "create_pr": "pr-result.json",
            "pr_checks": "pr-check-result.json",
            "merge_local": "land-result.json",
            "complete_task": "completion-result.json",
            "push_remote": "push-result.json",
        }
        name = candidates.get(effect_type)
        if name is None:
            return None
        path = task_dir(self.root, task_id) / name
        if not path.is_file():
            return None
        result = _read_json(path)
        if _is_successful_observation(effect, result):
            return result
        return None


def complete_local_task(root: Path, task_id: str) -> tuple[dict[str, Any], int]:
    land_path = task_dir(root, task_id) / "land-result.json"
    land_result = _read_json(land_path)
    if land_result.get("status") != "landed":
        return {
            "task_id": task_id,
            "status": "blocked",
            "reason": "land_not_landed",
            "complete": False,
        }, 1
    store = state_store(root)
    land_event = store.latest_event(task_id, event_type="LAND")
    if land_event is None:
        return _blocked_complete(task_id, "land_event_missing"), 1
    land_payload = _read_payload(land_event.payload_json)
    if land_payload.get("status") != "landed":
        return _blocked_complete(task_id, "land_event_not_landed"), 1
    artifact_sha = land_payload.get("artifact_sha256")
    if artifact_sha and file_hash(land_path) != artifact_sha:
        return _blocked_complete(task_id, "land_artifact_hash_mismatch"), 1
    if land_payload.get("landed_commit") != land_result.get("landed_commit"):
        return _blocked_complete(task_id, "land_event_commit_mismatch"), 1
    candidate_sha = str(land_result.get("candidate_diff_sha256") or "")
    landed_commit = str(land_result.get("landed_commit") or "")
    if not landed_commit:
        return {
            "task_id": task_id,
            "status": "blocked",
            "reason": "landed_commit_missing",
            "complete": False,
        }, 1
    if not _commit_exists(root, landed_commit):
        return _blocked_complete(task_id, "landed_commit_missing_in_git"), 1
    current = store.current_phase(task_id)
    event = store.append_event(
        task_id=task_id,
        candidate_id=str(land_result.get("candidate_id") or "") or None,
        event_type="COMPLETE",
        from_phase=current,
        to_phase=WorkflowPhase.COMPLETE,
        payload={
            "candidate_diff_sha256": candidate_sha,
            "landed_commit": landed_commit,
            "merge_commit_sha": landed_commit,
        },
        actor=_actor(),
    )
    result = {
        "schema_version": 1,
        "task_id": task_id,
        "status": "complete",
        "complete": True,
        "candidate_diff_sha256": candidate_sha,
        "landed_commit": landed_commit,
        "merge_commit_sha": landed_commit,
        "state_event_sha256": event.event_sha256,
        "written_by": "harness",
    }
    _write_json(task_dir(root, task_id) / "completion-result.json", result)
    return result, 0


def _current_event_sha(store: StateStore, task_id: str) -> str | None:
    current = getattr(store, "current_event_sha256", None)
    if not callable(current):
        return None
    value = current(task_id)
    return str(value) if value is not None else None


def _external_ref(result: dict[str, Any]) -> str | None:
    for key in ("ref", "landed_commit", "merge_commit_sha", "state_event_sha256"):
        value = result.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _observed_hash(result: dict[str, Any]) -> str | None:
    for key in ("head_sha", "diff_sha256", "landed_commit", "merge_commit_sha"):
        value = result.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _blocked_complete(task_id: str, reason: str) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "status": "blocked",
        "reason": reason,
        "complete": False,
    }


def _read_payload(payload_json: str) -> dict[str, Any]:
    import json

    data = json.loads(payload_json)
    if not isinstance(data, dict):
        raise ValueError("state event payload must be an object")
    return data


def _commit_exists(root: Path, sha: str) -> bool:
    from workflow_core.contract_harness.gitutil import git

    if not sha or set(sha) == {"0"}:
        return False
    return git(root, ["cat-file", "-e", f"{sha}^{{commit}}"], check=False).returncode == 0


def _is_successful_observation(effect: dict[str, Any], result: dict[str, Any]) -> bool:
    effect_type = str(effect["effect_type"])
    if result.get("task_id") != effect.get("task_id"):
        return False
    candidate_id = effect.get("candidate_id")
    if candidate_id and result.get("candidate_id") != candidate_id:
        return False
    if effect_type == "create_pr":
        return (
            result.get("status") == "created"
            and isinstance(result.get("ref"), str)
            and isinstance(result.get("head_sha"), str)
        )
    if effect_type == "pr_checks":
        return result.get("status") == "pass" and isinstance(result.get("head_sha"), str)
    if effect_type == "merge_local":
        return result.get("status") == "landed" and isinstance(result.get("landed_commit"), str)
    if effect_type == "complete_task":
        return result.get("complete") is True and isinstance(result.get("state_event_sha256"), str)
    if effect_type == "push_remote":
        return result.get("status") == "pushed" and isinstance(result.get("remote_sha_after"), str)
    return False


def _read_json(path: Path) -> dict[str, Any]:
    from workflow_core.contract_harness.jsonio import read_json

    return read_json(path)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    from workflow_core.contract_harness.jsonio import write_json

    write_json(path, data)


def _actor() -> str:
    import os

    return os.environ.get("HARNESS_ACTOR") or "harness"
