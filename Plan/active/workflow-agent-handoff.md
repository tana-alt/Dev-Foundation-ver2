# Workflow Agent Handoff

## Scope

この要項書は、workflow 実装側へ渡す専門エージェント構成と実行順序を定義する。インターン課題の提出スコープとして、AGENTS.md の主要目的である EPS / FCF / 決算評価を完成対象に含める。

LLM agent は 7 つにする。多すぎる agent は context の重複、schema 増加、handoff 劣化を生むため、context が強く重なるものは統合する。

独立 LLM agent にしないもの:

- `DataIngestionAgent`: 外部取得、sectioning、計算は Python workflow。
- `RiskAgent`: 各 specialist の `counter_evidence` / `risks` と `BearAgent` に吸収。
- `EvalAgent`: 最終評価は `JudgeAgent` に一本化。
- `ReportAgent`: Markdown 生成は deterministic Python renderer。

## Agent Boundary Decision

| AGENTS.md の要素 | 判断 | 理由 |
| --- | --- | --- |
| EPS Analyst + P&L Analyst | 統合 | EPS の質は revenue、margin、segment mix、tax/share count、一時要因を同時に見ないと判断できない |
| CFS Analyst + BS Analyst | 統合 | FCF 判断は CapEx、working capital、liquidity、debt、maturity と不可分 |
| Management eval Agent | 独立 | 経営方針・投資判断・時間軸の解釈に集中させる |
| Guidance Agent | 独立 | guidance vs consensus、前提、revision risk は management narrative と混ぜると甘くなる |
| Bull Agent | 独立 | good 側の最強ケースを作る |
| Bear Agent | 独立 | bad/neutral 側の最強ケースと Bull への反論を作る |
| Judge / Report Agent | 分離 | 判断は `JudgeAgent`、整形は Python。LLM に report draft を作らせない |

Runtime LLM agents:

1. `EarningsQualityAnalyst`
2. `CashFlowRiskAnalyst`
3. `ManagementIntentAnalyst`
4. `GuidanceAnalyst`
5. `BullAgent`
6. `BearAgent`
7. `JudgeAgent`

## Workflow

```text
RunSpec
  - ticker
  - fiscal_quarter
  - source URLs or local source files

        ↓

Data Ingestion / Normalization  [Python]
  - fetch financial API data
  - fetch filing / presentation / transcript
  - split documents into typed DocumentSection objects
  - calculate EPS surprise, revenue surprise, margins, CFO, FCF, CapEx, liquidity values
  - output FinancialSnapshot + DocumentSections + SourceIndex

        ↓

Financial Agents  [parallel LLM calls]
  - EarningsQualityAnalyst
  - CashFlowRiskAnalyst

        ↓

Presentation Agents  [parallel LLM calls]
  - ManagementIntentAnalyst
  - GuidanceAnalyst

        ↓

Evidence Aggregation  [Python]
  - validate all findings with Pydantic
  - reject missing source_ref
  - reject empty counter_evidence unless missing_data records the limitation
    and confidence is capped at 0.60
  - compress findings into AnalysisBrief

        ↓

Debate Agents
  - BullAgent
  - build compact BullCaseSummary  [Python]
  - BearAgent(with BullCaseSummary)

        ↓

JudgeAgent
  - label: good | neutral | bad
  - confidence
  - positive_evidence
  - negative_evidence
  - eps_outlook
  - fcf_outlook

        ↓

MarkdownRenderer  [Python]
  - input: MarkdownRendererInput = RunSpec + FinalVerdict + SourceIndex(optional)
  - deterministic report formatting
```

`BullAgent -> BearAgent(with BullCaseSummary) -> JudgeAgent` is fixed. Bull and Bear are sequential so Bear can directly challenge the strongest Bull case.

## Agent List

| Agent | Purpose | Input Context | Output |
| --- | --- | --- | --- |
| `EarningsQualityAnalyst` | EPS surprise、売上品質、利益率、営業レバレッジ、segment mix、一時要因を統合して見る | EPS, revenue, margin, segment, operating expense, tax/share count, one-time item sections | `EarningsQualityFinding` |
| `CashFlowRiskAnalyst` | CFO、FCF、CapEx、working capital、liquidity、debt、maturity を統合して見る | cash_flow, capex, working_capital, liquidity, debt, maturity, capital_resources sections | `CashFlowRiskFinding` |
| `ManagementIntentAnalyst` | 経営陣の意図、投資判断、時間軸を読む | strategy, MD&A, CEO/CFO commentary, management sections | `ManagementIntentFinding` |
| `GuidanceAnalyst` | guidance と consensus の差分、前提、revision risk を見る | guidance sections, precomputed consensus deltas, assumptions | `GuidanceFinding` |
| `BullAgent` | good と判断できる最強ケースを作る | validated `AnalysisBrief` | `BullCase` |
| `BearAgent` | bad/neutral と判断すべき最強ケースを作る | validated `AnalysisBrief`, `BullCaseSummary` | `BearCase` |
| `JudgeAgent` | good/neutral/bad を構造化判定する | `AnalysisBrief`, `BullCase`, `BearCase` | `FinalVerdict` |

## Context Routing

各 agent に全文を渡さない。workflow は `DocumentSection.section_type` と `source_ref` を使って、必要な section だけを渡す。

```text
EarningsQualityAnalyst:
  - eps
  - revenue
  - margin
  - segment
  - operating_expense
  - tax
  - share_count
  - one_time_item

CashFlowRiskAnalyst:
  - cash_flow
  - capex
  - working_capital
  - liquidity
  - debt
  - maturity
  - capital_resources

ManagementIntentAnalyst:
  - management_commentary
  - strategy
  - mdna
  - risk when tied to management actions

GuidanceAnalyst:
  - guidance
  - outlook
  - guidance_assumptions
  - precomputed consensus deltas
```

## Context Isolation Rationale

- `EarningsQualityAnalyst`: EPS と P&L は同じ earnings quality context を使う。分けると同じ資料を重複読みし、EPS beat と margin trend の整合性が落ちる。
- `CashFlowRiskAnalyst`: CFS と BS は FCF outlook の同じ cash/risk context を使う。分けると CapEx/working capital と liquidity/debt constraint の接続が弱くなる。
- `ManagementIntentAnalyst`: 経営意図を評価するため、戦略、投資判断、CEO/CFO commentary に限定する。
- `GuidanceAnalyst`: 将来数値目標の妥当性を評価するため、guidance、前提、consensus delta に限定する。
- `BullAgent` / `BearAgent`: 反対方向の主張を分離し、肯定根拠と否定根拠を独立して強くする。
- `JudgeAgent`: 最終構造化判定のみを担当し、Markdown 生成や追加調査を行わない。

## Required Models

Core models:

```python
RunSpec
FinancialSnapshot
DocumentSection
SourceIndex
EvidenceItem
```

`EvidenceItem` minimal fields:

```python
EvidenceItem:
  source_ref: str
  source_type: str
  claim: str
  metric: str | None
  period: str | None
  quote_or_value: str
  interpretation: str
  polarity: str
```

Specialist outputs:

```python
EarningsQualityFinding
CashFlowRiskFinding
ManagementIntentFinding
GuidanceFinding
AnalysisBrief
BullCase
BearCase
FinalVerdict
```

`AnalysisBrief` must contain:

```python
AnalysisBrief:
  ticker: str
  fiscal_quarter: str
  earnings_quality_finding: EarningsQualityFinding
  cash_flow_risk_finding: CashFlowRiskFinding
  management_intent_finding: ManagementIntentFinding
  guidance_finding: GuidanceFinding
  positive_evidence_pool: list[EvidenceItem]
  negative_evidence_pool: list[EvidenceItem]
  disputed_points: list[str]
  missing_data: list[str]
```

Debate coverage field:

```python
finding_coverage: dict[
  Literal[
    "earnings_quality",
    "cash_flow_risk",
    "management_intent",
    "guidance",
  ],
  Literal["supporting", "opposing", "not_material", "missing"],
]
```

`supporting` / `opposing` are relative to the current debate agent's thesis.

Renderer input:

```python
MarkdownRendererInput = RunSpec + FinalVerdict + SourceIndex(optional)
```

## Validation Gates

Before aggregation:

- Pydantic validation must pass.
- `confidence` must be `0.0 <= confidence <= 1.0`.
- Evidence items must include `source_ref`.
- Agents must not output stock forecasts, target prices, or trading advice.
- Agents must not calculate metrics from raw values.
- Run a banned phrase scan for investment-advice language such as `buy`, `sell`, `hold`, `target price`, `price target`, `undervalued`, and `overvalued`.

Before Judge:

- `AnalysisBrief` must include all four specialist findings.
- Positive and negative evidence pools must both be non-empty.
- `BullCase.strongest_positive_evidence` must be non-empty.
- `BullCase.finding_coverage` and `BearCase.finding_coverage` must include all four specialist keys.
- `BullCase.weak_points` must be non-empty.
- `BearCase.strongest_negative_evidence` must be non-empty.
- `BearCase.counter_to_bull_case` must be non-empty.
- Judge should prefer `neutral` when Bull and Bear are close.
- Judge should prefer `neutral` when EPS outlook and FCF outlook point in opposite directions.
- Important missing data should cap final confidence.
- `bad` requires negative evidence to clearly outweigh positive evidence, not merely one weak dimension.

Before report:

- `FinalVerdict.label` must be `good | neutral | bad`.
- `FinalVerdict.positive_evidence` must be non-empty.
- `FinalVerdict.negative_evidence` must be non-empty.
- `eps_outlook_reason` and `fcf_outlook_reason` must be non-empty.
- `non_advice_disclaimer` must be present.
- `MarkdownRendererInput` must equal `RunSpec + FinalVerdict + SourceIndex(optional)`.
- Run the banned phrase scan again on rendered Markdown with false-positive caution for quoted source text.

## Prompt References

Runtime prompt composition:

```text
src/prompts/shared/global_policy.md
+ src/prompts/shared/evidence_policy.md
+ src/prompts/shared/output_policy.md
+ one agent prompt file
```

Agent prompt files:

- `src/prompts/financial/earnings_quality_analyst.md`
- `src/prompts/financial/cash_flow_risk_analyst.md`
- `src/prompts/presentation/management_intent_analyst.md`
- `src/prompts/presentation/guidance_analyst.md`
- `src/prompts/debate/bull_agent.md`
- `src/prompts/debate/bear_agent.md`
- `src/prompts/debate/judge_agent.md`

Index files under `src/prompts/index/` are review aids only and must not be loaded as runtime prompt input.
