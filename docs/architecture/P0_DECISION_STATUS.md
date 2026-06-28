# P0 Architecture Decision Status

- Status: Active P0 control document
- Parent Issue: #25
- Active decision Issue: none
- Last accepted decision: P0-D6 / ADR-006 / PR #47
- Last updated: 2026-06-28

## Authority

`LINGSHU_FRAMEWORK_BLUEPRINT.md` is the single overall architecture document. This file records decision state only.

- **Confirmed** decisions may be used by later implementation Issues.
- **Proposed** and **Candidate** decisions must not be implemented.
- **Rejected** decisions require a new Issue, ADR, and project-lead approval before reconsideration.

## Confirmed decisions

### P0-D1

Repository and concurrent-development governance are accepted through ADR-001 / PR #32.

### P0-D2

Runtime concurrency is accepted through ADR-002 / PR #35: standard-library `asyncio`, one loop/runtime per Worker, structured task ownership, bounded resources, monotonic Deadline, cancellation propagation, restart budgets, and graceful shutdown.

### P0-D3

Package/component layout is accepted through ADR-003 / PR #38:

```text
Distribution:    lingshu
Import package:  lingshu
Production code: lingshu/
src layout:      prohibited
```

One root `pyproject.toml`, one version/release cadence, controlled public facade, and acyclic component dependencies are confirmed.

### P0-D4

Application Kernel and request pipeline are accepted through ADR-004 / PR #41: public `LingShu`, immutable revisions/plans, deterministic routing/middleware, async Handler, fixed request pipeline, bounded Request body, irreversible Response commit, deterministic exception mapping, and root exports `LingShu`, `Request`, `Response`, `HTTPException`.

### P0-D5

Hardening Foundations are accepted through ADR-005 / PR #44:

- typed identifiers and separate wall/monotonic time;
- stable error codes and safe problem responses;
- strict versioned configuration with protected values and atomic reload;
- bounded strict UTF-8 JSON and negotiation;
- Runtime Record reservation, append-only events, local segments, budgets, watermarks, retention, and recovery;
- common telemetry/redaction/cardinality rules;
- Verified hardening integration mapping.

### P0-D6

Executable, CLI, support, and build baseline are accepted through ADR-006 / PR #47 at merge commit `5f89572398cee509b9571ee1fe8c20bd2f71dfeb`.

Confirmed:

#### Ownership and public Server

- Application owns application definition/revision/lifecycle plan;
- public single-Worker Server owns one event loop/runtime/listener/protocol/readiness/drain;
- internal Supervisor owns process spawn, one-time listener binding/transfer, Worker readiness/restarts, signals, and exit;
- CLI owns arguments, target specification, configuration overrides, Supervisor setup, diagnostics, and terminal exit;
- documented public subpackage exports `Server`, `ServerConfig`, and `serve`;
- root exports remain unchanged;
- initial public multi-Worker Supervisor API is not exposed.

#### CLI and discovery

```text
lingshu run module:app
lingshu run module:create_app --factory
lingshu check module:app
lingshu version
python -m lingshu ...
```

- strict `module:attribute` grammar;
- no file paths, expression evaluation, calls, indexing, dotted attribute traversal, implicit scanning, or app guessing;
- instance mode requires LingShu;
- factory mode requires synchronous zero-argument callable returning LingShu;
- production/development/test profiles;
- development reload uses single-Worker process replacement.

#### Multi-Worker and shutdown

- cross-platform `spawn` semantic baseline;
- each Worker independently imports/freezes and reports RevisionId;
- required Workers must share one RevisionId;
- Supervisor binds listener once and explicitly transfers it;
- no correctness dependency on fork or `SO_REUSEPORT`;
- readiness requires listener, required Workers, ready resources/extensions, required Runtime Record policy, and no fatal startup condition;
- first termination drains; second or timeout hard-stops;
- stable exit codes 0, 1, 2, 3, 4, 5, 6, 7, 8, and 70.

#### Python/platform support

```text
Implementation:  CPython
Minimum:         3.12
Required:        3.12, 3.13, 3.14
Preview:         3.15 prerelease
requires-python: >=3.12
```

Tier 1 is maintained 64-bit Linux, supported 64-bit Windows, and supported 64-bit macOS. Linux x86_64, Windows x86_64, and macOS arm64 are required architecture coverage. PyPy, free-threaded, 32-bit, and other implementations remain deferred.

#### Build/version/artifacts

- Hatchling PEP 517 backend;
- PEP 621 root `[project]` metadata;
- no initial `setup.py`, `setup.cfg`, or dynamic metadata;
- static `[project].version` is the only manually edited version;
- runtime/CLI use `importlib.metadata`;
- console script `lingshu = "lingshu.cli:main"`;
- one `py3-none-any` wheel and one sdist;
- clean non-editable install outside checkout, inventory/metadata, sdist rebuild, editable developer test, and uninstall verification;
- required CI: Linux 3.12/3.13/3.14, Windows 3.12/3.14, macOS 3.12/3.14;
- Linux 3.15 prerelease remains visible non-blocking preview.

Detailed model:

- `docs/decisions/ADR-006-executable-cli-support-and-build-baseline.md`
- `docs/architecture/EXECUTABLE_AND_BUILD_BASELINE.md`

## Rejected principles

Previously rejected principles remain rejected. P0-D6 additionally rejects:

- Application as process Supervisor;
- Kernel importing Server;
- initial public multi-Worker root API;
- fork-only correctness or inherited mutable Application state;
- Worker bind races or required `SO_REUSEPORT`;
- arbitrary target expression evaluation or implicit application discovery;
- in-process or multi-Worker development reload;
- Python 3.11 as the initial minimum;
- unsupported PyPy/free-threaded/32-bit claims;
- initial `setup.py`/`setup.cfg`;
- duplicate version literals or unapproved dynamic versioning;
- editable installation as release evidence;
- shipping tests, tools, records, caches, credentials, or secrets inside wheel.

## Candidate — not executable

### Recommended next decision: P0-D7 final governance and freeze

- License selection and metadata;
- contribution policy and code of conduct;
- security disclosure, supported security versions, and vulnerability handling;
- changelog and release-note policy;
- pre-1.0 compatibility, SemVer, deprecation, and removal rules;
- tags, branches, version bumps, release publication, signing/attestation, and rollback;
- first development version and P1 milestone mapping;
- P1 Issue dependency graph and acceptance matrix;
- final Blueprint consistency audit;
- final P0 freeze and explicit P1 authorization decision.

### Deferred implementation/features

- exact numeric defaults and health endpoint paths;
- SIGHUP/multi-Worker configuration rollout;
- advanced CLI/factory forms and public Supervisor API;
- advanced routing/body formats;
- sync Handler adaptation and dependency injection;
- official capabilities/extensions;
- HTTP/2, HTTP/3, accelerators, extra runtimes/platforms;
- native extensions and platform wheels.

## Confirmation rule

A proposal becomes Confirmed only after a dedicated Issue, ADR/Blueprint amendment, explicit project-lead confirmation, reviewed/merged PR, and synchronization of this register.

P1 remains blocked until the final P0 freeze explicitly authorizes it.
