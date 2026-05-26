# Specialist Agent Workflow Design

## Purpose

AGENTS.md のフローを、インターン課題として説明しやすい専門エージェント設計へ落とし込む。完成スコープは「決算情報を構造化し、複数視点から読み解き、EPS と FCF の将来性を中心に readable な分析レポートへ落とすこと」である。

最終 LLM agent 数は 7 つにする。9-agent 案は context isolation だけを見ると明快だが、EPS/P&L と CFS/BS はそれぞれ読む文脈が大きく重なる。インターン課題では、分離の明快さよりも、実装可能な schema 数、handoff の少なさ、重複 context の削減を優先する。

## Design Principles

- 独立させる基準は agent 名ではなく、必要な context と判断軸が違うかどうか。
- context が強く重なる agent は統合し、同じ資料の重複読みを避ける。
- EPS と FCF は良し悪しが逆方向に出ることがあるため、Financial 内でも 2 系統に分ける。
- Management intent と guidance は近いが、経営方針の解釈と来期数値目標の現実性評価は別なので独立させる。
- Bull と Bear は同じ `AnalysisBrief` を見ても目的が逆なので、反対根拠を強くするため独立させる。
- Data ingestion、財務計算、document sectioning、Markdown rendering は LLM agent にしない。
- すべての agent 出力は Pydantic で検証する。
- Judge に全文資料や全文討論ログを渡さず、圧縮済みの構造化出力だけを渡す。
- `good | neutral | bad` を正式な判定ラベルにする。
- 反対根拠が空のまま report 生成へ進めない。
- 投資助言、株価予測、売買推奨に踏み込まない。

## Recommended Implementation Workflow

```text
RunSpec
  - ticker
  - fiscal quarter
  - source URLs / local documents

        ↓

Non-LLM Data Workflow
  - financial API data fetch
  - filing / presentation / transcript fetch
  - PDF / HTML / text sectioning
  - EPS surprise, revenue surprise, margins, CFO, FCF, CapEx changes
  - output: FinancialSnapshot + DocumentSections

        ↓

Financial Specialist Agents
  - EarningsQualityAnalyst
  - CashFlowRiskAnalyst

        ↓

Presentation Specialist Agents
  - ManagementIntentAnalyst
  - GuidanceAnalyst

        ↓

Evidence Aggregation
  - deterministic Python aggregation
  - output: AnalysisBrief

        ↓

Debate Agents
  - BullAgent
  - BearAgent(with BullCaseSummary)

        ↓

Judge Agent
  - good / neutral / bad
  - confidence
  - positive evidence
  - negative evidence
  - EPS outlook
  - FCF outlook

        ↓

Markdown Renderer
  - deterministic Python template
```

実装スコープの LLM agent は 7 つ。

1. `EarningsQualityAnalyst`
2. `CashFlowRiskAnalyst`
3. `ManagementIntentAnalyst`
4. `GuidanceAnalyst`
5. `BullAgent`
6. `BearAgent`
7. `JudgeAgent`

これは AGENTS.md の専門エージェント構造を保ちながら、context engineering 上の重複を削った完成スコープである。

## Why Seven Agents

| 統合/独立 | 判断 | 理由 |
| --- | --- | --- |
| EPS + P&L | 統合 | EPS の持続性は revenue、margin、segment mix、opex、tax/share count、一時要因を同時に見て判断するため |
| CFS + BS | 統合 | FCF の将来性は CapEx、working capital、liquidity、debt、maturity と同じ cash/risk context で判断するため |
| EPS/P&L + CFS/BS | 分離 | EPS は会計利益、FCF は現金創出力。EPS beat でも FCF 悪化はあり得るため |
| Management + Guidance | 分離 | 経営方針と来期数値目標の現実性は別の判断。混ぜると narrative に guidance 評価が引っ張られる |
| Bull + Bear | 分離 | 片方の立場に引っ張られ、反対根拠が薄くなりやすい |
| Judge + Report | 分離 | 構造化判断と文章整形が混ざると Pydantic 契約が崩れやすい |

## Agent Decisions

| AGENTS.md の要素 | 判断 | 提出スコープでの扱い |
| --- | --- | --- |
| Data Ingestion Layer | 残すが非LLM | Python処理。外部取得、sectioning、計算を担当 |
| EPS Analyst | 統合 | `EarningsQualityAnalyst` の EPS quality 領域 |
| P&L Analyst | 統合 | `EarningsQualityAnalyst` の profitability 領域 |
| CFS Analyst | 統合 | `CashFlowRiskAnalyst` の cash generation 領域 |
| BS Analyst | 統合 | `CashFlowRiskAnalyst` の liquidity/risk 領域 |
| Management eval Agent | 独立 | `ManagementIntentAnalyst` |
| Guidance Agent | 独立 | `GuidanceAnalyst` |
| Bull Agent | 独立 | `BullAgent` |
| Bear Agent | 独立 | `BearAgent` |
| Risk Agent | 削る | 各分析Agent、`CashFlowRiskAnalyst`、`BearAgent` の `risks` / `counter_evidence` に吸収 |
| Eval Agent | 削る | `JudgeAgent` と責務が重複 |
| Judge / Report Agent | 分離 | 判断は `JudgeAgent`、Markdown 整形は Python |
| Macro Agent | 対象外 | AGENTS.md の主目的である EPS / FCF / 決算評価から外れるため実装対象に含めない |

## Pydantic Contracts

### Core Data Models

```python
RunSpec:
  ticker: str
  fiscal_quarter: str
  filing_url: str | None
  presentation_url: str | None
  transcript_url: str | None

FinancialSnapshot:
  ticker: str
  fiscal_quarter: str
  revenue_actual: float | None
  revenue_consensus: float | None
  revenue_surprise_pct: float | None
  eps_actual: float | None
  eps_consensus: float | None
  eps_surprise_pct: float | None
  eps_yoy_pct: float | None
  gross_margin: float | None
  operating_margin: float | None
  operating_margin_yoy_delta: float | None
  operating_cash_flow: float | None
  free_cash_flow: float | None
  fcf_margin: float | None
  capex: float | None
  working_capital_change: float | None
  cash: float | None
  debt: float | None
  guidance_summary: str | None

DocumentSection:
  source_type: financial_api | filing | presentation | transcript
  section_type: revenue | eps | margin | cash_flow | capex | balance_sheet | guidance | management_commentary | risk | other
  source_ref: str
  text: str
```

### Shared Evidence Model

```python
EvidenceItem:
  claim: str
  source_type: financial_api | filing | presentation | transcript | consensus_delta | other_provided_context
  source_ref: str
  metric: str | None
  value: float | str | None
  period: str | None
  quote_or_value: str
  interpretation: str
  polarity: supporting | counter | mixed | neutral
```

### Specialist Outputs

```python
EarningsQualityFinding:
  agent_name: Literal["EarningsQualityAnalyst"]
  stance: positive | negative | mixed | neutral | unclear
  eps_surprise_assessment: object
  quality_of_earnings: object
  revenue_quality: object
  margin_trend: object
  operating_leverage: object
  segment_mix_effect: object
  eps_outlook_signal: object
  fcf_implication: object
  key_evidence: list[EvidenceItem]
  counter_evidence: list[EvidenceItem]
  confidence: float
  missing_data: list[str]
  handoff_summary: str

CashFlowRiskFinding:
  agent_name: Literal["CashFlowRiskAnalyst"]
  stance: positive | negative | mixed | neutral | unclear
  fcf_trend_assessment: object
  cash_conversion_assessment: object
  capex_assessment: object
  working_capital_effect: object
  liquidity_assessment: object
  leverage_or_financing_risk: object
  fcf_outlook_signal: object
  eps_constraint: object
  key_evidence: list[EvidenceItem]
  counter_evidence: list[EvidenceItem]
  confidence: float
  missing_data: list[str]
  handoff_summary: str

ManagementIntentFinding:
  agent_name: Literal["ManagementIntentAnalyst"]
  stance: positive | negative | mixed | neutral | unclear
  summary: str
  management_priorities: list[ManagementPriority]
  strategic_drivers: list[StrategicDriver]
  investment_actions: list[InvestmentAction]
  eps_implication: object
  fcf_implication: object
  key_evidence: list[EvidenceItem]
  counter_evidence: list[EvidenceItem]
  risks: list[RiskItem]
  confidence: float
  missing_data: list[str]
  handoff_summary: str

GuidanceFinding:
  agent_name: Literal["GuidanceAnalyst"]
  stance: positive | negative | mixed | neutral | unclear
  guidance_vs_consensus: object
  conservatism_level: conservative | balanced | aggressive | mixed | unclear
  assumption_quality: object
  revision_risk: object
  eps_implication: object
  fcf_implication: object
  key_evidence: list[EvidenceItem]
  counter_evidence: list[EvidenceItem]
  confidence: float
  missing_data: list[str]
  handoff_summary: str
```

### Debate and Judge Outputs

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

BullCase:
  thesis: str
  strongest_positive_evidence: list[EvidenceItem]
  finding_coverage: dict
  eps_bull_argument: str
  fcf_bull_argument: str
  conditions_needed: list[str]
  weak_points: list[str]
  confidence: float

BearCase:
  thesis: str
  strongest_negative_evidence: list[EvidenceItem]
  finding_coverage: dict
  eps_bear_argument: str
  fcf_bear_argument: str
  failure_modes: list[str]
  counter_to_bull_case: list[str]
  confidence: float

FinalVerdict:
  label: good | neutral | bad
  confidence: float
  summary: str
  positive_evidence: list[EvidenceItem]
  negative_evidence: list[EvidenceItem]
  eps_outlook: positive | negative | neutral | mixed | unclear
  eps_outlook_reason: str
  fcf_outlook: positive | negative | neutral | mixed | unclear
  fcf_outlook_reason: str
  non_advice_disclaimer: str
```

## Agent Responsibilities

### EarningsQualityAnalyst

EPS surprise の大きさだけでなく、EPS beat / miss の質、P&L の売上品質、利益率、営業レバレッジ、segment mix を見る。

Inputs:

- EPS actual / consensus / surprise
- revenue actual / consensus / growth
- gross margin / operating margin
- tax and share-count values where available
- one-time item sections
- revenue / margin / segment sections

Outputs:

- EPS surprise assessment
- quality of earnings
- revenue quality
- margin trend
- operating leverage
- segment mix effect
- EPS outlook signal
- P&L-derived FCF implication
- counter evidence

### CashFlowRiskAnalyst

FCF が将来増加する方向にあるかを、CFO、FCF、CapEx、working capital、liquidity、debt、maturity から見る。

Inputs:

- operating cash flow
- free cash flow
- CapEx
- working capital changes
- cash and equivalents
- debt and lease obligations
- liquidity / debt / capital resources sections

Outputs:

- FCF trend
- cash conversion assessment
- CapEx pressure
- working capital effect
- liquidity assessment
- leverage or financing risk
- FCF outlook signal
- EPS constraint from cash/risk
- counter evidence

### ManagementIntentAnalyst

経営陣が何を成長ドライバー、投資領域、コスト改善策として説明しているかを読む。

Inputs:

- presentation sections
- transcript / management commentary
- MD&A
- risk sections where relevant to management action

Outputs:

- management priorities
- strategic drivers
- investment or cost actions
- EPS / FCF implication by time horizon
- counter evidence

### GuidanceAnalyst

来期ガイダンスと市場期待の match / mismatch、前提の保守性や楽観性を見る。

Inputs:

- guidance summary
- precomputed consensus expectations and deltas
- guidance / outlook sections
- guidance assumption sections

Outputs:

- guidance versus consensus
- conservatism level
- assumption quality
- revision risk
- EPS / FCF implication
- counter evidence

### BullAgent

Validated findings だけを使い、良い決算と判断できる最強ケースを作る。

### BearAgent

Validated findings と compact `BullCaseSummary` だけを使い、悪い決算または neutral と判断できる最強ケースを作る。

### JudgeAgent

Bull / Bear の主張と `AnalysisBrief` をもとに最終判定を出す。Markdown は生成しない。

## Orchestrator Responsibilities

- Validate input ticker, quarter, and source configuration.
- Fetch and normalize data.
- Calculate financial metrics in Python.
- Split documents into typed sections.
- Route only relevant sections to each agent.
- Run independent specialist agents in parallel where possible.
- Validate every LLM response with Pydantic.
- Aggregate findings into `AnalysisBrief`.
- Reject outputs with empty `counter_evidence` where counter evidence is required.
- Run `BullAgent -> BearAgent(with BullCaseSummary)` sequentially, then pass both outputs to `JudgeAgent`.
- Pass only compact evidence and debate outputs to Judge.
- Render final Markdown with a deterministic Python template.
- Log each stage as structured events.

## Prompt Files

Runtime agent prompts live under `src/prompts/`:

- `src/prompts/financial/earnings_quality_analyst.md`
- `src/prompts/financial/cash_flow_risk_analyst.md`
- `src/prompts/presentation/management_intent_analyst.md`
- `src/prompts/presentation/guidance_analyst.md`
- `src/prompts/debate/bull_agent.md`
- `src/prompts/debate/bear_agent.md`
- `src/prompts/debate/judge_agent.md`

Shared policies:

- `src/prompts/shared/global_policy.md`
- `src/prompts/shared/evidence_policy.md`
- `src/prompts/shared/output_policy.md`

Review-only indexes:

- `src/prompts/index/financial_agents.md`
- `src/prompts/index/presentation_agents.md`
- `src/prompts/index/debate_judge_agents.md`

Index files are not runtime prompt inputs. Runtime loading must be one-agent scoped.

## Existing Code Alignment

The current implementation has `BullAnalyst`, `BearAnalyst`, `QuantsAnalyst`, and `MacroAnalyst`. For the AGENTS.md target workflow, these should not be treated as the final specialist set.

Required alignment:

- Replace `QuantsAnalyst` responsibility with `EarningsQualityAnalyst` and `CashFlowRiskAnalyst`.
- Replace `MacroAnalyst` responsibility with `ManagementIntentAnalyst` and `GuidanceAnalyst`, or remove macro-specific claims until peer/macro data is explicitly available.
- Keep `BullAnalyst` and `BearAnalyst` as debate-stage agents, not round-one analysts over raw filing sections.
- Change verdict label from `GOOD | MIXED | BAD` to `good | neutral | bad`.
- Keep report rendering in Python and update the template to match AGENTS.md output image.
