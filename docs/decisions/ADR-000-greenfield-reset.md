# ADR-000: Greenfield repository reset

- Status: Accepted
- Date: 2026-06-28
- Issue: #25
- Implemented by: PR #28
- Effective commit: `0ff49d7804067114129dd16501f85188e54425c3`

## Context

The previous repository contained a Sanic-based implementation, application scaffolding, tests, dependency files, and old architecture rules. LingShu is now a completely independent Python Web/API framework developed from scratch.

Keeping those files in the active tree repeatedly caused humans and AI developers to treat the old project as the implementation baseline.

## Decision

1. Preserve the previous repository state in `archive/legacy-sanic-20260628`.
2. Use the active `main` branch only for the greenfield framework.
3. Do not copy or adapt old Sanic code into the new framework.
4. Do not preserve old public APIs before v1.0.
5. Treat archived code, old Issues, and old Pull Requests as reference material only.
6. Re-evaluate any useful historical idea against the confirmed Blueprint before implementing it.
7. Start production implementation only after P0 acceptance and creation of a P1 Issue.

## Consequences

- The active tree contains no production source code or old tests.
- Historical implementation tasks must be closed or marked historical before P1.
- New package layout, dependencies, runtime design, and public APIs come only from confirmed greenfield decisions.
- Repository history does not create a compatibility requirement.

## Verification

- Archive branch: `archive/legacy-sanic-20260628`
- Archive commit: `b869270e0ec7cbc324d17ef246e39d0873aab14f`
- Reset Pull Request: #28
- Reset merge commit: `0ff49d7804067114129dd16501f85188e54425c3`
