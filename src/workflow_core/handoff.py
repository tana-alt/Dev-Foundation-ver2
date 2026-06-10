"""Handoff builder -- the context-management seed and the loop's hand-off organ.

Builds the single bounded packet an agent turn receives instead of full
conversation history: the frozen spec reference, the current diff (truncated to
a budget so context cannot rot), and the last gate failure. ``render_handoff``
turns it into compact markdown for injection. When the loop arrives, each
iteration is re-seeded from this packet, not the accumulated transcript.
"""

from __future__ import annotations

from workflow_core.runtime import HandoffPacket

DEFAULT_DIFF_BUDGET = 6000
TRUNCATION_MARKER = "\n... [diff truncated to budget]"


def build_handoff(
    spec_ref: str,
    diff: str = "",
    last_failure: str = "",
    *,
    diff_budget: int = DEFAULT_DIFF_BUDGET,
) -> HandoffPacket:
    bounded = diff
    if len(diff) > diff_budget:
        bounded = diff[:diff_budget] + TRUNCATION_MARKER
    return HandoffPacket(spec_ref=spec_ref, diff=bounded, last_failure=last_failure)


def render_handoff(packet: HandoffPacket) -> str:
    parts = ["# Handoff", f"spec: {packet.spec_ref}"]
    if packet.last_failure:
        parts.append(f"\n## Last failure\n{packet.last_failure}")
    if packet.diff:
        parts.append(f"\n## Current diff\n```diff\n{packet.diff}\n```")
    return "\n".join(parts)
