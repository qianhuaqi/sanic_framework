# P0 Architecture Decision Status

- Status: Active P0 control document
- Parent Issue: #25
- Active decision Issue: #46
- Active proposal: P0-D6 / ADR-006
- Last accepted decision: P0-D5 / ADR-005 / PR #44
- Last updated: 2026-06-28

## Authority

`LINGSHU_FRAMEWORK_BLUEPRINT.md` is the single overall architecture document. This file records decision state only.

- **Confirmed** decisions may be used by later implementation Issues.
- **Proposed** and **Candidate** decisions must not be implemented.
- **Rejected** decisions require a new Issue, ADR, and project-lead approval before reconsideration.

## Confirmed decisions

### P0-D1

Single repository and concurrent-development governance are accepted through ADR-001 / PR #32.

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

One root `pyproject.toml`, one version/release cadence, controlled facade, and acyclic component dependencies are confirmed.

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
- verified hardening integration mapping.

## Proposed — P0-D6, not executable until merged

Issue #46 and ADR-006 propose:

### Execution ownership

- Application owns application definitions/revision/lifecycle plan;
- public single-Worker Server owns one loop/runtime/listener/protocol/drain;
- internal Supervisor owns process spawn, one-time listener binding/transfer, Worker readiness/restarts, signals, and exit;
- CLI owns arguments, target specification, overrides, Supervisor construction, diagnostics, and terminal exit.

### Public Server surface

Documented public subpackage:

```python
from lingshu.server import Server, ServerConfig, serve
```

`Server` and `serve` are single-Worker only. Root exports remain unchanged. Multi-Worker Supervisor remains internal to CLI initially.

### CLI and discovery

```text
lingshu run module:app
lingshu run module:create_app --factory
lingshu check module:app
lingshu version
python -m lingshu ...
```

- target grammar is strict `module:attribute`;
- no file paths, expressions, calls, dotted attribute traversal, or implicit scanning;
- instance mode requires `LingShu`;
- factory mode requires synchronous zero-argument callable returning `LingShu`;
- production/development/test profiles;
- development reload is one-child process restart and cannot be multi-Worker.

### Processes, listener, readiness, and shutdown

- cross-platform `spawn` semantic baseline;
- each Worker independently imports/freezes target and reports RevisionId;
- Supervisor binds listener once and explicitly transfers it;
- no correctness dependency on fork or `SO_REUSEPORT`;
- readiness requires listener, required Workers, identical RevisionId, ready resources/extensions, and available required Runtime Record policy;
- first termination begins drain; second or timeout forces hard stop;
- stable exit-code catalog 0,1,2,3,4,5,6,7,8,70.

### Python/platform support

```text
Implementation: CPython
Minimum:        3.12
Required:       3.12, 3.13, 3.14
Preview:        3.15 prerelease
requires-python: >=3.12
```

Tier 1: maintained 64-bit Linux, supported 64-bit Windows, and supported 64-bit macOS. PyPy, free-threaded, 32-bit, and other interpreters remain deferred.

### Build/version/artifacts

- Hatchling PEP 517 backend;
- standard root `[project]` metadata;
- no `setup.py`/`setup.cfg` initially;
- static `[project].version` is the only manually edited version;
- runtime/CLI reads installed version via `importlib.metadata`;
- console script `lingshu = "lingshu.cli:main"`;
- one `py3-none-any` wheel and one sdist;
- clean-install/outside-checkout/inventory/metadata/sdist-rebuild tests;
- required CI: Linux 3.12/3.13/3.14, Windows 3.12/3.14, macOS 3.12/3.14;
- Linux 3.15 prerelease visible non-blocking preview.

Proposal documents:

- `docs/decisions/ADR-006-executable-cli-support-and-build-baseline.md`
- `docs/architecture/EXECUTABLE_AND_BUILD_BASELINE.md`

## Rejected principles

Previously rejected principles remain rejected. P0-D6 additionally rejects:

- Application as process Supervisor;
- Kernel importing Server;
- initial public multi-Worker root API;
- fork-only correctness or inherited mutable Application state;
- Worker port-bind races or required `SO_REUSEPORT`;
- arbitrary target expression evaluation or implicit app discovery;
- in-process development reload or multi-Worker reload;
- Python 3.11 as initial minimum;
- unsupported PyPy/free-threaded/32-bit claims;
- initial `setup.py`/`setup.cfg`;
- duplicate version literals or unapproved dynamic versioning;
- editable installation as release evidence;
- shipping tests/tools/records/secrets/caches inside the wheel.

## Candidate — not executable

### Later framework decisions

- numeric defaults and concrete health endpoints;
- SIGHUP and multi-Worker configuration rollout transport;
- advanced routing/body formats;
- sync Handler adaptation and dependency injection;
- official capabilities/extensions;
- HTTP/2, HTTP/3, accelerators, additional runtimes/platforms;
- public multi-Worker Supervisor API.

### Governance and P0 completion

- License, contribution, security disclosure/support, changelog, code of conduct, release/version policy;
- first public release and artifact signing/attestation;
- P1 scope, v0.x mapping, final Blueprint freeze, and explicit P1 authorization.

## Confirmation rule

A proposal becomes Confirmed only after a dedicated Issue, ADR/Blueprint amendment, explicit project-lead confirmation, reviewed/merged PR, and synchronization of this register.

P1 remains blocked until all P0 exit conditions are met.
