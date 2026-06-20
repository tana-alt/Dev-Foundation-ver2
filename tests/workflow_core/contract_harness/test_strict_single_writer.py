from __future__ import annotations

import concurrent.futures
import json
from pathlib import Path

from .conftest import TASK_ID, create_session, start_daemon, strict_cli, strict_json


def test_strict_concurrent_submit_requests_are_serialized(harness_repo: Path) -> None:
    daemon = start_daemon(harness_repo)
    try:
        writer = create_session(harness_repo, "writer", agent_id="writer.codex.T-0001")
        admin = create_session(harness_repo, "admin", agent_id="admin.local.T-0001")
        assert strict_cli(harness_repo, "prepare", TASK_ID, session=writer).returncode == 0
        (harness_repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
        assert strict_cli(harness_repo, "verify", TASK_ID, session=writer).returncode == 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(
                    lambda _i: strict_cli(harness_repo, "submit", TASK_ID, session=writer),
                    range(2),
                )
            )

        codes = sorted(result.returncode for result in results)
        assert codes == [0, 1]
        failed = [json.loads(result.stdout) for result in results if result.returncode != 0][0]
        assert failed["error"]["code"] == "invalid_state"
        integrity = strict_json(harness_repo, "integrity", "verify", session=admin)
        assert integrity["result"]["status"] == "pass"
    finally:
        daemon.stop()
