"""Interactive external-source separation.

External research is represented as a separate packet and Markdown appendix. It
is not consumed by the main earnings-review verdict unless a human explicitly
accepts a candidate and routes it back through a controlled workflow.
"""

from __future__ import annotations

from pathlib import Path

from .report_quality_contracts import ExternalResearchPacket


def render_external_sources_markdown(packet: ExternalResearchPacket) -> str:
    lines = [
        "# Interactive External Sources",
        "",
        "This file is intentionally separated from `report.md`.",
        "External sources do not modify the main verdict unless explicitly accepted.",
        "",
        "| source_id | title | published_date | timing | proposed_use | accepted_by_user | url |",
        "|---|---|---:|---|---|---|---|",
    ]
    for item in packet.candidates:
        lines.append(
            "| {source_id} | {title} | {published_date} | {timing} | {proposed_use} | {accepted} | {url} |".format(
                source_id=item.source_id.replace("|", "\\|"),
                title=item.title.replace("|", "\\|"),
                published_date=item.published_date or "—",
                timing=item.timing.value,
                proposed_use=item.proposed_use.replace("|", "\\|"),
                accepted=str(item.accepted_by_user).lower(),
                url=item.url.replace("|", "\\|"),
            )
        )
    return "\n".join(lines).strip() + "\n"


def save_external_sources_markdown(packet: ExternalResearchPacket, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_external_sources_markdown(packet), encoding="utf-8")


def load_external_research_packet(path: str | Path) -> ExternalResearchPacket:
    return ExternalResearchPacket.model_validate_json(Path(path).read_text(encoding="utf-8"))


def save_external_research_packet(packet: ExternalResearchPacket, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(packet.model_dump_json(indent=2), encoding="utf-8")
