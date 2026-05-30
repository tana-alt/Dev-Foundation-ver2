import os
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).resolve().parents[1]


def lane_map_template() -> dict[str, Any]:
    raw = yaml.safe_load((ROOT / "templates/parallel-lane-map.yaml").read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return cast(dict[str, Any], raw)


def write_actual_lane_map(tmp_path: Path, data: dict[str, Any]) -> Path:
    identity = cast(dict[str, Any], data["identity"])
    project_id = cast(str, identity["project_id"])
    work_id = cast(str, identity["work_id"])
    path = tmp_path / "Plan" / project_id / "lane-maps" / f"{work_id}.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def valid_actual_lane_map() -> dict[str, Any]:
    data = lane_map_template()
    data["status"] = "active"
    data["identity"] = {
        "work_id": "foundation-lane-map-ci",
        "project_id": "foundation",
        "created_at": "2026-05-30",
    }
    data["governance"]["map_owner"] = "agent"
    data["handoff"]["next_action"] = "review"

    lanes = cast(list[dict[str, Any]], data["lanes"])
    lanes[0]["owner"] = "unassigned"
    lanes[0]["branch_target"] = "agent/foundation-lane-map-ci/docs/lane-map-docs"
    lanes[0]["worktree_target"] = "../worktrees/foundation/foundation-lane-map-ci-docs"
    lanes[1]["owner"] = "unassigned"
    lanes[1]["branch_target"] = "agent/foundation-lane-map-ci/verification/lane-map-tests"
    lanes[1]["worktree_target"] = "../worktrees/foundation/foundation-lane-map-ci-verification"
    return data


def run_lane_check(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/check-lane-map.py")],
        cwd=ROOT,
        env={**os.environ, "FOUNDATION_REPO_ROOT": str(tmp_path)},
        check=False,
        capture_output=True,
        text=True,
    )


def test_check_lane_map_accepts_valid_plan_lane_map(tmp_path: Path) -> None:
    write_actual_lane_map(tmp_path, valid_actual_lane_map())

    result = run_lane_check(tmp_path)

    assert result.returncode == 0
    assert "lane map check: passed" in result.stdout


def test_check_lane_map_rejects_branch_target_with_extra_segments(tmp_path: Path) -> None:
    data = valid_actual_lane_map()
    lanes = cast(list[dict[str, Any]], data["lanes"])
    lanes[0]["branch_target"] = "agent/foundation-lane-map-ci/docs/lane-map-docs/extra"
    write_actual_lane_map(tmp_path, data)

    result = run_lane_check(tmp_path)

    assert result.returncode == 1
    assert "branch_target must be agent/<work_id>/<lane>/<slug>" in result.stderr


def test_check_lane_map_rejects_placeholders_in_plan_lane_map(tmp_path: Path) -> None:
    data = valid_actual_lane_map()
    lanes = cast(list[dict[str, Any]], data["lanes"])
    lanes[0]["branch_target"] = "agent/foundation-lane-map-ci/docs/<short-slug>"
    write_actual_lane_map(tmp_path, data)

    result = run_lane_check(tmp_path)

    assert result.returncode == 1
    assert "must not contain template placeholders in Plan lane maps" in result.stderr


def test_check_lane_map_rejects_plan_project_id_mismatch(tmp_path: Path) -> None:
    data = valid_actual_lane_map()
    path = tmp_path / "Plan" / "other-project" / "lane-maps" / "foundation-lane-map-ci.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    result = run_lane_check(tmp_path)

    assert result.returncode == 1
    assert "identity.project_id must match Plan path project_id: other-project" in result.stderr


def test_check_lane_map_allows_same_lane_overlapping_targets(tmp_path: Path) -> None:
    data = valid_actual_lane_map()
    lanes = cast(list[dict[str, Any]], data["lanes"])
    lanes[0]["allowed_write_targets"] = ["docs/", "docs/reference/"]
    lanes[1]["allowed_write_targets"] = ["tests/"]
    write_actual_lane_map(tmp_path, data)

    result = run_lane_check(tmp_path)

    assert result.returncode == 0
