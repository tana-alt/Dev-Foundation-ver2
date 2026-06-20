from __future__ import annotations

AUTHORITY_ARTIFACTS = {
    "contract.lock.json",
    "candidate.diff",
    "verify-result.json",
    "submission.json",
    "gate-result.json",
    "integration-result.json",
    "land-result.json",
    "push-result.json",
    "completion-certificate.json",
    "pr-result.json",
    "pr-check-result.json",
}

DIAGNOSTIC_ARTIFACTS = {
    "scope-map-forward.json",
    "scope-map-reverse.json",
    "affected-set.json",
    "context-audit.json",
    "agent-tools.json",
    "agent-skills.json",
    "writer-session.json",
    "integrator-session.json",
    "status-result.json",
}


def is_authority_artifact(name: str) -> bool:
    return name in AUTHORITY_ARTIFACTS or name.startswith("reviews/")


def is_diagnostic_artifact(name: str) -> bool:
    return name in DIAGNOSTIC_ARTIFACTS or name.startswith(("comm/", "reviews/worktree-"))


def artifact_type_for(name: str) -> str:
    if name.startswith("reviews/"):
        return "review_verdict"
    return name.removesuffix(".json").replace("-", "_").replace(".", "_").replace("/", "_")
