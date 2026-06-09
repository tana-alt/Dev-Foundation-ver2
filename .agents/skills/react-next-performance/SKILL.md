---
name: react-next-performance
description: Use when React or Next.js changes touch server/client boundaries, data fetching, Suspense, caching, hydration, dynamic imports, bundle size, render frequency, expensive lists, or perceived responsiveness. Prefer official React and Next.js docs through doc-lookup; use Vercel guidance only as optional tactical review material.
metadata:
  source_attribution: "Replaces retired Vercel Engineering React Best Practices material; bulk imported rule payload removed."
---

# React Next Performance

Use this skill for performance-sensitive React and Next.js implementation or
review. This is a compact routing contract, not a local copy of framework docs.

Source attribution: the retired local skill imported Vercel Engineering React
Best Practices material. This replacement removes the bulk imported payload and
keeps Vercel guidance only as optional tactical review material.

## Effect

When this skill fires, make the React/Next performance-sensitive choice
explicit: identify the performance surface, preserve local architecture, check
official docs for version-sensitive behavior, and verify with the narrowest
useful evidence available.

## Workflow

1. Identify React/Next versions, router model, runtime, and whether code runs on
   the server, client, edge, or during build.
2. Use `doc-lookup` for official React and Next.js docs before relying on
   memory for version-sensitive APIs.
3. Inspect the local component/data-flow pattern before changing architecture.
4. Fix the highest-impact bottleneck first and keep changes scoped.
5. Verify with the closest lint/test/build or performance evidence available.

## Review Areas

- Priority order: async waterfalls and bundle size first, then server behavior,
  client data fetching, re-render control, rendering work, JavaScript hot paths,
  and advanced patterns only when evidence points there.
- Server/client component boundaries and serialized props.
- Data fetching, request deduplication, caching, invalidation, and waterfalls.
- Suspense, streaming, loading states, and perceived responsiveness.
- Hydration mismatches, client-only state, and browser-only APIs.
- Dynamic imports, package imports, third-party scripts, and bundle size.
- Render frequency, derived state, memoization, expensive lists, and event
  handlers.
- CSS, images, fonts, SVGs, and long-list rendering behavior.

Use external Vercel-style rule taxonomies as optional review prompts, not as a
local rule database. Do not import broad rule payloads into this compact repo.

## Do Not Use When

- The task is ordinary React/Next UI implementation without a stated or implied
  performance-sensitive surface; use `frontend-implementation`.
- The task is only visual polish, accessibility, focus, responsive overflow, or
  state-quality review; use `ui-quality-gate`.
- The task only needs current framework/API facts and no implementation or
  review decision; use `doc-lookup`.
- The task is broad release confidence rather than React/Next performance risk;
  use `release-check`.

## Constraints

- Do not cargo-cult `memo`, `useMemo`, or `useCallback`.
- Do not introduce new dependencies for performance unless the repo already uses
  them or the gain is justified.
- Do not use unstable or experimental APIs unless the project already opts in
  and official docs confirm the version.
- Do not replace project data-fetching conventions without evidence.
- Treat Vercel tactical guidance as secondary to official React/Next docs and
  repo patterns.

## Stop Guidance

Stop at recommendation-only when measurement would require production traffic,
unavailable profiling infrastructure, or workload data not present in the task.
Do not invent benchmark claims without evidence.

## Output

Return:

- `performance_surface`: boundary, fetching/cache, hydration, bundle, render,
  list, or responsiveness surface touched
- `basis`: official docs checked, repo pattern checked, or why not needed
- `decision`: change made or recommendation
- `verification`: lint/test/build/browser/perf evidence, or blocked reason
- `residual_risk`: what remains unmeasured or workload-dependent
