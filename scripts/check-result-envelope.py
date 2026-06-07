#!/usr/bin/env python3
from __future__ import annotations

from agent_operational_checks import run_check, validate_check_result_envelopes

if __name__ == "__main__":
    raise SystemExit(run_check("check-result envelope check", validate_check_result_envelopes))
