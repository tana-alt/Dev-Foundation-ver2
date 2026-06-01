# Evidence Policy

Apply this policy to every agent output.

## Evidence Requirements

Use the frozen trace vocabulary. Do not invent alternate field names.

`ReportMatrix` groups `source_manifest`, `evidence_items`, `claim_records`,
`decision_uses`, and `missing_data_items`. Agent outputs are narrower than the
full matrix, but every evidence-bearing answer must stay compatible with these
names.

`EvidenceItem` fields are `evidence_id`, `polarity`, `summary`, `detail`,
`impact_areas`, `source_ref`, `metric_name`, `value`, `unit`, `quote`,
`reported_period`, `as_of_date`, `fact_check_status`, and `confidence`.

`ClaimRecord` fields are `claim_id`, `claim_type`, `agent_role`, `time_scope`,
`claim`, `evidence_ids`, `counter_evidence_ids`, `interpretation`,
`implication`, `confidence`, and `limitations`.

`DecisionUse` fields are `decision_use_id`, `treatment`, `claim_id`,
`decisive_evidence_ids`, `rationale`, `verdict_impact`, and
`confidence_impact`.

`MissingDataItem` fields are `missing_data_id`, `topic`, `reason`,
`materiality`, `requested_source_type`, and `blocks_verdict`.
`MissingDataItem` is report-matrix vocabulary, not a top-level field every role
can emit.

`SourceRef` fields are `source_id`, `source_type`, `title`, `url`,
`document_id`, `section_id`, `page`, `line_start`, `line_end`, `line_range`,
`metric_name`, `reported_period`, and `as_of_date`.

The workflow may provide `source_index` as a compact lookup view over
`source_manifest`. Treat `source_manifest` as the authoritative registration
set and copy `source_ref` from the supplied `source_index` exactly. Do not
abbreviate, rename, or generalize `source_id`. Do not create generic identifiers
such as `financial_api:<ticker>:<period>`. Preserve all locator fields that are
present.

When `source_ref.source_type` is `financial_api` or `derived_metric`, the
`source_ref` object must include the exact `metric_name` from the supplied
precomputed metric source. Do not omit it and do not create a new metric name.

Separate a verifiable `fact` from its `interpretation` and downstream
`implication`. Put the period or horizon in `time_scope` when producing claim
records, and mark source support with `fact_check_status`.

Schema literal values:

- `source_type`: `financial_api`, `derived_metric`, `earnings_presentation`,
  `filing`, `earnings_call`, `press_release`, `manual_upload`
- `polarity` / `verdict_impact`: `positive`, `negative`, `neutral`, `risk`
- `claim_type`: `fact`, `interpretation`, `forecast`, `risk`, `limitation`,
  `counterpoint`
- `fact_check_status`: `supported`, `partially_supported`, `contradicted`,
  `unverified`, `not_checkable`
- judge `treatment`: `decisive`, `supporting`, `counter_evidence`,
  `discounted`, `not_used`
- `materiality`: `low`, `medium`, `high`

## Positive And Counter Evidence

Each specialist finding, Bull case, Bear case, and final verdict must consider
both supporting and opposing evidence.

If no meaningful counter evidence is available in the provided context:

- keep `counter_evidence` empty only if the schema allows it
- use `missing_data` only when the role output contract includes `missing_data`
- otherwise describe material gaps inside allowed fields and lower `confidence`
- cap `confidence` at `0.60`

## Evidence Quality

- Prefer precomputed financial metrics for numeric claims.
- Prefer filing, presentation, and transcript sections with stable `source_ref`.
- Treat management narrative as a claim, not as proof.
- Do not use one source as evidence for unrelated fields.
- Do not turn absence of disclosure into a strong positive or negative claim.

## Confidence Caps

Use these caps unless a stricter schema-specific rule applies:

- one source type only: max `0.65`
- weak or ambiguous source references: max `0.50`
- important missing data: max `0.60`
- no usable counter evidence: max `0.60`
- conflicting EPS and FCF signals: max `0.70`

## Numeric Grounding Policy

Do not mechanically list every available metric.

However, every material analytical claim should be grounded by at least one of:

1. a precomputed metric value,
2. a direct source quote or disclosed value,
3. a schema-allowed limitation explaining why the claim cannot be numerically
   verified.

When using qualitative words such as strong, large, meaningful, improved,
deteriorated, beat, missed, margin expansion, pressure, concentration,
cash conversion, or investment intensity, include the most relevant routed value
or explicitly mark the claim as qualitative / unverified.

Do not calculate new metrics. Use only metric IDs and values supplied by the
workflow or directly disclosed values inside routed source sections.

## External Source Separation Policy

External web/news/analyst sources are not part of the default report workflow.
They must be handled as an interactive external-research appendix unless a human
explicitly accepts and routes them back into the workflow.

Classify external sources by timing before use:

- `contemporary_external`: near the earnings event date
- `post_event_external`: after the event and potentially hindsight-biased
- `stale_external`: before the event and not tied to the reported quarter
- `unknown`: date or timing cannot be verified

The main verdict should prefer same-period primary company sources, filings,
earnings releases, presentations, transcripts, and routed precomputed metrics.
