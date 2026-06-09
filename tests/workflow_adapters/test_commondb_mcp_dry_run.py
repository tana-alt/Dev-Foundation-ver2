from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.workflow_adapters.commondb_context_adapter import (
    ContextValidationError,
    validate_context_result,
)

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "commondb-mcp-dry-run.py"
ENABLE_SCRIPT = ROOT / "scripts" / "enable-commondb-mcp-local.sh"
E2E_SCRIPT = ROOT / "scripts" / "check-personal-workflow-app-e2e.sh"


def run_dry_run(config: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--config", str(config), "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def run_enable(config: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", str(ENABLE_SCRIPT), "--config", str(config), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_dry_run_accepts_placeholder_config_and_emits_sanitized_status() -> None:
    result = run_dry_run(ROOT / "templates" / "codex-config.toml.example")

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "passed"
    assert payload["live_mcp"] == "not_used"
    assert payload["qdrant"] == "out_of_scope"
    assert "raw_source" not in result.stdout
    assert "/Users/" not in result.stdout


def test_dry_run_blocks_missing_commondb_search_config(tmp_path: Path) -> None:
    config = tmp_path / "codex-config.toml"
    config.write_text(
        '[mcp_servers.serena]\ncommand = "serena"\nargs = ["start-mcp-server"]\n',
        encoding="utf-8",
    )

    result = run_dry_run(config)

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert payload["message"] == "commondb.search dry_run block missing"


def test_e2e_rejects_public_codex_urls(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    result = subprocess.run(
        ["sh", str(E2E_SCRIPT), "--dry-run", "--config", str(config)],
        cwd=ROOT,
        env={**os.environ, "PERSONAL_WORKFLOW_CODEX_URL": "https://example.com/codex?token=raw"},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 66
    assert result.stdout.strip() == "codex_link_status=blocked"


def test_enable_local_helper_appends_safe_dry_run_block(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text('[mcp_servers.serena]\ncommand = "serena"\n', encoding="utf-8")

    dry_run = run_enable(config, "--dry-run")
    assert dry_run.returncode == 0
    assert "status=would_append" in dry_run.stdout
    assert "commondb.search" not in dry_run.stdout
    assert run_dry_run(config).returncode == 1

    applied = run_enable(config, "--apply")
    assert applied.returncode == 0
    assert "status=appended" in applied.stdout
    assert "backup=" in applied.stdout
    assert run_dry_run(config).returncode == 0

    verified = run_enable(config, "--dry-run")
    assert verified.returncode == 0
    assert "status=already_present" in verified.stdout


def test_enable_local_helper_blocks_live_existing_block(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        '[mcp_servers."commondb.search"]\n'
        'command = "python3"\n'
        'args = ["live-search.py"]\n'
        "dry_run = false\n",
        encoding="utf-8",
    )

    result = run_enable(config, "--apply")

    assert result.returncode == 1
    assert "status=blocked" in result.stdout
    assert "existing_commondb_search_block_is_not_dry_run_only" in result.stdout


def test_adapter_rejects_fake_risk_payload_before_consumption() -> None:
    unsafe_result = {
        "schema_version": "0.1",
        "record_type": "context_result",
        "result_id": "commondb-dry-run-risk-001",
        "request_id": "commondb-dry-run-request-001",
        "status": "ok",
        "source_refs": ["commondb:dry-run:fake-risk"],
        "snippets": [
            {
                "source_ref": "commondb:dry-run:fake-risk",
                "relevance": "Fake unsafe payload.",
                "text": "raw_source: fake non-secret payload should be blocked",
            }
        ],
        "error": {"code": None, "message": None},
    }

    with pytest.raises(ContextValidationError, match="forbidden boundary marker"):
        validate_context_result(unsafe_result)
