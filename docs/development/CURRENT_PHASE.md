# Current Phase

Project: LingShu Framework
Current phase: P0-G1 - Governance and Architecture Fact-Source Consolidation
Phase type: non-implementation architecture and governance
Current baseline: `main` at or after PR #28 merge commit `0ff49d7804067114129dd16501f85188e54425c3`
Current branch: `human/dodo/phase-p0-g1-governance-hardening`
Current issue: #25
Status: in progress
Next phase allowed: no

## Foundational fact

LingShu is a completely new, independently implemented Python Web/API framework.

It does not depend on Sanic, FastAPI, Flask, Django, Starlette, or any other upper-level Web framework. The archived implementation creates no compatibility obligation.

The complete previous implementation is preserved at `archive/legacy-sanic-20260628` and is not an active source of truth.

## Completed baseline

PR #28 has been merged. The active `main` tree now contains architecture and governance files only; legacy source, tests, scaffolds, dependency configuration, and Sanic runtime files are no longer part of the active tree.

## Current objective

1. Complete the development constitution.
2. Synchronize README, AGENTS, ADR, phase, and handoff state.
3. Mark all unresolved package, directory, `src/`, distribution, and release choices as non-executable candidates.
4. Maintain one authoritative Blueprint while using a separate status register only to track confirmation state.
5. Integrate accepted hardening requirements into the Blueprint before P0 freeze.
6. Close or clearly archive remaining legacy implementation Issues.
7. Prepare explicit P1 scope and acceptance criteria only after the architecture choices are confirmed.

## In scope

- Architecture and governance documents.
- Fact-source priority and conflict rules.
- Blueprint decision-status tracking.
- Closing or classifying legacy Issues and PRs.
- P0 acceptance preparation.
- Repository-level public governance decisions such as license, security policy, and contribution policy.

## Out of scope

- Production framework implementation.
- Source package or directory skeleton creation.
- Sanic adapters, migrations, or compatibility layers.
- Copying old source, tests, scaffolds, or dependencies.
- Publishing packages.
- Starting P1 before project-lead confirmation.

## Unresolved decisions

The following remain candidates and must not be implemented yet:

- single package versus monorepo multi-distribution layout;
- direct `lingshu/` package versus any `src/` layout;
- exact Core, HTTP, Server, Record, CLI, and extension directory boundaries;
- which capabilities are built-in and which are separately installable;
- release-version mapping and first public compatibility promise;
- open-source license and public contribution/security policies.

The detailed status is tracked in `docs/architecture/P0_DECISION_STATUS.md`.

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
