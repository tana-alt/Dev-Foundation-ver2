from __future__ import annotations

from pathlib import Path

from workflow_core.envfp import collect_fingerprint, fingerprint_hash

EXPECTED_FIELDS = {
    "cpu_model",
    "nproc",
    "cgroup_cpu_quota",
    "cgroup_mem_limit_mb",
    "kernel",
    "os_image",
    "runtime_versions",
    "lockfile_hashes",
    "cpu_governor",
    "virtualized",
}

# ---------------------------------------------------------------------------
# collect_fingerprint
# ---------------------------------------------------------------------------


def test_all_r13_fields_present() -> None:
    data = collect_fingerprint()
    assert set(data) == EXPECTED_FIELDS
    versions = data["runtime_versions"]
    assert isinstance(versions, dict) and "python" in versions


def test_lockfile_hash_changes_fingerprint(tmp_path: Path) -> None:
    bare = collect_fingerprint(tmp_path)
    assert bare["lockfile_hashes"] == {}
    (tmp_path / "uv.lock").write_text("lock-content", encoding="utf-8")
    locked = collect_fingerprint(tmp_path)
    hashes = locked["lockfile_hashes"]
    assert isinstance(hashes, dict) and "uv.lock" in hashes
    assert fingerprint_hash(bare) != fingerprint_hash(locked)


# ---------------------------------------------------------------------------
# fingerprint_hash
# ---------------------------------------------------------------------------


def test_fingerprint_hash_is_canonical() -> None:
    a = {"b": 1, "a": {"y": 2, "x": 3}}
    b = {"a": {"x": 3, "y": 2}, "b": 1}
    assert fingerprint_hash(a) == fingerprint_hash(b)
    assert len(fingerprint_hash(a)) == 64
