from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol, cast

RunMode = Literal["mock", "sdk"]
RunStatus = Literal["completed", "blocked"]


class ContractValidationError(ValueError):
    """Raised when a work contract is not safe to hand to a runner."""


@dataclass(frozen=True)
class GitScope:
    mode: str
    base_ref: str
    merge_target: str
    branch_target: str
    worktree_target: str
    conflict_policy: str
    sibling_branch_refs: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> GitScope:
        return cls(
            mode=_require_text(data, "mode"),
            base_ref=_require_text(data, "base_ref"),
            merge_target=_require_text(data, "merge_target"),
            branch_target=_require_text(data, "branch_target"),
            worktree_target=_require_text(data, "worktree_target"),
            conflict_policy=_require_text(data, "conflict_policy"),
            sibling_branch_refs=tuple(_optional_text_list(data, "sibling_branch_refs")),
        )


@dataclass(frozen=True)
class ApprovedWorkContract:
    work_contract_id: str
    issue_id: str
    proposal_id: str
    project_id: str
    goal: str
    source_refs: tuple[str, ...]
    allowed_write_targets: tuple[str, ...]
    denied_context: tuple[str, ...]
    verification: tuple[str, ...]
    human_gate: dict[str, Any]
    risk_flags: tuple[str, ...]
    git_scope: GitScope

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> ApprovedWorkContract:
        normalized = _normalize_contract_mapping(data)
        contract = cls(
            work_contract_id=_require_text(normalized, "work_contract_id"),
            issue_id=_require_text(normalized, "issue_id"),
            proposal_id=_require_text(normalized, "proposal_id"),
            project_id=_require_text(normalized, "project_id"),
            goal=_require_text(normalized, "goal"),
            source_refs=tuple(_require_text_list(normalized, "source_refs")),
            allowed_write_targets=tuple(_require_text_list(normalized, "allowed_write_targets")),
            denied_context=tuple(_require_text_list(normalized, "denied_context")),
            verification=tuple(_require_text_list(normalized, "verification")),
            human_gate=_require_mapping(normalized, "human_gate"),
            risk_flags=tuple(_optional_text_list(normalized, "risk_flags")),
            git_scope=GitScope.from_mapping(_require_mapping(normalized, "git_scope")),
        )
        contract.validate_for_execution()
        return contract

    def validate_for_execution(self) -> None:
        status = self.human_gate.get("status")
        if status != "approved":
            raise ContractValidationError(
                "approved work contract requires human_gate.status == 'approved'"
            )
        if self.git_scope.mode != "parallel":
            raise ContractValidationError("codex runner requires git_scope.mode == 'parallel'")
        if not self.git_scope.branch_target.startswith("agent/"):
            raise ContractValidationError("branch_target must be an owned agent/* branch")
        if self.git_scope.merge_target in {"main", "master"}:
            raise ContractValidationError(
                "merge_target must be an explicit ref such as origin/main"
            )
        for target in self.allowed_write_targets:
            if Path(target).is_absolute() or ".." in Path(target).parts:
                raise ContractValidationError("allowed_write_targets must be relative repo paths")


@dataclass(frozen=True)
class CodexRunConfig:
    mode: RunMode = "mock"
    model: str = "configured-by-human"
    cwd: Path | None = None
    artifact_dir: Path = Path("artifact/demo-codex-sdk-run")
    allow_real_sdk: bool = False
    mock_summary: str = "mock codex sdk run completed"
    extra_instructions: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> CodexRunConfig:
        runner = _require_mapping(data, "runner") if "runner" in data else data
        mode_text = _require_text(runner, "mode") if "mode" in runner else "mock"
        if mode_text not in {"mock", "sdk"}:
            raise ContractValidationError("runner.mode must be 'mock' or 'sdk'")
        artifact_dir = Path(str(runner.get("artifact_dir", "artifact/demo-codex-sdk-run")))
        cwd_value = runner.get("cwd")
        cwd = Path(str(cwd_value)) if cwd_value else None
        return cls(
            mode=cast(RunMode, mode_text),
            model=str(runner.get("model", "configured-by-human")),
            cwd=cwd,
            artifact_dir=artifact_dir,
            allow_real_sdk=bool(runner.get("allow_real_sdk", False)),
            mock_summary=str(runner.get("mock_summary", "mock codex sdk run completed")),
            extra_instructions=tuple(_optional_text_list(runner, "extra_instructions")),
        )


@dataclass(frozen=True)
class CodexInvocation:
    prompt: str
    cwd: Path
    model: str
    allowed_write_targets: tuple[str, ...]


@dataclass(frozen=True)
class CodexSDKResult:
    status: RunStatus
    summary: str
    changed_paths: tuple[str, ...] = ()
    verification_notes: tuple[str, ...] = ()
    raw_response_ref: str = ""


class CodexSDKClient(Protocol):
    def run(self, invocation: CodexInvocation) -> CodexSDKResult:
        """Run Codex headlessly. Tests inject mocks; real execution is human-gated."""


@dataclass(frozen=True)
class MockCodexSDKClient:
    summary: str = "mock codex sdk run completed"
    changed_paths: tuple[str, ...] = ()
    verification_notes: tuple[str, ...] = ("mocked local execution only",)

    def run(self, invocation: CodexInvocation) -> CodexSDKResult:
        del invocation
        return CodexSDKResult(
            status="completed",
            summary=self.summary,
            changed_paths=self.changed_paths,
            verification_notes=self.verification_notes,
        )


@dataclass
class CapturingCodexSDKClient:
    result: CodexSDKResult
    invocations: list[CodexInvocation] = field(default_factory=list)

    def run(self, invocation: CodexInvocation) -> CodexSDKResult:
        self.invocations.append(invocation)
        return self.result


@dataclass(frozen=True)
class ExecutionRunResult:
    run_id: str
    work_contract_id: str
    project_id: str
    status: RunStatus
    mode: RunMode
    summary: str
    changed_paths: tuple[str, ...]
    verification_notes: tuple[str, ...]
    artifact_dir: Path
    created_at: str

    def to_record(self) -> dict[str, Any]:
        return {
            "schema_version": "0.1",
            "record_type": "codex_sdk_execution_run",
            "status": self.status,
            "identity": {
                "run_id": self.run_id,
                "work_contract_id": self.work_contract_id,
                "project_id": self.project_id,
                "created_at": self.created_at,
            },
            "runner": {"mode": self.mode},
            "outputs": {
                "summary": self.summary,
                "changed_paths": list(self.changed_paths),
                "verification_notes": list(self.verification_notes),
                "artifact_dir": self.artifact_dir.as_posix(),
            },
        }


@dataclass(frozen=True)
class CodexSDKExecutionAdapter:
    client: CodexSDKClient
    config: CodexRunConfig

    def build_invocation(self, contract: ApprovedWorkContract) -> CodexInvocation:
        cwd = self.config.cwd or Path(contract.git_scope.worktree_target)
        return CodexInvocation(
            prompt=build_headless_prompt(contract, self.config.extra_instructions),
            cwd=cwd,
            model=self.config.model,
            allowed_write_targets=contract.allowed_write_targets,
        )

    def execute(self, contract: ApprovedWorkContract) -> ExecutionRunResult:
        if self.config.mode == "sdk" and not self.config.allow_real_sdk:
            return ExecutionRunResult(
                run_id=_run_id(contract.work_contract_id),
                work_contract_id=contract.work_contract_id,
                project_id=contract.project_id,
                status="blocked",
                mode=self.config.mode,
                summary="real Codex SDK execution requires explicit human approval",
                changed_paths=(),
                verification_notes=("real SDK smoke skipped: human gate not approved",),
                artifact_dir=self.config.artifact_dir,
                created_at=_now(),
            )

        sdk_result = self.client.run(self.build_invocation(contract))
        _validate_changed_paths(contract, sdk_result.changed_paths)
        return ExecutionRunResult(
            run_id=_run_id(contract.work_contract_id),
            work_contract_id=contract.work_contract_id,
            project_id=contract.project_id,
            status=sdk_result.status,
            mode=self.config.mode,
            summary=sdk_result.summary,
            changed_paths=sdk_result.changed_paths,
            verification_notes=sdk_result.verification_notes,
            artifact_dir=self.config.artifact_dir,
            created_at=_now(),
        )


def build_headless_prompt(
    contract: ApprovedWorkContract,
    extra_instructions: tuple[str, ...] = (),
) -> str:
    lines = [
        "You are a headless Codex lane worker executing an approved work contract.",
        "",
        f"Work contract: {contract.work_contract_id}",
        f"Project: {contract.project_id}",
        f"Issue: {contract.issue_id}",
        f"Proposal: {contract.proposal_id}",
        f"Goal: {contract.goal}",
        "",
        "Source refs:",
        *[f"- {ref}" for ref in contract.source_refs],
        "",
        "Allowed write targets:",
        *[f"- {target}" for target in contract.allowed_write_targets],
        "",
        "Denied context:",
        *[f"- {item}" for item in contract.denied_context],
        "",
        "Required verification:",
        *[f"- {item}" for item in contract.verification],
        "",
        "Human gates and non-goals:",
        "- Do not merge, release, deploy, mutate CI/CD, handle secrets, or approve yourself.",
        "- Report real SDK smoke as skipped unless explicit human approval is supplied.",
        "",
        "Git scope:",
        f"- base_ref: {contract.git_scope.base_ref}",
        f"- merge_target: {contract.git_scope.merge_target}",
        f"- branch_target: {contract.git_scope.branch_target}",
        f"- worktree_target: {contract.git_scope.worktree_target}",
        f"- conflict_policy: {contract.git_scope.conflict_policy}",
    ]
    if contract.risk_flags:
        lines.extend(["", "Risk flags:", *[f"- {item}" for item in contract.risk_flags]])
    if extra_instructions:
        lines.extend(["", "Runner instructions:", *[f"- {item}" for item in extra_instructions]])
    return "\n".join(lines)


def _normalize_contract_mapping(data: dict[str, Any]) -> dict[str, Any]:
    if "work_contract_id" in data:
        return data

    identity = data.get("identity")
    intent = data.get("intent")
    inputs = data.get("inputs")
    boundaries = data.get("boundaries")
    verification = data.get("evidence_and_verification")
    values = (identity, intent, inputs, boundaries, verification)
    if not all(isinstance(value, dict) for value in values):
        return data

    return {
        "work_contract_id": identity.get("work_id"),
        "issue_id": data.get("issue_id", identity.get("issue_id", "")),
        "proposal_id": data.get("proposal_id", identity.get("proposal_id", "")),
        "project_id": identity.get("project_id"),
        "goal": intent.get("task_intent"),
        "source_refs": inputs.get("source_refs"),
        "allowed_write_targets": boundaries.get("allowed_write_targets"),
        "denied_context": boundaries.get("denied_context"),
        "verification": verification.get("verification_required"),
        "human_gate": data.get("human_gate", {"status": "required"}),
        "risk_flags": boundaries.get("risk_flags", []),
        "git_scope": boundaries.get("git_scope"),
    }


def _validate_changed_paths(contract: ApprovedWorkContract, changed_paths: tuple[str, ...]) -> None:
    for path in changed_paths:
        in_scope = any(
            path == target or path.startswith(f"{target.rstrip('/')}/")
            for target in contract.allowed_write_targets
        )
        if not in_scope:
            raise ContractValidationError(
                f"reported changed path is outside allowed targets: {path}"
            )


def _require_mapping(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ContractValidationError(f"{key} must be a mapping")
    return cast(dict[str, Any], value)


def _require_text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{key} must be a non-empty string")
    return value


def _require_text_list(data: dict[str, Any], key: str) -> list[str]:
    values = _optional_text_list(data, key)
    if not values:
        raise ContractValidationError(f"{key} must be a non-empty string list")
    return values


def _optional_text_list(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key, [])
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ContractValidationError(f"{key} must be a string list")
    return value


def _run_id(work_contract_id: str) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    return f"run-{work_contract_id}-{timestamp}"


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()
