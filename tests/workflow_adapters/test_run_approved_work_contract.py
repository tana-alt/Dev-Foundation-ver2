import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_runner_script_writes_mock_execution_record(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifact"
    command = [
        sys.executable,
        str(ROOT / "scripts" / "run-approved-work-contract.py"),
        str(ROOT / "artifact" / "demo-codex-sdk-run" / "approved-work-contract.yaml"),
        "--config",
        str(ROOT / "templates" / "codex-sdk-run-config.yaml"),
        "--artifact-dir",
        str(artifact_dir),
    ]

    completed = subprocess.run(
        command,
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    output_path = Path(completed.stdout.strip())
    assert output_path.is_file()
    record = yaml.safe_load(output_path.read_text(encoding="utf-8"))
    assert record["record_type"] == "codex_sdk_execution_run"
    assert record["status"] == "completed"
    assert record["runner"]["mode"] == "mock"
    assert record["outputs"]["artifact_dir"] == artifact_dir.as_posix()
