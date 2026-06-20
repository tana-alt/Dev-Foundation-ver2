from __future__ import annotations

import json
from pathlib import Path

from .conftest import TASK_ID, load_runtime_json, run_harness, runtime_task_dir


def test_status_projection_does_not_treat_scope_map_as_authority(harness_repo: Path) -> None:
    assert run_harness(harness_repo, "prepare", TASK_ID).returncode == 0
    assert run_harness(harness_repo, "scope-map", TASK_ID, "--forward").returncode == 0

    status = run_harness(harness_repo, "status", TASK_ID)

    assert status.returncode == 0, status.stdout + status.stderr
    result = json.loads(status.stdout)
    assert result["phase"] == "prepared"
    assert "scope-map-forward.json" not in result["artifacts"]["present"]
    assert result["state_store"]["integrity"] == "pass"


def test_comm_done_message_does_not_complete_task(harness_repo: Path) -> None:
    runtime = runtime_task_dir(harness_repo)
    comm = runtime / "comm" / "sessions"
    comm.mkdir(parents=True)
    (comm / "agent.json").write_text(
        json.dumps({"message": "完了しました。LGTM。", "authoritative": False}),
        encoding="utf-8",
    )

    assert run_harness(harness_repo, "prepare", TASK_ID).returncode == 0
    status = run_harness(harness_repo, "status", TASK_ID)

    assert status.returncode == 0, status.stdout + status.stderr
    result = json.loads(status.stdout)
    assert result["phase"] == "prepared"
    assert result["authority"]["complete"] is False


def test_prepare_binds_contract_to_state_store_and_evidence(harness_repo: Path) -> None:
    prepared = run_harness(harness_repo, "prepare", TASK_ID)

    assert prepared.returncode == 0, prepared.stdout + prepared.stderr
    status = run_harness(harness_repo, "status", TASK_ID)
    result = json.loads(status.stdout)
    manifest = load_runtime_json(harness_repo, "authority-manifest.json")
    assert result["state_store"]["current_phase"] == "prepared"
    assert manifest["authority_artifacts"]["contract.lock.json"]["sha256"].startswith("sha256:")


def test_pushed_json_without_complete_state_event_is_not_complete(harness_repo: Path) -> None:
    assert run_harness(harness_repo, "prepare", TASK_ID).returncode == 0
    runtime = runtime_task_dir(harness_repo)
    (runtime / "push-result.json").write_text(
        json.dumps(
            {
                "task_id": TASK_ID,
                "status": "pushed",
                "reason": "ok",
                "landed_commit": "0" * 40,
                "remote_sha_after": "0" * 40,
            }
        ),
        encoding="utf-8",
    )

    status = run_harness(harness_repo, "status", TASK_ID)

    assert status.returncode == 0, status.stdout + status.stderr
    result = json.loads(status.stdout)
    assert result["authority"] == {
        "complete": False,
        "source": "push-result.json status=pushed without StateStore COMPLETE event",
    }
