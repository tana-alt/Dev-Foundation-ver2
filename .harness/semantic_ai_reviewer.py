from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        print("usage: semantic_ai_reviewer.py <review_packet> <review_output>", file=sys.stderr)
        return 2
    packet_path = Path(args[0]).resolve()
    output_path = Path(args[1]).resolve()
    packet = _read_json(packet_path)
    workspace = Path(str(packet["review_workspace"]["path"])).resolve()
    response = _run_codex(packet_path, output_path, workspace, packet)
    verdict = _parse_verdict(response)
    output_path.write_text(json.dumps(verdict, sort_keys=True) + "\n", encoding="utf-8")
    return 0


def _run_codex(
    packet_path: Path,
    output_path: Path,
    workspace: Path,
    packet: dict[str, Any],
) -> str:
    codex_bin = os.environ.get("HARNESS_SEMANTIC_REVIEWER_CODEX_BIN", "codex")
    timeout = int(os.environ.get("HARNESS_SEMANTIC_REVIEWER_TIMEOUT_S", "900"))
    with tempfile.TemporaryDirectory(prefix="semantic-review-") as tmp:
        tmp_path = Path(tmp)
        schema_path = tmp_path / "verdict.schema.json"
        response_path = tmp_path / "response.json"
        schema_path.write_text(json.dumps(_schema(), sort_keys=True), encoding="utf-8")
        command = [
            codex_bin,
            "--ask-for-approval",
            "never",
            "exec",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--color",
            "never",
            "--cd",
            str(workspace),
            "--add-dir",
            str(packet_path.parents[1]),
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(response_path),
        ]
        model = os.environ.get("HARNESS_SEMANTIC_REVIEWER_MODEL")
        if model:
            command.extend(["--model", model])
        command.append("-")
        completed = subprocess.run(
            command,
            input=_prompt(packet_path, output_path, packet),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(_bounded(completed.stderr or completed.stdout))
        if response_path.is_file():
            return response_path.read_text(encoding="utf-8")
        return completed.stdout


def _prompt(packet_path: Path, output_path: Path, packet: dict[str, Any]) -> str:
    summary = {
        "task_id": packet.get("task_id"),
        "candidate_diff_sha256": packet.get("candidate_diff_sha256"),
        "candidate_diff_index": packet.get("candidate_diff_index"),
        "test_interpretation": packet.get("test_interpretation"),
        "quality_status": (packet.get("quality_result") or {}).get("status"),
        "tool_candidates_status": (packet.get("tool_candidates") or {}).get("status"),
        "reviewer_policy": packet.get("reviewer_policy"),
        "diff_instruction": packet.get("diff_instruction"),
    }
    return (
        "You are the semantic AI reviewer for a contract harness task.\n"
        "Read the review packet and decide whether to approve or block the candidate.\n"
        "Do not edit files. Do not run broad tests. Use the packet's diff, diff index, "
        "machine evidence, test interpretation, quality flags, tool candidates, and "
        "reviewer policy as the review basis.\n"
        "Approve only when the diff appears aligned with the task goal and the machine "
        "evidence is meaningful. Block if the implementation is semantically wrong, "
        "under-tested for the stated goal, gaming a gate, task-specific as a proposed "
        "general tool, or missing required evidence.\n"
        f"Review packet path: {packet_path}\n"
        f"Harness output path: {output_path}\n"
        "Packet summary:\n"
        f"{json.dumps(summary, indent=2, sort_keys=True)}\n"
        "Return only JSON matching the provided schema.\n"
    )


def _schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["verdict", "labels", "reason"],
        "properties": {
            "verdict": {"type": "string", "enum": ["approve", "block"]},
            "labels": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 8,
            },
            "reason": {"type": "string", "maxLength": 2000},
        },
    }


def _parse_verdict(text: str) -> dict[str, Any]:
    data = json.loads(_strip_fence(text))
    if not isinstance(data, dict):
        raise ValueError("semantic reviewer response must be a JSON object")
    verdict = str(data.get("verdict", ""))
    if verdict not in {"approve", "block"}:
        raise ValueError("semantic reviewer verdict must be approve or block")
    labels = data.get("labels", [])
    if not isinstance(labels, list) or not all(isinstance(item, str) for item in labels):
        raise ValueError("semantic reviewer labels must be a string list")
    return {
        "verdict": verdict,
        "labels": labels[:8],
        "reason": str(data.get("reason", ""))[:2000],
    }


def _strip_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _bounded(text: str) -> str:
    return text.strip()[:4000]


if __name__ == "__main__":
    raise SystemExit(main())
