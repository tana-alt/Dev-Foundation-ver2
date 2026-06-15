"""Exit-code convention (R6) helpers for harness CLIs.

The repo-wide convention (docs/reference/exit-codes-reference.md) is:
0 = pass, 1 = quality fail (regression / gate fail), 2 = inconclusive
(re-measure), 3 = tool error (measurement impossible, bad config, missing
preconditions). argparse's default usage-error exit is 2, which would let a
typo masquerade as a statistical non-answer, so harness parsers remap usage
errors to 3.
"""

from __future__ import annotations

import argparse
import sys
from typing import NoReturn

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_INCONCLUSIVE = 2
EXIT_TOOL_ERROR = 3


class R6ArgumentParser(argparse.ArgumentParser):
    """ArgumentParser whose usage errors exit 3 (tool error) instead of 2."""

    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        self.exit(EXIT_TOOL_ERROR, f"{self.prog}: error: {message}\n")
