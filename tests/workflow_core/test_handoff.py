from __future__ import annotations

from workflow_core.handoff import TRUNCATION_MARKER, build_handoff, render_handoff


def test_build_handoff_keeps_small_diff_intact() -> None:
    packet = build_handoff("Plan/spec.md", diff="+a\n+b\n", last_failure="check failed")
    assert packet.spec_ref == "Plan/spec.md"
    assert packet.diff == "+a\n+b\n"
    assert packet.last_failure == "check failed"


def test_build_handoff_truncates_over_budget() -> None:
    big = "+" + "x" * 10000
    packet = build_handoff("Plan/spec.md", diff=big, diff_budget=100)
    assert packet.diff.endswith(TRUNCATION_MARKER)
    assert len(packet.diff) == 100 + len(TRUNCATION_MARKER)


def test_render_handoff_includes_sections_present() -> None:
    rendered = render_handoff(build_handoff("Plan/spec.md", diff="+a\n", last_failure="boom"))
    assert "spec: Plan/spec.md" in rendered
    assert "## Last failure" in rendered
    assert "boom" in rendered
    assert "```diff" in rendered


def test_render_handoff_omits_absent_sections() -> None:
    rendered = render_handoff(build_handoff("Plan/spec.md"))
    assert "spec: Plan/spec.md" in rendered
    assert "## Last failure" not in rendered
    assert "## Current diff" not in rendered
