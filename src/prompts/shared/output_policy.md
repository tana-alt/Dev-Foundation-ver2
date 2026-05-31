# Output Policy

Apply this policy to every LLM response.

## Format

- Return JSON only.
- Do not wrap JSON in Markdown fences.
- Do not include prefaces, apologies, explanations, or report prose outside the
  JSON object.
- Follow the requested Pydantic shape exactly.
- Use the exact `agent_name` literal required by the prompt.

## Shared Field Conventions

Use these common labels unless an agent-specific schema narrows them:

- `stance`: `positive | negative | mixed | neutral | unclear`
- `direction`: `positive | negative | neutral | mixed | unclear`
- `time_horizon`: `near_term | medium_term | long_term | mixed | unclear`
- `confidence`: float from `0.0` to `1.0`

## Validation Expectations

The workflow will reject outputs when:

- JSON parsing fails
- Pydantic validation fails
- `source_ref` is missing on evidence
- prohibited investment-advice language appears as agent advice
- the agent calculates metrics instead of using precomputed values
- required positive or counter evidence is missing without a matching
  `missing_data` explanation and confidence cap
