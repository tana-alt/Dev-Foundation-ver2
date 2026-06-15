from __future__ import annotations

from pathlib import Path

from workflow_core.plans import active_plan_ids, plan_files, plan_gated

INDEX = """\
project_id: demo
plans:
  - plan_id: Plan_N0001
    status: completed
    plan_ref: Plan/demo/plans/Plan_N0001.md
    log_ref: Plan/demo/logs/Plan_N0001.log.md
  - plan_id: Plan_N0002
    status: active
    plan_ref: Plan/demo/plans/Plan_N0002.md
    log_ref: Plan/demo/logs/Plan_N0002.log.md
"""


def write_plan(root: Path, project: str, name: str) -> None:
    plans_dir = root / "Plan" / project / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    (plans_dir / name).write_text("# plan\n", encoding="utf-8")


def test_plan_files_filters_and_sorts(tmp_path: Path) -> None:
    write_plan(tmp_path, "demo", "Plan_N0002.md")
    write_plan(tmp_path, "demo", "Plan_N0001.md")
    write_plan(tmp_path, "demo", "notes.md")
    assert [p.name for p in plan_files(tmp_path, "demo")] == ["Plan_N0001.md", "Plan_N0002.md"]


def test_active_plan_ids_pairs_id_with_status() -> None:
    assert active_plan_ids(INDEX) == ["Plan_N0002"]


def test_gated_when_index_marks_existing_plan_active(tmp_path: Path) -> None:
    write_plan(tmp_path, "demo", "Plan_N0001.md")
    write_plan(tmp_path, "demo", "Plan_N0002.md")
    (tmp_path / "Plan" / "demo" / "index.yaml").write_text(INDEX, encoding="utf-8")
    assert plan_gated(tmp_path, "demo")


def test_not_gated_when_all_plans_inactive(tmp_path: Path) -> None:
    write_plan(tmp_path, "demo", "Plan_N0001.md")
    index = INDEX.replace("status: active", "status: completed")
    (tmp_path / "Plan" / "demo" / "index.yaml").write_text(index, encoding="utf-8")
    assert not plan_gated(tmp_path, "demo")


def test_gated_when_plan_file_exists_without_index(tmp_path: Path) -> None:
    write_plan(tmp_path, "demo", "Plan_N0001.md")
    assert plan_gated(tmp_path, "demo")


def test_not_gated_without_plan_files(tmp_path: Path) -> None:
    assert not plan_gated(tmp_path, "demo")
    (tmp_path / "Plan" / "demo" / "plans").mkdir(parents=True)
    assert not plan_gated(tmp_path, "demo")
