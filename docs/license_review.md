# License Review

## Current Decisions

- `vectorbt` is deferred, not permanently rejected. It is useful for fast
  parameter screening, but the current PyPI package describes the license as
  Apache 2.0 with Commons Clause, so it is not part of the core OSS dependency
  set.
- Freqtrade is not a core dependency because GPLv3 and bot-runtime state are a
  poor fit for this repo's contract-first foundation.
- Hummingbot full runtime stays outside this `uv` project. This repo tracks only
  API-boundary code and sanitized config templates until a dedicated executor
  lane is approved.

## Vectorbt Gate

Before adding a `screening-vectorbt` dependency group, complete a human license
review and decide whether Commons Clause is acceptable for this project. If it
is accepted, keep it optional and isolated from default CI and production
execution paths.

## Source Refs

- `artifact/Gpt-pro-review`
- https://pypi.org/project/vectorbt/

