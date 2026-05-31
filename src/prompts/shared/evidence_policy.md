# Evidence Policy

Apply this policy to every agent output.

## Evidence Requirements

Every evidence item must include:

- `source_ref`
- `source_type`
- `claim`
- `quote_or_value`
- `interpretation`
- `polarity`

`source_ref` must point to a routed source section or precomputed metric supplied
by the workflow. Do not invent source identifiers.

Copy `source_ref` from the supplied `source_index` exactly. Do not abbreviate,
rename, or generalize `source_id`. Do not create generic identifiers such as
`financial_api:<ticker>:<period>`. Preserve locator fields including
`url`, `document_id`, `section_id`, `metric_name`, `page`, and `title` when
present.

When `source_ref.source_type` is `financial_api` or `derived_metric`, the
`source_ref` object must include the exact `metric_name` from the supplied
precomputed metric source. Do not omit it and do not create a new metric name.

## Positive And Counter Evidence

Each specialist finding, Bull case, Bear case, and final verdict must consider
both supporting and opposing evidence.

If no meaningful counter evidence is available in the provided context:

- keep `counter_evidence` empty only if the schema allows it
- explain the limitation in `missing_data`
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
3. a `missing_data` caveat explaining why the claim cannot be numerically verified.

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
