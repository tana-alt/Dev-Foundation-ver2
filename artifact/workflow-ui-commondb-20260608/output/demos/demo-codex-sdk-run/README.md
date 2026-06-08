# Demo Codex SDK Run

This demo is a sanitized local fixture for the codex-runner lane. It shows the
shape of an approved work contract that can be handed to the headless adapter
without running the real Codex SDK, merging, deploying, mutating CI/CD, or
handling secrets.

Example local command:

```sh
uv run python scripts/run-approved-work-contract.py \
  artifact/workflow-ui-commondb-20260608/output/demos/demo-codex-sdk-run/approved-work-contract.yaml \
  --config templates/codex-sdk-run-config.yaml \
  --artifact-dir artifact/workflow-ui-commondb-20260608/output/demos/demo-codex-sdk-run/output
```
