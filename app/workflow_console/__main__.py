"""Entrypoint for the local mock workflow console."""

from src.workflow_ui import render_console


def main() -> None:
    print(render_console())


if __name__ == "__main__":
    main()
