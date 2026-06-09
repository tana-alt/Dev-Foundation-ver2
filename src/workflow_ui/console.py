"""Deterministic local console rendering for sanitized workflow fixtures."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from html import escape

from src.workflow_ui.fixtures import (
    AppServerUiPanel,
    WorkflowRun,
    WorkflowRunEvent,
    load_sanitized_runs,
)

FORBIDDEN_TEXT = (
    "raw_thread_body",
    "raw_terminal_log",
    "credential",
    "browser_session",
    "local_runtime_state",
)


def assert_sanitized(run: WorkflowRun) -> None:
    """Reject fixture content that would weaken the lane's evidence boundary."""
    rendered = repr(run).lower()
    for forbidden in FORBIDDEN_TEXT:
        if forbidden in rendered:
            raise ValueError(f"fixture contains forbidden marker: {forbidden}")


def build_console_snapshot(runs: Iterable[WorkflowRun] | None = None) -> dict[str, object]:
    selected_runs = list(runs if runs is not None else load_sanitized_runs())
    for run in selected_runs:
        assert_sanitized(run)

    return {
        "screen_order": [
            "work_queue",
            "proposal_review",
            "approved_contract",
            "execution_run",
            "verification",
            "handoff",
        ],
        "runs": selected_runs,
        "real_app_server_smoke": "skipped_human_gate_required",
    }


def _app_server_panel(run: WorkflowRun) -> AppServerUiPanel:
    panel = run["app_server"]
    if not panel["codex_app_link_ref"].startswith("codex-app-link:"):
        raise ValueError("codex app link ref must be opaque")
    if not panel["thread_ref"].startswith("app-server-thread:"):
        raise ValueError("app server thread ref must be opaque")
    for artifact_ref in panel["artifact_refs"]:
        if not (
            artifact_ref.startswith("codex-app-artifact:") or artifact_ref.startswith("github-pr:")
        ):
            raise ValueError("artifact ref must be an approved opaque ref")
    for event in panel["events"]:
        if not event["external_event_ref"].startswith("app-server-event:"):
            raise ValueError("app server event ref must be opaque")
    return panel


def _validate_workflow_controls(run: WorkflowRun) -> None:
    if run["commondb"]["stores_raw_body"]:
        raise ValueError("commondb controls must not store raw bodies")
    allowed_destinations = {"useful_source", "approved_memo"}
    for destination in run["commondb"]["searchable_destinations"]:
        if destination not in allowed_destinations:
            raise ValueError("commondb destination is outside approved scope")
    if run["scope_guard"]["status"] == "spec_amendment_required":
        return
    if "goal drift" not in run["scope_guard"]["completion_policy"].lower():
        raise ValueError("scope guard must reject goal drift completion")


def render_console(runs: Iterable[WorkflowRun] | None = None) -> str:
    snapshot = build_console_snapshot(runs)
    selected_runs = snapshot["runs"]
    if not isinstance(selected_runs, list):
        raise TypeError("console snapshot runs must be a list")

    lines = ["Workflow Console", "Real App Server smoke: skipped"]
    for run in selected_runs:
        _validate_workflow_controls(run)
        app_server = _app_server_panel(run)
        latest_event = app_server["events"][-1] if app_server["events"] else None
        lines.extend(
            [
                "",
                f"Goal: {run['goal']['statement']}",
                f"Work queue: {run['issue_id']} - {run['title']}",
                f"Proposal review: {run['proposal_summary']}",
                f"Selected candidate: {run['candidates'][0]['candidate_id']}",
                f"Approved contract: {run['approved_contract_ref']}",
                f"Execution run: {run['execution_status']} via {run['runner']}",
                f"Codex App link: {app_server['codex_app_link_ref']}",
                f"App Server project: {app_server['project_id']} / {app_server['workflow_id']}",
                f"App Server thread: {app_server['thread_ref']} via {app_server['transport']}",
                f"App Server gate: {app_server['gate_status']}",
                f"CommonDB search: {run['commondb']['search_permission']}",
                f"CommonDB searchable: {', '.join(run['commondb']['searchable_destinations'])}",
                f"Scope guard: {run['scope_guard']['status']}",
                f"Verification: {run['verification_result']}",
                f"Handoff: {run['handoff_status']}",
            ]
        )
        if latest_event is not None:
            lines.append(f"Latest event: {latest_event['kind']} - {latest_event['summary']}")
    return "\n".join(lines)


def render_html_console(runs: Iterable[WorkflowRun] | None = None) -> str:
    snapshot = build_console_snapshot(runs)
    selected_runs = snapshot["runs"]
    if not isinstance(selected_runs, list):
        raise TypeError("console snapshot runs must be a list")

    run_sections = "\n".join(_render_run_card(run) for run in selected_runs)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Workflow Console</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f8f5;
      --surface: #ffffff;
      --ink: #17211b;
      --muted: #627064;
      --line: #d7ddd2;
      --accent: #0f766e;
      --warn: #a15c07;
      --good: #2f6b3f;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--ink);
      font: 14px/1.5 ui-sans-serif, system-ui, -apple-system,
        BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    main {{
      width: min(1180px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 28px 0 36px;
    }}
    header {{
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 16px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 18px;
      margin-bottom: 18px;
    }}
    h1 {{
      margin: 0;
      font-size: 24px;
      line-height: 1.2;
      letter-spacing: 0;
    }}
    .meta {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
      color: var(--muted);
      font-size: 13px;
    }}
    .pill {{
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 4px 10px;
      background: var(--surface);
      white-space: nowrap;
    }}
    .run {{
      display: grid;
      grid-template-columns: minmax(0, 1.05fr) minmax(320px, 0.95fr);
      gap: 14px;
      align-items: stretch;
    }}
    .panel {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      min-width: 0;
    }}
    h2, h3 {{
      margin: 0 0 10px;
      font-size: 16px;
      line-height: 1.25;
      letter-spacing: 0;
    }}
    dl {{
      display: grid;
      grid-template-columns: 150px minmax(0, 1fr);
      gap: 8px 12px;
      margin: 0;
    }}
    dt {{
      color: var(--muted);
    }}
    dd {{
      margin: 0;
      overflow-wrap: anywhere;
    }}
    .status {{
      color: var(--warn);
      font-weight: 700;
    }}
    .event-list {{
      display: grid;
      gap: 10px;
      margin: 0;
      padding: 0;
      list-style: none;
    }}
    .event {{
      border-left: 3px solid var(--accent);
      padding-left: 10px;
    }}
    .event.blocked {{
      border-color: var(--warn);
    }}
    .event.observed {{
      border-color: var(--good);
    }}
    .event-head {{
      display: flex;
      gap: 8px;
      align-items: baseline;
      justify-content: space-between;
      color: var(--muted);
      font-size: 12px;
    }}
    .event-summary {{
      margin-top: 3px;
      overflow-wrap: anywhere;
    }}
    .stack {{
      display: grid;
      gap: 12px;
    }}
    .section-title {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
    }}
    ul.compact {{
      margin: 0;
      padding-left: 18px;
    }}
    .link-ref {{
      color: var(--accent);
      font-weight: 700;
      overflow-wrap: anywhere;
    }}
    @media (max-width: 820px) {{
      main {{
        width: min(100vw - 20px, 680px);
        padding-top: 18px;
      }}
      header, .run {{
        display: block;
      }}
      .meta {{
        justify-content: flex-start;
        margin-top: 12px;
      }}
      .panel + .panel {{
        margin-top: 12px;
      }}
      dl {{
        grid-template-columns: 1fr;
      }}
      dt {{
        font-weight: 700;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Workflow Console</h1>
      <div class="meta">
        <span class="pill">Workflow Core authority</span>
        <span class="pill">App Server refs only</span>
        <span class="pill">Real smoke skipped</span>
      </div>
    </header>
    {run_sections}
  </main>
</body>
</html>
"""


def _render_run_card(run: WorkflowRun) -> str:
    _validate_workflow_controls(run)
    app_server = _app_server_panel(run)
    events = "\n".join(_render_event(event) for event in app_server["events"])
    return f"""<section class="run" aria-label="{escape(run["issue_id"])}">
  <article class="panel stack">
    <div>
      <div class="section-title">Goal setup</div>
      <h2>{escape(run["goal"]["statement"])}</h2>
      <dl>
        <dt>Outcome</dt>
        <dd>{escape(run["goal"]["desired_outcome"])}</dd>
        <dt>CommonDB</dt>
        <dd>{escape(run["goal"]["commondb_preference"])}</dd>
        <dt>Success</dt>
        <dd>{_render_list(run["goal"]["success_criteria"])}</dd>
        <dt>Non-goals</dt>
        <dd>{_render_list(run["goal"]["non_goals"])}</dd>
      </dl>
    </div>
    <div>
      <div class="section-title">Proposal candidate</div>
      <dl>
        <dt>Issue</dt>
        <dd>{escape(run["issue_id"])}</dd>
        <dt>Selected</dt>
        <dd>{escape(run["candidates"][0]["candidate_id"])}
          - {escape(run["candidates"][0]["title"])}</dd>
        <dt>Proposal</dt>
        <dd>{escape(run["proposal_summary"])}</dd>
        <dt>Codex App</dt>
        <dd class="link-ref">{escape(run["candidates"][0]["codex_app_ref"])}</dd>
        <dt>Contract</dt>
        <dd>{escape(run["approved_contract_ref"])}</dd>
        <dt>Execution</dt>
        <dd><span class="status">{escape(run["execution_status"])}</span>
          via {escape(run["runner"])}</dd>
      </dl>
    </div>
    <div>
      <div class="section-title">CommonDB controls</div>
      <dl>
        <dt>Search</dt>
        <dd>{escape(run["commondb"]["search_permission"])}</dd>
        <dt>Searchable</dt>
        <dd>{_render_list(run["commondb"]["searchable_destinations"])}</dd>
        <dt>Sources</dt>
        <dd>{_render_list(run["commondb"]["source_refs"])}</dd>
        <dt>Approved memos</dt>
        <dd>{_render_list(run["commondb"]["approved_memo_refs"])}</dd>
        <dt>Migration</dt>
        <dd>{escape(run["commondb"]["migration_approval"])}</dd>
      </dl>
    </div>
    <div>
      <div class="section-title">Scope guard</div>
      <dl>
        <dt>Status</dt>
        <dd>{escape(run["scope_guard"]["status"])}</dd>
        <dt>Policy</dt>
        <dd>{escape(run["scope_guard"]["expansion_policy"])}</dd>
        <dt>Completion</dt>
        <dd>{escape(run["scope_guard"]["completion_policy"])}</dd>
      </dl>
    </div>
  </article>
  <aside class="panel" aria-label="App Server integration">
    <h3>Codex App Project Link</h3>
    <dl>
      <dt>Project</dt>
      <dd>{escape(app_server["project_id"])}</dd>
      <dt>Workflow</dt>
      <dd>{escape(app_server["workflow_id"])}</dd>
      <dt>Codex App</dt>
      <dd class="link-ref">{escape(app_server["codex_app_link_ref"])}</dd>
      <dt>Status</dt>
      <dd>{escape(app_server["link_status"])}</dd>
      <dt>Thread</dt>
      <dd>{escape(app_server["thread_ref"])}</dd>
      <dt>Transport</dt>
      <dd>{escape(app_server["transport"])}</dd>
      <dt>Gate</dt>
      <dd>{escape(app_server["gate_status"])}</dd>
      <dt>Smoke</dt>
      <dd>{escape(app_server["real_smoke_status"])}</dd>
      <dt>Artifacts</dt>
      <dd>{_render_list(app_server["artifact_refs"])}</dd>
    </dl>
    <h3>Events</h3>
    <ol class="event-list">
      {events}
    </ol>
  </aside>
</section>"""


def _render_list(values: Sequence[str]) -> str:
    items = "".join(f"<li>{escape(value)}</li>" for value in values)
    return f'<ul class="compact">{items}</ul>'


def _render_event(event: WorkflowRunEvent) -> str:
    status = escape(event["status"])
    return f"""<li class="event {status}">
  <div class="event-head">
    <span>{escape(event["kind"])}</span>
    <span>{status}</span>
  </div>
  <div class="event-summary">{escape(event["summary"])}</div>
</li>"""
