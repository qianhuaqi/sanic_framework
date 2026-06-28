# Current Phase

Project: LingShu Framework
Canonical repository: `qianhuaqi/lingshu`
Current phase: P0-D6 - Executable, CLI, Support Matrix, and Build Baseline
Phase type: non-implementation architecture and governance
Accepted baseline: latest accepted `main`
Active decision branch: `human/dodo/phase-p0-d6-executable-build-baseline`
Active decision Issue: #46
Parent architecture Issue: #25
Status: proposed architecture under project-lead review
Next phase allowed: no

## Foundational fact

LingShu is a new, independently implemented Python Web/API framework. It does not depend on Sanic, FastAPI, Flask, Django, Starlette, or another upper-level Web framework.

## Completed decisions

- P0-D1: repository/concurrent development — ADR-001 / PR #32.
- P0-D2: runtime concurrency — ADR-002 / PR #35.
- P0-D3: package/component layout — ADR-003 / PR #38.
- P0-D4: Application Kernel/request pipeline — ADR-004 / PR #41.
- P0-D5: Hardening Foundations — ADR-005 / PR #44.

Confirmed package baseline:

```text
Distribution:    lingshu
Import package:  lingshu
Production code: lingshu/
src layout:      prohibited
```

## Active proposal: P0-D6

The proposal defines:

- ownership boundaries among Application, single-Worker Server, internal Supervisor, and CLI;
- documented `lingshu.server` public subpackage with `Server`, `ServerConfig`, and `serve`;
- canonical `lingshu` and equivalent `python -m lingshu` entry points;
- initial CLI commands `run`, `check`, and `version`;
- strict `module:attribute` target grammar and explicit synchronous zero-argument `--factory`;
- production/development/test profiles;
- development reload through one-child process restart, never in-process reload;
- cross-platform `spawn` semantics for multi-Worker CLI execution;
- Supervisor binding each listener once and explicitly transferring it to Workers;
- readiness based on listeners, required Worker count, identical RevisionId, extensions/resources, and Runtime Record policy;
- first graceful termination, second hard-stop request, and stable CLI exit codes;
- CPython 3.12 minimum, required 3.12/3.13/3.14, and visible non-blocking 3.15 preview;
- Tier 1 64-bit Linux, Windows, and macOS support;
- Hatchling PEP 517 backend and standard PEP 621 project metadata;
- static `[project].version` as the single version source;
- console script `lingshu = "lingshu.cli:main"`;
- pure-Python wheel and sdist artifact policy;
- required CI/clean-install matrix.

Detailed proposal:

- `docs/decisions/ADR-006-executable-cli-support-and-build-baseline.md`
- `docs/architecture/EXECUTABLE_AND_BUILD_BASELINE.md`

## Explicitly unresolved

- actual production files, package code, CLI, Server, Supervisor, or CI implementation;
- actual first development version;
- license and public governance policy;
- exact numeric defaults;
- concrete health endpoint paths;
- SIGHUP and production multi-Worker configuration reload transport;
- async/parameterized factories and advanced CLI commands;
- PyPy, free-threaded builds, 32-bit systems, and native extensions;
- PyPI publication, signing, and attestation.

## Current objective

1. review the Application/Server/Supervisor/CLI ownership split;
2. verify strict application discovery and no arbitrary expression evaluation;
3. verify spawn, listener, readiness, signal, and exit-code semantics;
4. verify Python/platform support commitments;
5. verify Hatchling, version, artifact, and CI decisions;
6. open a documentation-only Pull Request;
7. keep P1 blocked.

## Out of scope

- creating `pyproject.toml`, `lingshu/`, tests, or workflows;
- adding runtime/build dependencies to the actual project;
- implementing or publishing the framework;
- starting P1.

## Exit conditions for P0-D6

1. ADR-006 and detailed baseline are reviewed and merged;
2. public and CLI execution boundaries are explicit;
3. process/listener/readiness/signal/exit semantics are explicit;
4. Python/platform/build/version/artifact/CI contracts are explicit;
5. deferred choices remain unresolved;
6. the project lead performs the final merge.

P0 continues after P0-D6. P1 remains blocked.
