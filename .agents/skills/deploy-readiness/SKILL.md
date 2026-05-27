---
name: deploy-readiness
description: "Use when changing deployment, Docker, CI/CD, environment variables, build output, runtime config, health checks, or release process."
---


## Purpose

Prevent deployment regressions caused by configuration, packaging, runtime, or release-process changes.

## Use when

- Dockerfile, CI/CD, deployment scripts, env vars, or runtime config change.
- GitHub Actions or CI checks that affect build, test, release, or deployment
  readiness change.
- A build or production startup behavior changes.
- Health checks, rollback, monitoring, or release commands are touched.

## Success conditions

- Build and startup path are clear.
- Required env vars are documented without secret values.
- Health check or smoke test exists when repo pattern supports it.
- Rollback or mitigation path is clear for risky changes.
- Runtime image and permissions follow repo security expectations.

## GitHub Actions / CI mode

Use this thin mode only when CI remains part of release or deploy readiness.

- Confirm changed workflows run the repo's required checks.
- Avoid broadening permissions, token access, caches, or artifacts without a
  readiness reason.
- Keep secrets out of workflow logs and generated artifacts.
- Record which local command maps to the changed CI job when a mapping exists.
- Require human review before operational use of release/deploy workflow
  changes.

## Constraints

- Do not bake secrets into images, scripts, logs, or config.
- Do not use floating `latest` tags unless repo policy allows it.
- Do not run as root in containers unless justified.
- Do not include dev dependencies in production artifacts unless necessary.
- Do not change deployment policy during unrelated feature work.

## Output

- Deploy risk summary.
- Commands checked.
- Env/config changes.
- Blockers.
