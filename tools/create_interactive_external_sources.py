#!/usr/bin/env python3
"""Create a separated interactive external-source appendix."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.report_quality_contracts import ExternalResearchPacket
from src.report_quality_external_research import (
    save_external_research_packet,
    save_external_sources_markdown,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--fiscal-period", required=True)
    parser.add_argument("--out-dir", default="outputs/interactive-external")
    args = parser.parse_args()

    packet = ExternalResearchPacket(ticker=args.ticker.upper(), fiscal_period=args.fiscal_period)
    out_dir = Path(args.out_dir)
    save_external_research_packet(packet, out_dir / "external_research_packet.json")
    save_external_sources_markdown(packet, out_dir / "interactive_external_sources.md")
    print(f"created {out_dir}")


if __name__ == "__main__":
    main()
