# Current Phase

Project: LingShu Framework
Current phase: C0 - global framework research convergence
Current branch: research/phase-c0-global-frameworks
Current PR: pending
Status: research convergence ready for review
Next runtime phase allowed: no

## Accepted Baseline

- Phase A accepted and merged.
- Phase B accepted and merged through PR #8.
- Current main baseline before this research branch: commit `76852c7`.
- Phase B tests previously recorded: 125 passed, 0 failed, 1 skipped.

## Current Phase Goal

Complete the documentation-only Phase C0 convergence before runtime implementation:

- consolidate global framework research;
- freeze adopt/adapt/extension/reject/later decisions;
- define core versus extension boundaries;
- map findings into small Phase C-F implementation PRs;
- correct stale governance state;
- keep runtime code unchanged.

## Current Deliverables

```text
docs/research/framework-capability-matrix.md
docs/research/lingshu-adoption-matrix.md
docs/architecture/phase-cf-implementation-map.md
docs/adr/ADR-core-vs-extension-boundary.md
```

Supporting research and ADRs cover:

```text
data/ORM/ODM/Redis
security/auth/signing/idempotency
concurrency/cancellation/resilience/shutdown
schema/validation/OpenAPI/codegen
extensions/DI/events/audit/observability/testing
```

## Current Prohibitions

- Do not modify LingShu runtime code in the C0 research branch.
- Do not start Phase C1 before the C0 research PR is independently reviewed and merged.
- Do not combine C1 security/lifecycle implementation with database, Redis, MongoDB, OpenAPI, or extension runtime work.
- Do not create one giant Phase C-F implementation PR.
- Do not silently move extension/later capabilities into the core.
- Do not merge the research PR without independent validation.
- Do not commit secrets, local personal paths, network addresses, or private credentials.
- Do not add business-code imports from `lingshu.system`.

## Next Runtime Phase

After C0 is accepted and merged, begin:

```text
C1 - Request execution foundation and lifecycle
```

C1 is limited to:

```text
RequestExecutionContext
compiled RoutePolicy skeleton
deadline/cancellation
TaskRegistry
health/live/ready/drain
ShutdownCoordinator
```

C1 must not implement JWT, HMAC signing, Redis, ORM, MongoDB, OpenAPI generation, or the full extension runtime.

## Acceptance Owner

- Xiao Gu performs independent review and records the acceptance result.
- Codex may implement later phases only after the accepted status is recorded in GitHub.
- GitHub branch, PR, commits, tests, ADRs, and this file are the source of truth; local chat state is not.

## Branch And PR

- Branch: `research/phase-c0-global-frameworks`
- Pull request: pending creation
