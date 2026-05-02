---
applyTo: ".github/workflows/**,Dockerfile,docker-compose*.yml,Makefile"
---

# Infra Instructions

- CI/CD、GitHub Actions、Docker、secret、auth 周りの変更は別承認対象とする
- merge gate は Human review + required CI pass を維持する
- AI review は補助 signal であり、block 条件として扱わない
- CI を変えるときは対応するローカル実行コマンドも docs に反映する
- 本番運用に trace / eval を導入する場合は `docs/evals/regression.md` を先に同期する
