from __future__ import annotations


class DaemonError(RuntimeError):
    code = "internal_error"


class DaemonUnavailableError(DaemonError):
    code = "daemon_unavailable"


class UsageDaemonError(DaemonError):
    code = "usage_error"


class ConflictDaemonError(DaemonError):
    code = "conflict"


class IntegrityDaemonError(DaemonError):
    code = "integrity_error"
