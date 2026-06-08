#!/usr/bin/env python3
from __future__ import annotations

from agent_operational_checks import run_check, validate_operational_scorecard

if __name__ == "__main__":
    raise SystemExit(run_check("operational scorecard check", validate_operational_scorecard))
