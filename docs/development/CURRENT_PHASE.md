# Current Phase

Project: LingShu Framework
Canonical repository: `qianhuaqi/lingshu`
Current phase: P0 - Architecture Decision Review and Blueprint Consolidation
Phase type: non-implementation architecture and governance
Current baseline: `main` after PR #29 merge commit `0b5310f5e90dd321f9d5c571a89904dca949847c`
Active implementation branch: none
Current issue: #25
Status: awaiting project-lead architecture decisions
Next phase allowed: no

## Foundational fact

LingShu is a completely new, independently implemented Python Web/API framework.

It does not depend on Sanic, FastAPI, Flask, Django, Starlette, or any other upper-level Web framework. The archived implementation creates no compatibility obligation.

The complete previous implementation is preserved at `archive/legacy-sanic-20260628` and is not an active source of truth.

## Completed baseline

- PR #28 replaced the active tree with the greenfield P0 baseline.
- PR #29 completed the governance contract, decision-status register, and controlled P0-RC0 Blueprint entrypoint.
- The repository was renamed from `qianhuaqi/sanic_framework` to `qianhuaqi/lingshu`.
- The old repository URL redirects to the canonical repository.
- Legacy source, tests, scaffolds, dependency configuration, and Sanic runtime files are absent from active `main`.
- Issue #25 is the only active architecture Issue.

## Current objective

1. Review the candidate architecture chapter by chapter with the project lead.
2. Confirm the final repository and source layout.
3. Confirm Core, HTTP, Server, Record, CLI, and extension boundaries.
4. Confirm built-in versus separately installable capabilities.
5. Integrate accepted hardening requirements into the single Blueprint.
6. Confirm release stages, Python/platform support, and compatibility policy.
7. Confirm license, contribution, and vulnerability-reporting policy before public release.
8. Prepare an explicit P1 Issue only after P0 acceptance.

## In scope

- Architecture decision discussion and recording.
- Blueprint amendments and ADRs.
- Decision-status updates.
- P0 acceptance preparation.
- Repository-level governance decisions.

## Out of scope

- Production framework implementation.
- Source package or directory skeleton creation.
- Sanic adapters, migrations, or compatibility layers.
- Copying old source, tests, scaffolds, or dependencies.
- Runtime dependency introduction.
- Package publication.
- Starting P1 before project-lead confirmation.

## Unresolved decisions

The following remain candidates and must not be implemented yet:

- single package versus monorepo multi-distribution layout;
- direct `lingshu/` package versus any `src/` layout;
- exact Core, HTTP, Server, Record, CLI, and extension directory boundaries;
- which capabilities are built in and which are separately installable;
- release-version mapping and first public compatibility promise;
- supported Python and platform range;
- open-source license and public contribution/security policies.

The detailed state is tracked in `docs/architecture/P0_DECISION_STATUS.md`.

## Exit conditions

P0 ends only when:

1. the project lead confirms the complete Blueprint;
2. all accepted hardening items are integrated into that single Blueprint;
3. no active fact source describes LingShu as Sanic-based;
4. package and directory structure are explicitly confirmed;
5. dependency and extension boundaries are explicitly confirmed;
6. release stages and P1 acceptance criteria are ready;
7. all legacy implementation Issues are closed or marked historical;
8. governance files are internally consistent;
9. the project lead explicitly authorizes creation of the P1 Issue.
