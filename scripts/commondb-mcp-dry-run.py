#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.workflow_adapters.commondb_context_adapter import (  # noqa: E402
    ContextValidationError,
    validate_context_result,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local CommonDB MCP dry_run safety.")
    parser.add_argument("--config", required=True, help="Codex config TOML target to inspect.")
    parser.add_argument("--json", action="store_true", help="Emit sanitized JSON.")
    args = parser.parse_args()

    config_path = Path(args.config).expanduser()
    checks: list[dict[str, str]] = []

    if not config_path.exists() or not config_path.is_file():
        return emit(args.json, "blocked", checks, f"config target unavailable: {config_path.name}")

    with config_path.open("rb") as handle:
        config = tomllib.load(handle)

    commondb = config.get("mcp_servers", {}).get("commondb.search")
    if not isinstance(commondb, dict):
        return emit(args.json, "blocked", checks, "commondb.search dry_run block missing")

    if commondb.get("dry_run") is not True:
        return emit(args.json, "blocked", checks, "commondb.search dry_run must be true")

    checks.append({"name": "config_target", "result": "passed"})
    checks.append({"name": "dry_run_only", "result": "passed"})

    fake_unsafe_result: dict[str, Any] = {
        "schema_version": "0.1",
        "record_type": "context_result",
        "result_id": "commondb-dry-run-risk-001",
        "request_id": "commondb-dry-run-request-001",
        "status": "ok",
        "source_refs": ["commondb:dry-run:fake-risk"],
        "snippets": [
            {
                "source_ref": "commondb:dry-run:fake-risk",
                "relevance": "Fake unsafe payload must be blocked.",
                "text": "raw_source: fake non-secret payload should not pass adapter validation",
            }
        ],
        "error": {"code": None, "message": None},
    }

    try:
        validate_context_result(fake_unsafe_result)
    except ContextValidationError:
        checks.append({"name": "fake_risk_blocked", "result": "passed"})
    else:
        return emit(args.json, "blocked", checks, "fake risk payload unexpectedly accepted")

    blocked_result = {
        "schema_version": "0.1",
        "record_type": "context_result",
        "result_id": "commondb-dry-run-blocked-001",
        "request_id": "commondb-dry-run-request-001",
        "status": "blocked",
        "source_refs": ["commondb:dry-run:fake-risk"],
        "snippets": [],
        "error": {
            "code": "dry_run_risk_blocked",
            "message": "Fake dry-run risk content was blocked before agent consumption.",
        },
    }
    validate_context_result(blocked_result)
    checks.append({"name": "sanitized_block_result", "result": "passed"})

    return emit(args.json, "passed", checks, "dry_run verified with sanitized blocked result")


def emit(json_mode: bool, status: str, checks: list[dict[str, str]], message: str) -> int:
    payload = {
        "schema_version": "0.1",
        "record_type": "commondb_mcp_dry_run_result",
        "status": status,
        "message": message,
        "checks": checks,
        "live_mcp": "not_used",
        "qdrant": "out_of_scope",
    }
    if json_mode:
        print(json.dumps(payload, sort_keys=True))
    else:
        print(f"status={status}")
        print(f"message={message}")
        for check in checks:
            print(f"check.{check['name']}={check['result']}")
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
