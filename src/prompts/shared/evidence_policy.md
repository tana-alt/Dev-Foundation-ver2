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
