from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from workflow_core.contract_harness.agent_tools import role_agent_skills, role_agent_tools
from workflow_core.contract_harness.contract import ensure_prepared
from workflow_core.contract_harness.jsonio import read_json, write_json
from workflow_core.contract_harness.runtime_paths import task_dir


def audit_context(root: Path, task_id: str) -> dict[str, Any]:
    ensure_prepared(root, task_id)
    runtime = task_dir(root, task_id)
    roles = {
        "writer": _role_context(root, task_id, runtime, "writer"),
        "reviewer": _role_context(root, task_id, runtime, "reviewer"),
        "integrator": _role_context(root, task_id, runtime, "integrator"),
    }
    result = {
        "task_id": task_id,
        "status": "pass" if all(role["status"] == "pass" for role in roles.values()) else "fail",
        "pressure_estimator": "utf8_json_bytes_and_chars_div_4",
        "roles": roles,
        "total_estimated_tokens": sum(int(role["estimated_tokens"]) for role in roles.values()),
    }
    write_json(runtime / "context-audit.json", result)
    return result


def _role_context(root: Path, task_id: str, runtime: Path, role: str) -> dict[str, Any]:
    tools = role_agent_tools(root, task_id, role)
    skills = role_agent_skills(root, role)
    payload = {
        "task_id": task_id,
        "role": role,
        "agent_tools": tools,
        "agent_skills": skills,
        "available_artifacts": _available_artifacts(runtime),
        "context": _payload_context(runtime, role),
    }
    missing = _missing_required(role, tools, skills)
    pressure = _pressure(payload)
    return {
        "status": "pass" if not missing else "fail",
        "bytes": pressure["bytes"],
        "estimated_tokens": pressure["estimated_tokens"],
        "tool_count": len(tools),
        "skill_count": len(skills),
        "tools": [str(tool.get("name", "")) for tool in tools],
        "skills": [str(skill.get("name", "")) for skill in skills],
        "missing_required": missing,
    }


def _available_artifacts(runtime: Path) -> dict[str, bool]:
    names = (
        "capsule.json",
        "contract.lock.json",
        "verifier-plan.json",
        "scope-map-forward.json",
        "scope-map-reverse.json",
        "verify-result.json",
        "submission.json",
        "integration-result.json",
    )
    return {name: (runtime / name).is_file() for name in names}


def _payload_context(runtime: Path, role: str) -> dict[str, Any]:
    if role == "writer":
        return {
            "capsule": _read_optional(runtime / "capsule.json"),
            "scope_map_forward": _read_optional(runtime / "scope-map-forward.json"),
        }
    if role == "reviewer":
        return {
            "scope_map_reverse": _read_optional(runtime / "scope-map-reverse.json"),
            "submission": _read_optional(runtime / "submission.json"),
            "review_packets": _review_packet_names(runtime),
        }
    return {
        "submission": _read_optional(runtime / "submission.json"),
        "integration_result": _read_optional(runtime / "integration-result.json"),
    }


def _review_packet_names(runtime: Path) -> list[str]:
    reviews = runtime / "reviews"
    if not reviews.is_dir():
        return []
    return sorted(path.name for path in reviews.glob("*.review-packet.json"))


def _read_optional(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return read_json(path)
    except (OSError, ValueError):
        return None


def _missing_required(
    role: str,
    tools: list[dict[str, Any]],
    skills: list[dict[str, Any]],
) -> list[str]:
    tool_names = {str(tool.get("name", "")) for tool in tools}
    skills_by_name = {str(skill.get("name", "")): skill for skill in skills}
    skill_names = set(skills_by_name)
    required_tools = {
        "writer": {"scope-map-forward", "verify", "submit", "context-audit"},
        "reviewer": {"scope-map-reverse", "review-verdict", "context-audit"},
        "integrator": {"review-collect", "dispatch", "gate", "context-audit"},
    }[role]
    required_skills = {
        "writer": {"tdd-scope", "implementation-slice-verification"},
        "reviewer": {"security-check", "implementation-slice-verification"},
        "integrator": {"scope-routing-governance", "implementation-slice-verification"},
    }[role]
    missing = [f"tool:{name}" for name in sorted(required_tools - tool_names)]
    missing.extend(f"skill:{name}" for name in sorted(required_skills - skill_names))
    for name in sorted(required_skills & skill_names):
        if not skills_by_name[name].get("path"):
            missing.append(f"skill_path:{name}")
    return missing


def _pressure(payload: dict[str, Any]) -> dict[str, int]:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    byte_count = len(text.encode("utf-8"))
    return {
        "bytes": byte_count,
        "estimated_tokens": max(1, math.ceil(len(text) / 4)),
    }
