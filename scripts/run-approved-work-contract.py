#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast

import yaml

from src.workflow_adapters.codex_sdk_adapter import (
    ApprovedWorkContract,
    CodexRunConfig,
    CodexSDKExecutionAdapter,
    ContractValidationError,
    MockCodexSDKClient,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run an approved work contract through a mockable Codex SDK adapter."
    )
    parser.add_argument("contract", type=Path, help="Path to approved work contract YAML.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("templates/codex-sdk-run-config.yaml"),
        help="Path to Codex SDK run config YAML.",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Override artifact output directory.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "yaml"),
        default="yaml",
        help="Output record format.",
    )
    args = parser.parse_args()

    try:
        contract_data = _load_mapping(args.contract)
        config_data = _load_mapping(args.config)
        contract = ApprovedWorkContract.from_mapping(contract_data)
        config = CodexRunConfig.from_mapping(config_data)
        if args.artifact_dir is not None:
            config = CodexRunConfig(
                mode=config.mode,
                model=config.model,
                cwd=config.cwd,
                artifact_dir=args.artifact_dir,
                allow_real_sdk=config.allow_real_sdk,
                mock_summary=config.mock_summary,
                extra_instructions=config.extra_instructions,
            )

        client = MockCodexSDKClient(summary=config.mock_summary)
        adapter = CodexSDKExecutionAdapter(client=client, config=config)
        result = adapter.execute(contract)
        record = result.to_record()
        output_path = _write_record(record, config.artifact_dir, args.format)
    except (ContractValidationError, OSError, yaml.YAMLError) as exc:
        print(f"blocked: {exc}", file=sys.stderr)
        return 2

    print(output_path.as_posix())
    return 0 if result.status == "completed" else 3


def _load_mapping(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ContractValidationError(f"{path} must contain a mapping")
    return cast(dict[str, Any], raw)


def _write_record(record: dict[str, Any], artifact_dir: Path, output_format: str) -> Path:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    output_path = artifact_dir / f"{record['identity']['run_id']}.{output_format}"
    if output_format == "json":
        output_path.write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    else:
        output_path.write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")
    return output_path


if __name__ == "__main__":
    raise SystemExit(main())
