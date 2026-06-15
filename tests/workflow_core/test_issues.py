from __future__ import annotations

from workflow_core.evaluation import EvalReport, ToolStat
from workflow_core.issues import IssueThresholds, derive_issues, render_issues_markdown


def report(**overrides: object) -> EvalReport:
    data: dict[str, object] = {
        "runs": 10,
        "success_rate": 0.9,
        "mean_tool_call_rate": 0.5,
        "mean_skill_usage_rate": 0.1,
        "runs_with_unexpected": 0,
    }
    data.update(overrides)
    return EvalReport.model_validate(data)


def stat(name: str, *, calls: int, failures: int) -> ToolStat:
    return ToolStat(
        name=name,
        kind="tool",
        calls=calls,
        failures=failures,
        runs_used=1,
        usage_rate=0.5,
        failure_rate=round(failures / calls, 4) if calls else 0.0,
    )


def test_healthy_signals_yield_no_issues() -> None:
    issues = derive_issues(report(), [stat("Bash", calls=20, failures=1)], IssueThresholds())
    assert issues == []


def test_low_success_rate_surfaces() -> None:
    (issue,) = derive_issues(report(success_rate=0.5), [], IssueThresholds())
    assert issue.kind == "low_success_rate"
    assert issue.value == 0.5


def test_no_runs_is_not_a_success_issue() -> None:
    empty = report(runs=0, success_rate=0.0)
    assert derive_issues(empty, [], IssueThresholds()) == []


def test_failing_tool_surfaces_only_above_min_calls() -> None:
    thresholds = IssueThresholds(min_calls=5, max_failure_rate=0.3)
    quiet = stat("WebFetch", calls=2, failures=2)
    noisy = stat("Bash", calls=6, failures=3)
    issues = derive_issues(report(), [quiet, noisy], thresholds)
    assert [issue.subject for issue in issues] == ["tool:Bash"]
    assert issues[0].kind == "high_failure_rate"


def test_unexpected_actions_surface() -> None:
    (issue,) = derive_issues(report(runs_with_unexpected=2), [], IssueThresholds())
    assert issue.kind == "unexpected_actions"
    assert issue.value == 2.0


def test_markdown_rendering_lists_issues_or_says_clean() -> None:
    issues = derive_issues(report(success_rate=0.5), [], IssueThresholds())
    markdown = render_issues_markdown(issues, project="demo", generated_at="t0")
    assert "# Open Harness Issues" in markdown
    assert "[low_success_rate]" in markdown
    clean = render_issues_markdown([], project="demo", generated_at="t0")
    assert "No open issues." in clean
