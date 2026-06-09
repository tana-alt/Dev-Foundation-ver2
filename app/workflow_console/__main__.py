"""Entrypoint for the local mock workflow console."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from src.workflow_ui import render_console, render_html_console


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Render the sanitized workflow console.")
    parser.add_argument(
        "--format",
        choices=("text", "html"),
        default="text",
        help="Console output format.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional file path for rendered output.",
    )
    args = parser.parse_args(argv)

    rendered = render_html_console() if args.format == "html" else render_console()
    if args.output is None:
        print(rendered)
        return
    args.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
