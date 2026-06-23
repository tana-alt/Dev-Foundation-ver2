from __future__ import annotations

import json
from pathlib import Path

import pytest

from .conftest import TASK_ID, run_harness


def test_comm_peers_lists_spawned_writer_brief(harness_repo: Path) -> None:
    spawned = run_harness(
        harness_repo,
        "spawn",
        TASK_ID,
        "--role",
        "writer",
        "--agent",
        "codex",
        "--comm",
        "--brief",
        "インフラエンジニアとして環境構築を行う",
    )
    assert spawned.returncode == 0, spawned.stdout + spawned.stderr

    peers = run_harness(harness_repo, "comm-peers", TASK_ID)

    assert peers.returncode == 0, peers.stdout + peers.stderr
    result = json.loads(peers.stdout)
    assert result["peers"][0]["role"] == "writer"
    assert result["peers"][0]["brief"] == "インフラエンジニアとして環境構築を行う"


def test_comm_peers_keeps_multiple_briefed_writers(harness_repo: Path) -> None:
    first = run_harness(
        harness_repo,
        "spawn",
        TASK_ID,
        "--role",
        "writer",
        "--agent",
        "codex",
        "--comm",
        "--brief",
        "インフラエンジニアとして環境構築を行う",
    )
    second = run_harness(
        harness_repo,
        "spawn",
        TASK_ID,
        "--role",
        "writer",
        "--agent",
        "codex",
        "--comm",
        "--brief",
        "テストエンジニアとして検証計画を作る",
    )
    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    first_session = json.loads(first.stdout)
    second_session = json.loads(second.stdout)

    peers = run_harness(harness_repo, "comm-peers", TASK_ID)

    assert peers.returncode == 0, peers.stdout + peers.stderr
    result = json.loads(peers.stdout)
    ids = {peer["agent_id"] for peer in result["peers"]}
    briefs = {peer["brief"] for peer in result["peers"]}
    assert first_session["agent_id"] != second_session["agent_id"]
    assert first_session["agent_id"] in ids
    assert second_session["agent_id"] in ids
    assert "インフラエンジニアとして環境構築を行う" in briefs
    assert "テストエンジニアとして検証計画を作る" in briefs
    assert all(peer["delegation_hash_id"].startswith("sha256:") for peer in result["peers"])


def test_comm_send_to_existing_peer_resolves_sender_and_target_role(
    harness_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spawned = run_harness(
        harness_repo,
        "spawn",
        TASK_ID,
        "--role",
        "writer",
        "--agent",
        "codex",
        "--comm",
        "--brief",
        "インフラエンジニアとして環境構築を行う",
    )
    assert spawned.returncode == 0, spawned.stdout + spawned.stderr
    peer_id = json.loads(spawned.stdout)["agent_id"]
    monkeypatch.setenv("FOUNDATION_AGENT_ID", "writer.codex.T-0001.coordinator")
    monkeypatch.setenv("HARNESS_ROLE", "writer")

    sent = run_harness(
        harness_repo,
        "comm-send",
        TASK_ID,
        "--to",
        peer_id,
        "--subject",
        "環境構築",
        "--body",
        "Goal: prepare the environment",
        "--delegation-brief",
        "インフラエンジニアとして環境構築を行う",
    )

    assert sent.returncode == 0, sent.stdout + sent.stderr
    message = json.loads(sent.stdout)
    assert message["from"]["agent_id"] == "writer.codex.T-0001.coordinator"
    assert message["to"]["agent_id"] == peer_id
    assert message["to"]["role"] == "writer"
    assert message["kind"] == "action_request"
    assert message["delegation"]["brief"] == "インフラエンジニアとして環境構築を行う"
    inbox = run_harness(harness_repo, "comm-inbox", TASK_ID, "--agent-id", peer_id)
    assert inbox.returncode == 0, inbox.stdout + inbox.stderr
    assert json.loads(inbox.stdout)["message_count"] == 1


def test_comm_send_to_unknown_peer_requires_session(
    harness_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FOUNDATION_AGENT_ID", "writer.codex.T-0001.coordinator")
    monkeypatch.setenv("HARNESS_ROLE", "writer")

    sent = run_harness(
        harness_repo,
        "comm-send",
        TASK_ID,
        "--to",
        "writer.codex.T-0001.unknown",
        "--subject",
        "環境構築",
        "--body",
        "Goal: prepare the environment",
    )

    assert sent.returncode == 1
    assert "unknown peer" in sent.stdout


def test_handoff_reply_links_to_delegation_message(
    harness_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spawned = run_harness(
        harness_repo,
        "spawn",
        TASK_ID,
        "--role",
        "writer",
        "--agent",
        "codex",
        "--comm",
        "--brief",
        "インフラエンジニアとして環境構築を行う",
    )
    peer_id = json.loads(spawned.stdout)["agent_id"]
    monkeypatch.setenv("FOUNDATION_AGENT_ID", "writer.codex.T-0001.coordinator")
    delegation = run_harness(
        harness_repo,
        "comm-send",
        TASK_ID,
        "--to",
        peer_id,
        "--subject",
        "環境構築",
        "--body",
        "Goal: prepare the environment",
        "--delegation-brief",
        "インフラエンジニアとして環境構築を行う",
    )
    delegation_id = json.loads(delegation.stdout)["message_sha256"]
    monkeypatch.setenv("FOUNDATION_AGENT_ID", peer_id)

    reply = run_harness(
        harness_repo,
        "comm-send",
        TASK_ID,
        "--to",
        "writer.codex.T-0001.coordinator",
        "--subject",
        "環境構築 handoff",
        "--body",
        "環境構築は完了。検証は unit で確認済み。",
        "--in-reply-to",
        delegation_id,
    )

    assert reply.returncode == 0, reply.stdout + reply.stderr
    message = json.loads(reply.stdout)
    assert message["kind"] == "handoff_note"
    assert message["in_reply_to"] == delegation_id
    assert "環境構築は完了" in message["body_markdown"]


def test_handoff_reply_requires_existing_message(
    harness_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FOUNDATION_AGENT_ID", "writer.codex.T-0001.infra")
    monkeypatch.setenv("HARNESS_ROLE", "writer")

    reply = run_harness(
        harness_repo,
        "comm-send",
        TASK_ID,
        "--to",
        "writer.codex.T-0001.coordinator",
        "--subject",
        "環境構築 handoff",
        "--body",
        "環境構築は完了。",
        "--in-reply-to",
        "sha256:missing",
    )

    assert reply.returncode == 1
    assert "in_reply_to message not found" in reply.stdout
