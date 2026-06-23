以下の形に寄せるのがよいです。

* `policy.yaml`: repo-wide の方針、アーキテクチャ不変条件、review の姿勢、scope 判定原則だけを持つ。
* `task.yaml`: task 固有の目的、設計前提、影響範囲、受け入れ条件、不変条件、攻撃的入力、review 依頼を持つ。
* `AGENTS.md`: ACP、review handoff、具体コマンド、エージェント間の運用手順を持つ。
* `docs/reference`: 補助資料。completion-critical な情報の唯一の置き場にはしない。
* `allowed_paths`: hard gate ではなく、期待される影響範囲・review hint。
* `forbidden_paths`: block。
* YAML 必須情報の欠落: `rework`。
* 形式揺れ: 許容。semantic completeness を見る。

以下がブラッシュアップ案です。

---

## `.harness/policy.yaml` 案

```yaml
schema_version: 1
policy_id: "contract-harness-policy"
policy_kind: "repo_wide_policy"

authority:
  source: ".harness/policy.yaml"
  rule: >
    This file defines repo-wide harness policy. Task-specific requirements
    belong in task.yaml. Operational procedures such as ACP usage and review
    handoff commands belong in AGENTS.md.
  missing_required_yaml_information: "rework"
  format_variance: "tolerated"
  interpretation: >
    Prefer semantic completeness over rigid field spelling. If required
    information is absent, ambiguous, or only present in optional references,
    request rework.

context_model:
  contract_sources:
    global_policy: ".harness/policy.yaml"
    task_contract: ".harness/tasks/<task_id>/task.yaml"
    operational_protocols: "AGENTS.md"
    optional_references: "docs/reference/**"

  rule: >
    Normal writer, reviewer, and integrator work should be possible from
    AGENTS.md, policy.yaml, task.yaml, and generated packets. Reference docs
    may explain details but must not be the only source of completion-critical
    requirements.

  completion_critical_information_must_be_inline:
    - task_goal
    - task_architecture
    - expected_scope
    - forbidden_scope
    - protected_invariants
    - acceptance_criteria
    - adversarial_inputs_or_attack_tests
    - expected_evidence
    - review_request

architecture:
  summary: >
    Contract Harness coordinates agent work through task contracts, bounded
    scope, evidence, staged review, gate decisions, and integration decisions.
    The tracked control plane defines policy and tasks; runtime state and
    operational queues must remain outside tracked repository state.

  boundaries:
    tracked_control_plane:
      - ".harness/policy.yaml"
      - ".harness/tasks/**/task.yaml"
      - ".harness/review.yaml"
      - "AGENTS.md"
      - "README.md"
      - "docs/reference/**"

    runtime_state:
      - "harness-runtime/**"
      - ".harness/state/**"

  repo_wide_invariants:
    - id: "ARCH-CONTROL-PLANE-TRACKED"
      statement: ".harness policy/task files are tracked control-plane configuration."

    - id: "ARCH-RUNTIME-NOT-TRACKED"
      statement: "Runtime queues, locks, sessions, credentials, and generated operational state must not be tracked."

    - id: "ARCH-TASK-CONTRACT-SELF-CONTAINED"
      statement: "task.yaml must contain enough task-specific contract information for normal execution and review."

    - id: "ARCH-REFERENCE-NOT-CONTRACT"
      statement: "docs/reference may explain the contract but must not be the only source of required task behavior."

    - id: "ARCH-AGENTS-FOR-OPERATIONS"
      statement: "ACP procedures, review handoff commands, and agent operation rules belong in AGENTS.md."

    - id: "ARCH-INTEGRATED-NOT-LANDED"
      statement: "Integrated means integration evidence exists; it does not imply landed or pushed."

    - id: "ARCH-ROLE-NOT-SECURITY"
      statement: "HARNESS_ROLE is an orchestration boundary, not a security boundary."

scope_policy:
  allowed_paths:
    semantics: "expected_impact_area"
    hard_gate: false
    rule: >
      allowed_paths describes the expected impact area for planning and review.
      A change outside allowed_paths is not automatically blocked, but it must
      be explained, impact-estimated, and reviewed.

  forbidden_paths:
    semantics: "blocked_area"
    hard_gate: true
    rule: >
      Any candidate change touching forbidden_paths must be blocked unless the
      task explicitly exists to change that forbidden rule and policy allows it.

  impact_estimation:
    rule: >
      When path impact is unclear or a change escapes allowed_paths, use the
      repository's path-impact estimation tool when available and include the
      result in review evidence.

task_contract:
  required_information:
    - task_id
    - goal
    - architecture
    - scope
    - protected_invariants
    - acceptance
    - adversarial_acceptance
    - expected_evidence
    - review_request

  missing_required_information_result: "rework"

  format_policy:
    strict_schema_required: false
    rule: >
      Field names and structure may vary if meaning is clear. However, missing
      required information, contradictory instructions, or reference-only
      completion criteria require rework.

  task_must_not:
    - redefine_repo_wide_policy
    - make_optional_reference_docs_required_by_accident
    - place_ACP_or_review_handoff_operational_protocols_in_task_yaml
    - treat_allowed_paths_as_a_hard_gate
    - weaken_forbidden_paths_without_explicit_policy_task

review:
  default_posture: "adversarial_counterexample_search"
  rule: >
    Review should search for the cheapest counterexample that invalidates the
    architecture, task contract, implementation, test evidence, or scope claim.

  stages:
    architecture_review:
      timing: "before_or_early_implementation"
      purpose: >
        Evaluate whether the proposed architecture, task decomposition,
        invariants, scope model, and acceptance/adversarial tests are sufficient.
      reviewer_must_evaluate:
        - "Does the architecture section contain enough information to reason about the change?"
        - "Are protected invariants explicit and relevant?"
        - "Do acceptance criteria cover both normal behavior and failure behavior?"
        - "Do adversarial inputs test robustness rather than only happy paths?"
        - "Are forbidden paths blocked?"
        - "Are allowed_paths treated as expected impact, not as a hard gate?"
        - "Is the path-impact estimate present when scope is unclear?"
        - "Are ACP and review handoff details delegated to AGENTS.md?"

    code_review:
      timing: "after_implementation"
      purpose: >
        Evaluate actual code, tests, evidence, and robustness after implementation.
      reviewer_must_evaluate:
        - "Does the implementation preserve the stated architecture and invariants?"
        - "Do tests prove the acceptance criteria?"
        - "Do tests include adversarial, malformed, missing, contradictory, or scope-escaping inputs where relevant?"
        - "Does the code avoid gate gaming, verifier weakening, or policy weakening?"
        - "Are forbidden paths untouched?"
        - "Are out-of-allowed-path changes justified with impact evidence?"
        - "Is evidence fresh relative to the candidate diff?"
        - "Are failures reported as rework or block with clear labels?"

  verdicts:
    - pass
    - rework
    - block

  blocking_labels:
    - forbidden_path
    - missing_required_yaml_information
    - architecture_gap
    - invariant_gap
    - acceptance_gap
    - adversarial_test_gap
    - missing_repro
    - stale_evidence
    - scope_risk
    - policy_weakening
    - gate_gaming
    - operation_protocol_leak

references:
  default: "optional"
  rule: >
    Reference docs are supplemental. Broken optional references should not block
    normal work if the inline contract is complete. Required references may
    block only when explicitly marked required by the task.
```

---

## `.harness/tasks/<task_id>/task.yaml` 案

これは、今回の方針を実装・検証するための task としての例です。

```yaml
schema_version: 1
task_id: "p0-policy-task-contract-refinement"
task_kind: "control_plane_refinement"

goal:
  summary: >
    Refine policy.yaml and task.yaml contracts so normal harness work is
    self-contained, architecture-aware, adversarially reviewable, and not
    dependent on docs/reference for completion-critical information.

  done_when:
    - "policy.yaml defines repo-wide policy, architecture invariants, scope semantics, and staged review posture."
    - "task.yaml defines task-specific architecture, invariants, acceptance criteria, adversarial acceptance, evidence, and review request."
    - "ACP and review handoff operational details are delegated to AGENTS.md."
    - "allowed_paths is treated as expected impact scope, not a hard gate."
    - "forbidden_paths is treated as blocking."
    - "Missing required YAML information results in rework."
    - "Format variance is tolerated when semantic information is complete."

non_goals:
  - "Do not make YAML structure fully machine-verification-first."
  - "Do not move ACP commands or detailed review handoff procedures into policy.yaml or task.yaml."
  - "Do not treat allowed_paths as a blocking gate."
  - "Do not make docs/reference required for normal task execution."
  - "Do not duplicate repo-wide policy inside individual task files."

policy:
  source: ".harness/policy.yaml"
  applicable_policy_ids:
    - "ARCH-CONTROL-PLANE-TRACKED"
    - "ARCH-RUNTIME-NOT-TRACKED"
    - "ARCH-TASK-CONTRACT-SELF-CONTAINED"
    - "ARCH-REFERENCE-NOT-CONTRACT"
    - "ARCH-AGENTS-FOR-OPERATIONS"
    - "ARCH-INTEGRATED-NOT-LANDED"

architecture:
  summary: >
    Split the harness contract into three layers: policy.yaml for repo-wide
    policy, task.yaml for task-specific contracts, and AGENTS.md for operational
    agent procedures. Review becomes a two-stage process: architecture review
    before or during design, and code review after implementation.

  components:
    - id: "GLOBAL-POLICY"
      responsibility: >
        Holds repo-wide architecture invariants, scope semantics, review posture,
        and required task information rules.
      primary_paths:
        - ".harness/policy.yaml"

    - id: "TASK-CONTRACT"
      responsibility: >
        Holds task-specific goal, architecture, expected impact, forbidden paths,
        protected invariants, acceptance criteria, adversarial acceptance, and
        review request.
      primary_paths:
        - ".harness/tasks/**/task.yaml"

    - id: "OPERATIONAL-PROTOCOLS"
      responsibility: >
        Holds ACP usage, review handoff procedures, command-level workflow, and
        agent operation rules.
      primary_paths:
        - "AGENTS.md"

    - id: "OPTIONAL-REFERENCE"
      responsibility: >
        Provides deeper explanation for unusual, high-risk, or harness-internal
        work. It is not the primary contract for normal tasks.
      primary_paths:
        - "docs/reference/**"

    - id: "REVIEW-FLOW"
      responsibility: >
        Separates architecture review from implementation/code review.
      stages:
        - architecture_review
        - code_review

  design_rules:
    - id: "DESIGN-POLICY-TASK-SEPARATION"
      statement: "Repo-wide rules stay in policy.yaml; task-specific rules stay in task.yaml."

    - id: "DESIGN-AGENTS-OWNS-OPERATIONS"
      statement: "ACP and review handoff operational procedures belong in AGENTS.md."

    - id: "DESIGN-REFERENCE-LIGHT"
      statement: "docs/reference is optional support, not the default contract path."

    - id: "DESIGN-REVIEW-TWO-STAGE"
      statement: "Architecture review evaluates design and tests; code review evaluates implementation and robustness."

scope:
  allowed_paths:
    - ".harness/policy.yaml"
    - ".harness/tasks/**/task.yaml"
    - ".harness/review.yaml"
    - ".harness/semantic_ai_reviewer.py"
    - "src/workflow_core/contract_harness/**"
    - "AGENTS.md"
    - "README.md"
    - "docs/reference/**"
    - "tests/**"

  allowed_paths_semantics:
    hard_gate: false
    meaning: >
      These are the expected impact paths. Changes outside this list require
      explanation and path-impact review, but are not automatically blocked.

  forbidden_paths:
    - "harness-runtime/**"
    - ".harness/state/**"
    - ".serena/**"
    - "**/*secret*"
    - "**/*credential*"
    - "**/*token*"
    - "**/*.pem"
    - "**/*.key"

  forbidden_paths_semantics:
    hard_gate: true
    meaning: >
      Candidate changes touching these paths are blocking unless this task is
      explicitly rewritten as an approved policy exception task.

  impact_estimation:
    required_when:
      - "candidate changes paths outside allowed_paths"
      - "candidate changes review, gate, verifier, or policy behavior"
      - "candidate changes task packet generation"
      - "reviewer cannot determine the architectural blast radius"
    evidence: "Include path-impact estimation output or a clear manual impact analysis."

protected_invariants:
  - id: "INV-POLICY-IS-GLOBAL"
    statement: "Repo-wide constraints are defined in policy.yaml, not duplicated in task.yaml."

  - id: "INV-TASK-IS-SPECIFIC"
    statement: "Task-specific architecture, invariants, acceptance, adversarial inputs, and review request are defined in task.yaml."

  - id: "INV-AGENTS-OWNS-HANDOFF-AND-ACP"
    statement: "ACP and review handoff operational procedures are maintained in AGENTS.md."

  - id: "INV-REFERENCE-NOT-REQUIRED-COMMON-PATH"
    statement: "docs/reference is not required for normal writer/reviewer/integrator work."

  - id: "INV-REQUIRED-MISSING-MEANS-REWORK"
    statement: "If required YAML information is missing, the result is rework."

  - id: "INV-FORMAT-VARIANCE-TOLERATED"
    statement: "Equivalent field shapes are acceptable if the required meaning is present."

  - id: "INV-ALLOWED-PATHS-NOT-HARD-GATE"
    statement: "allowed_paths is a planning/review signal, not a hard gate."

  - id: "INV-FORBIDDEN-PATHS-BLOCK"
    statement: "forbidden_paths is blocking."

  - id: "INV-REVIEW-TWO-STAGE"
    statement: "Reviewer request distinguishes architecture review from code review."

  - id: "INV-ADVERSARIAL-ACCEPTANCE"
    statement: "Acceptance must include invariant checks and adversarial or malformed inputs where relevant."

acceptance:
  criteria:
    - id: "ACCEPT-POLICY-HAS-REPO-WIDE-CONTRACT"
      claim: >
        policy.yaml contains repo-wide architecture invariants, scope semantics,
        review posture, and missing-information behavior.
      evidence:
        - "policy.yaml diff"
        - "review showing global/task/operation separation"
      adversarial_checks:
        - input: "Move repo-wide invariant only into task.yaml."
          expected: "rework: duplicated or misplaced global policy"
        - input: "Remove missing-required-information behavior from policy.yaml."
          expected: "rework: missing required YAML policy"
        - input: "Make allowed_paths a hard block in policy.yaml."
          expected: "rework: violates allowed_paths semantics"

    - id: "ACCEPT-TASK-HAS-TASK-SPECIFIC-ARCHITECTURE"
      claim: >
        task.yaml contains enough architecture information for a reviewer to
        evaluate the design without opening docs/reference.
      evidence:
        - "task.yaml architecture section"
        - "architecture review packet or equivalent reviewer input"
      adversarial_checks:
        - input: "Architecture section contains only a docs/reference link."
          expected: "rework: architecture_gap"
        - input: "Architecture omits affected components."
          expected: "rework: architecture_gap"
        - input: "Architecture contradicts policy.yaml boundaries."
          expected: "block or rework depending on severity"

    - id: "ACCEPT-INVARIANTS-AND-ADVERSARIAL-INPUTS"
      claim: >
        Acceptance criteria include protected invariants and adversarial inputs,
        not only happy-path checks.
      evidence:
        - "acceptance criteria list"
        - "adversarial checks list"
        - "tests or manual review evidence"
      adversarial_checks:
        - input: "Missing required task field."
          expected: "rework"
        - input: "Malformed YAML shape but all required meaning is present."
          expected: "accepted or reviewer-note, not automatic failure"
        - input: "Reference-only acceptance criteria."
          expected: "rework: acceptance_gap"
        - input: "Contradictory allowed/forbidden path instruction."
          expected: "rework or block"

    - id: "ACCEPT-SCOPE-SEMANTICS"
      claim: >
        allowed_paths is advisory expected impact scope; forbidden_paths is
        blocking.
      evidence:
        - "scope section in task.yaml"
        - "policy.yaml scope_policy section"
        - "path-impact estimate when needed"
      adversarial_checks:
        - input: "Candidate modifies path outside allowed_paths with explanation and impact estimate."
          expected: "review required; not automatically blocked"
        - input: "Candidate modifies path outside allowed_paths without explanation."
          expected: "rework: scope_risk"
        - input: "Candidate modifies forbidden path."
          expected: "block: forbidden_path"
        - input: "Candidate weakens forbidden_paths to pass."
          expected: "block: policy_weakening or gate_gaming"

    - id: "ACCEPT-AGENTS-OWNS-ACP-AND-HANDOFF"
      claim: >
        ACP and review handoff operational procedures are migrated to AGENTS.md,
        while policy.yaml/task.yaml only reference that operational source.
      evidence:
        - "AGENTS.md section for ACP and review handoff"
        - "policy.yaml operation_protocols source"
        - "task.yaml does not duplicate command-level protocol"
      adversarial_checks:
        - input: "ACP command details exist only in task.yaml."
          expected: "rework: operation_protocol_leak"
        - input: "Review handoff commands are duplicated inconsistently between AGENTS.md and task.yaml."
          expected: "rework: contradictory operation protocol"
        - input: "AGENTS.md lacks ACP/review handoff procedure after migration."
          expected: "rework: missing operational protocol"

    - id: "ACCEPT-TWO-STAGE-REVIEW"
      claim: >
        Reviewer instructions distinguish architecture review from code review.
      evidence:
        - "policy.yaml review.stages"
        - "task.yaml review_request"
        - "generated review packet or reviewer-facing summary"
      adversarial_checks:
        - input: "Reviewer is asked only to approve code without architecture/test review."
          expected: "rework: architecture_review_missing"
        - input: "Architecture review ignores test adequacy."
          expected: "rework: adversarial_test_gap"
        - input: "Code review ignores adversarial input handling."
          expected: "rework: adversarial_test_gap"

    - id: "ACCEPT-NO-GATE-GAMING"
      claim: >
        Candidate must not pass by weakening policy, verifier, review, tests,
        or gate behavior.
      evidence:
        - "diff review"
        - "test result"
        - "reviewer verdict"
      adversarial_checks:
        - input: "Candidate deletes failing adversarial tests."
          expected: "block: gate_gaming"
        - input: "Candidate changes reviewer labels to avoid block."
          expected: "block: policy_weakening"
        - input: "Candidate changes prepare/review behavior to downgrade required missing fields from rework to pass."
          expected: "block: gate_gaming"

expected_evidence:
  required:
    - id: "EVIDENCE-DIFF-SUMMARY"
      description: "Summarize changed policy/task/AGENTS/review files."

    - id: "EVIDENCE-ARCHITECTURE-REVIEW"
      description: "Reviewer or author explains architecture fit, invariants, and test adequacy."

    - id: "EVIDENCE-CODE-REVIEW"
      description: "After implementation, reviewer evaluates actual code, tests, and adversarial robustness."

    - id: "EVIDENCE-SCOPE"
      description: "List changed paths and explain any change outside allowed_paths."

    - id: "EVIDENCE-PATH-IMPACT"
      description: "Include path-impact estimate when scope is unclear or out-of-allowed-path changes exist."

    - id: "EVIDENCE-TESTS"
      description: "Include commands or manual evidence proving acceptance and adversarial checks."

review_request:
  architecture_review:
    ask: >
      Evaluate whether the architecture, contract split, task invariants,
      acceptance criteria, adversarial inputs, and scope semantics are adequate
      before implementation is treated as acceptable.
    must_answer:
      - "Is the policy/task/AGENTS separation clean?"
      - "Is the architecture information sufficient?"
      - "Are protected invariants explicit?"
      - "Are acceptance criteria meaningful and reviewable?"
      - "Do adversarial checks cover malformed, missing, contradictory, and scope-escaping inputs?"
      - "Are allowed_paths and forbidden_paths semantics correct?"
      - "Is path-impact estimation requested where appropriate?"

  code_review:
    ask: >
      After implementation, evaluate the actual diff, tests, evidence, and
      behavior under adversarial inputs.
    must_answer:
      - "Does the implementation preserve the stated invariants?"
      - "Does it avoid moving ACP/review handoff details back into YAML?"
      - "Does it treat missing required YAML information as rework?"
      - "Does it tolerate harmless format variance?"
      - "Does it block forbidden_paths?"
      - "Does it avoid hard-gating allowed_paths?"
      - "Does it resist gate gaming, stale evidence, and policy weakening?"
      - "Are tests and evidence fresh and sufficient?"

references:
  optional:
    - path: "docs/reference/**"
      use_when: >
        Use only for deeper rationale, unusual failures, or harness-internal
        implementation details. Do not rely on this as the only source of
        completion-critical task requirements.
```

---

## 重要な調整点

前回案から大きく変えるべき点は、`policy.yaml` / `task.yaml` に ACP や handoff の具体コマンドを持たせすぎないことです。あなたの方針では、そこは `AGENTS.md` に移管するのが自然です。

そのため、YAML 側には次の程度だけ残すのがよいです。

```yaml
operation_protocols:
  source: "AGENTS.md"
  includes:
    - ACP
    - review_handoff
    - agent_commands
```

一方で、review の観点そのものは `policy.yaml` と `task.yaml` に残すべきです。理由は、reviewer が何を評価するべきかは task contract の一部だからです。

特に今回の設計では、reviewer への依頼を次の 2 段階に分けるのが中核です。

```text
Architecture review:
  アーキテクチャ、影響範囲、不変条件、受け入れ条件、攻撃的テストの妥当性を評価する。

Code review:
  実装後のコード、テスト、証跡、攻撃的入力への耐性、scope 逸脱、gate gaming を評価する。
```

---

## さらに整理するならフィールド名はこうすると安定します

既存との互換性を優先するなら `allowed_paths` のままでよいですが、意味の誤解を避けるなら将来的には以下のようにするのもありです。

```yaml
scope:
  expected_paths:
    - "..."
  forbidden_paths:
    - "..."
```

ただし、既存の文脈で `allowed_paths` がすでに使われているなら、すぐ改名せずに以下の明示を入れる方が安全です。

```yaml
allowed_paths_semantics:
  hard_gate: false
  meaning: "expected impact area, not a blocking gate"
```

今回の方針では、この明示がかなり重要です。`allowed_paths` という名前だけだと、reviewer や gate 実装が hard gate と誤解しやすいためです。
