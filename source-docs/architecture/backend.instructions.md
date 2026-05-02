---
applyTo: "apps/api/**,src/graph/**,src/services/**,src/db/**,src/schemas/**"
---

# Backend Instructions

- `ARCHITECTURE.md` の dependency direction と hard boundaries を守る
- `apps/api/` は API surface の公開境界として扱い、内部都合を外へ漏らさない
- `src/graph/` は state machine と routing に集中し、service 実装責務を持たない
- `src/services/` は reusable domain service に限定し、`graph/` を逆参照しない
- `src/db/` は persistence に集中し、state 遷移責務を持たない
- schema や contract を変えるときは task docs と spec を同期する
- verifier fail は局所修正を優先する
- DB schema、auth、billing、secret、infra に触れる変更は Human gate 前提で進める
