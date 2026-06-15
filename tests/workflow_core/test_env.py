"""Tests for workflow_core.env -- env_int and env_float knob parsing."""

from __future__ import annotations

import pytest

from workflow_core.env import env_float, env_int

# ---------------------------------------------------------------------------
# env_int
# ---------------------------------------------------------------------------


def test_env_int_unset_returns_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FOUNDATION_TEST_INT", raising=False)
    assert env_int("FOUNDATION_TEST_INT", 42) == 42


def test_env_int_valid_value_is_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDATION_TEST_INT", "7")
    assert env_int("FOUNDATION_TEST_INT", 0) == 7


def test_env_int_malformed_returns_default_and_warns(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("FOUNDATION_TEST_INT", "not_a_number")
    result = env_int("FOUNDATION_TEST_INT", 99)
    assert result == 99
    captured = capsys.readouterr()
    assert "warning" in captured.err.lower()
    assert "FOUNDATION_TEST_INT" in captured.err


def test_env_int_empty_string_returns_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDATION_TEST_INT", "")
    assert env_int("FOUNDATION_TEST_INT", 5) == 5


def test_env_int_whitespace_only_returns_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDATION_TEST_INT", "   ")
    assert env_int("FOUNDATION_TEST_INT", 5) == 5


def test_env_int_no_warning_for_empty_string(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("FOUNDATION_TEST_INT", "")
    env_int("FOUNDATION_TEST_INT", 1)
    captured = capsys.readouterr()
    assert captured.err == ""


# ---------------------------------------------------------------------------
# env_float
# ---------------------------------------------------------------------------


def test_env_float_unset_returns_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FOUNDATION_TEST_FLOAT", raising=False)
    assert env_float("FOUNDATION_TEST_FLOAT", 1.5) == 1.5


def test_env_float_valid_value_is_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDATION_TEST_FLOAT", "3.14")
    assert env_float("FOUNDATION_TEST_FLOAT", 0.0) == pytest.approx(3.14)


def test_env_float_malformed_returns_default_and_warns(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("FOUNDATION_TEST_FLOAT", "banana")
    result = env_float("FOUNDATION_TEST_FLOAT", 2.0)
    assert result == 2.0
    captured = capsys.readouterr()
    assert "warning" in captured.err.lower()
    assert "FOUNDATION_TEST_FLOAT" in captured.err


def test_env_float_empty_string_returns_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDATION_TEST_FLOAT", "")
    assert env_float("FOUNDATION_TEST_FLOAT", 9.9) == 9.9


def test_env_float_whitespace_only_returns_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDATION_TEST_FLOAT", "  ")
    assert env_float("FOUNDATION_TEST_FLOAT", 9.9) == 9.9


def test_env_float_no_warning_for_empty_string(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("FOUNDATION_TEST_FLOAT", "")
    env_float("FOUNDATION_TEST_FLOAT", 1.0)
    captured = capsys.readouterr()
    assert captured.err == ""
