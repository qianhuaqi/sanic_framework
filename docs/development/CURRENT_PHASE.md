# Current Phase

Project: LingShu Framework
Current phase: P0 - Greenfield Architecture Consolidation
Phase type: non-implementation architecture
Current branch: human/dodo/phase-p0-greenfield-reset
Current issue: #25
Status: in progress
Next phase allowed: no

## Foundational fact

LingShu is a completely new, independently implemented Python Web/API framework.

It does not depend on Sanic, FastAPI, Flask, Django, Starlette, or any other upper-level Web framework. The old repository implementation creates no compatibility obligation.

## Current objective

1. Establish a clean repository baseline.
2. Preserve the old Sanic-based state in an archive branch.
3. Consolidate the complete Blueprint into one authoritative file.
4. Resolve remaining P0 package, directory, runtime, extension, and release questions.
5. Obtain explicit project-lead confirmation before P1.

## In scope

- Architecture and governance documents.
- Greenfield repository reset.
- Blueprint consistency review.
- Closing or classifying legacy Issues and PRs.
- Defining P1 acceptance criteria.

## Out of scope

- Production framework implementation.
- Sanic adapters or migration.
- Legacy API compatibility.
- Copying old source or tests.
- Publishing packages.
- Starting P1 before project-lead confirmation.

## Exit conditions

P0 ends only when:

1. the project lead confirms the complete Blueprint;
2. there is exactly one authoritative architecture file;
3. no active fact source describes LingShu as Sanic-based;
4. package and directory structure are explicitly confirmed;
5. P1 scope and acceptance criteria are ready;
6. all legacy implementation Issues are closed or marked historical.
