# ADR-006: Executable entry points, CLI, support matrix, and build baseline

- Status: Accepted
- Date: 2026-06-28
- Parent architecture Issue: #25
- Decision Issue: #46 (completed)
- Implemented by: PR #47
- Effective merge commit: `5f89572398cee509b9571ee1fe8c20bd2f71dfeb`
- Detailed model: `docs/architecture/EXECUTABLE_AND_BUILD_BASELINE.md`

## Context

LingShu required an executable and packaging baseline before P1 could create package files. The project needed one answer for startup ownership, application discovery, multi-Worker spawning, listener distribution, readiness, signals, Python/platform support, build tooling, version metadata, artifacts, and CI.

## Decision

### Execution ownership

```text
Application
  owns routes, middleware, extensions, configuration revision, and application lifecycle

Server
  owns one Worker event loop, listeners/transports, protocol execution, readiness, drain, and connection shutdown

Supervisor
  owns process creation, listener binding/transfer, Worker readiness aggregation, restart budget, process signals, and final exit code

CLI
  owns argument parsing, target specification, configuration overrides, Supervisor construction, diagnostics, and terminal exit
```

Application does not bind sockets or supervise processes. The internal Kernel does not import Server.

### Public single-Worker Server API

`lingshu.server` is a documented public subpackage:

```python
from lingshu.server import Server, ServerConfig, serve
```

Conceptual asynchronous usage:

```python
server = Server(app, ServerConfig(host="127.0.0.1", port=8000))
await server.start()
await server.wait_closed()
```

Blocking convenience:

```python
serve(app, host="127.0.0.1", port=8000)
```

Rules:

- `Server` and `serve` are single-Worker only;
- `ServerConfig` is immutable and validated before binding;
- startup freezes an unfrozen Application before runtime resources are created;
- freeze/startup failure leaves no listener or partial Server state;
- programmatic Server installs no process-global signals by default;
- `serve` owns an event loop, may install supported main-thread signals, blocks until shutdown, and rejects invocation from an already running event loop;
- drain/close is idempotent;
- the initial multi-Worker Supervisor remains internal to CLI;
- root exports remain `LingShu`, `Request`, `Response`, and `HTTPException`.

### Canonical CLI

Equivalent entry points:

```text
lingshu ...
python -m lingshu ...
```

Initial commands:

```text
lingshu run TARGET
lingshu check TARGET
lingshu version
```

- `run` starts service;
- `check` imports, validates, freezes, and reports diagnostics without binding or accepting traffic;
- `version` reports installed version/runtime support without importing user application code.

### Application target grammar

Accepted grammar:

```text
module:attribute
```

Examples:

```text
myapp.main:app
myapp:create_app --factory
```

Rules:

- module is a dotted Python module name;
- attribute is one Python identifier;
- file-path targets, calls, parentheses, indexing, lambdas, arbitrary expressions, dotted attribute traversal, and implicit scanning are prohibited;
- without `--factory`, target must be a `LingShu` instance;
- with `--factory`, target must be a synchronous zero-argument callable returning `LingShu`;
- async/parameterized factories remain deferred;
- each Worker imports its own target and does not inherit a mutable parent Application singleton.

### Run command baseline

Conceptual usage:

```text
lingshu run myapp.main:app \
  --host 127.0.0.1 \
  --port 8000 \
  --workers 1
```

Initial options:

```text
--factory
--host
--port
--workers
--config
--profile
--reload
--graceful-timeout
--hard-stop-timeout
--log-level
```

Values pass through ADR-005 configuration precedence and validation. Exact numeric defaults remain implementation tuning.

### Profiles

```text
production
development
test
```

- `run` defaults to production;
- `--reload` explicitly selects development;
- development behavior is never silently enabled for production;
- profiles select validated defaults/policies and do not bypass schemas;
- test profile belongs to controlled test harnesses.

### Development reload

Development reload is process replacement, not in-process module reload and not production configuration-revision reload.

```text
watcher parent
└─ one child Worker
```

- reload is single-Worker only;
- `--reload` with more than one Worker fails before startup;
- changes are debounced/coalesced;
- old child receives bounded stop before replacement becomes authoritative;
- process replacement clears module/application state;
- VCS, environments, caches, builds, Runtime Record storage, and configured exclusions are ignored;
- no zero-downtime or production durability guarantee is made.

### Multi-Worker process model

CLI multi-Worker execution uses internal Supervisor and cross-platform `spawn` semantics.

- correctness never depends on fork inheritance;
- Supervisor validates target/configuration but does not use a parent-imported Application as Worker state;
- each Worker imports, resolves, validates/freezes, starts one loop/runtime, and reports RevisionId/readiness;
- all required Workers must report the same RevisionId before readiness;
- deterministic import/configuration/freeze failures are startup failures, not restart-loop candidates;
- unexpected runtime exits use ADR-002 restart budgets;
- Worker count is positive and bounded;
- dynamic autoscaling remains deferred.

### Listener ownership

Supervisor binds each listener exactly once before Workers accept traffic.

- bind failure occurs before readiness;
- socket descriptor/handle is explicitly transferred or duplicated to spawned Workers;
- correctness does not depend on `SO_REUSEPORT`;
- ephemeral port selection occurs once;
- Workers do not race to bind;
- stop-admission withdraws/closes listener ownership;
- transfer implementation is private and platform-specific;
- single-Worker programmatic Server binds directly.

### Readiness

Supervisor readiness requires:

- listener bound;
- required Worker count started;
- all required Workers report the same RevisionId;
- required Application/extension resources ready;
- required Runtime Record policy available;
- no startup fatal condition.

Startup, development replacement, partial rollout, hard disk watermark, degraded configuration, or insufficient Workers are not-ready states. Liveness is distinct from readiness.

### Signals and shutdown

CLI/Supervisor owns process signals.

- first termination enters graceful drain;
- second termination requests hard stop;
- graceful timeout escalates to hard stop;
- Unix SIGTERM/SIGINT and interactive Windows Ctrl+C are supported according to platform capability;
- unsupported signals are not advertised as portable;
- SIGHUP configuration reload is deferred;
- programmatic Server installs signals only through explicit main-thread configuration.

### Exit codes

```text
0   clean shutdown / successful check or version
1   uncategorized command failure
2   CLI usage or argument error
3   application import/discovery/type error
4   configuration, validation, freeze, or extension-startup error
5   listener bind or platform startup error
6   fatal Worker failure or restart-budget exhaustion
7   graceful shutdown timeout / forced hard stop
8   required Runtime Record policy unavailable
70  unexpected CLI/Supervisor defect
```

Platform shells may report signal statuses differently; LingShu records the internal termination reason.

### Python support

```text
Implementation:  CPython
Minimum:         Python 3.12
Required:        Python 3.12, 3.13, 3.14
Preview:         Python 3.15 prerelease until promoted
requires-python: >=3.12
```

No artificial upper bound is encoded. A new minor becomes required only after the full compatibility gate. Preview failures are visible but non-blocking until promotion.

Initially unsupported/deferred:

- Python 3.11 and older;
- PyPy/other implementations;
- 32-bit Python;
- free-threaded CPython;
- embedded/minimal distributions lacking required standard-library behavior.

### Platform support tiers

Tier 1, release blocking:

```text
maintained 64-bit Linux
supported 64-bit Windows desktop/server
supported 64-bit macOS
```

Required architecture coverage:

- Linux x86_64;
- Windows x86_64;
- macOS arm64.

Linux arm64 and macOS x86_64 are Tier 2 when CI capacity exists. Exact OS floors belong to maintained release metadata/tests.

### Build backend

Initial PEP 517 backend is Hatchling:

```toml
[build-system]
requires = ["hatchling>=1.26,<2"]
build-backend = "hatchling.build"
```

LingShu uses one root `pyproject.toml` and standard PEP 621 `[project]` metadata. `setup.py`, `setup.cfg`, and dynamic metadata are not used initially. Build-backend changes require a dedicated decision.

### Project metadata and dependencies

Confirmed concepts:

```text
name = "lingshu"
requires-python = ">=3.12"
readme = "README.md"
dynamic metadata = none initially
console script = lingshu
```

License metadata remains blocked until the governance/license decision. Mandatory runtime dependencies start empty unless separately approved. Development tools do not leak into runtime requirements.

### Authoritative version source

The only manually edited version is static `[project].version` in `pyproject.toml`.

- runtime/CLI read installed metadata with `importlib.metadata.version("lingshu")`;
- no duplicate manually maintained `__version__` literal;
- Git tags/artifacts must match project version;
- component versions remain prohibited;
- SCM-derived dynamic versioning requires a later ADR.

### Console entry point

```toml
[project.scripts]
lingshu = "lingshu.cli:main"
```

`main()` returns an integer code and does not call `os._exit`. `python -m lingshu` delegates to the same function. Importing CLI starts no resources and imports no user application.

### Artifact policy

Initial outputs:

```text
one py3-none-any wheel
one source distribution
```

Wheel includes approved package code/data only and excludes tests, tools, benchmarks, fuzz corpora, caches, local configuration, Runtime Records, credentials, secrets, and development artifacts.

Sdist includes the source/metadata required to rebuild the wheel plus accepted README/governance/license material.

### Packaging verification

Packaging-sensitive changes and releases must:

1. build wheel and sdist in isolation;
2. inspect metadata and inventory;
3. create fresh environments;
4. install wheel non-editably;
5. test imports/CLI/smoke behavior outside checkout;
6. rebuild wheel from sdist and compare expected metadata/inventory;
7. avoid repository `PYTHONPATH` injection;
8. verify forbidden files/secrets are absent;
9. test editable installation separately;
10. uninstall and verify package-owned files are removed.

CI records artifact hashes. Semantic metadata/inventory equality is the initial minimum; byte reproducibility remains a target.

### CI compatibility matrix

Required pull-request matrix:

```text
Linux:   CPython 3.12, 3.13, 3.14
Windows: CPython 3.12, 3.14
macOS:   CPython 3.12, 3.14
```

Preview:

```text
Linux: CPython 3.15 prerelease, visible and non-blocking until promoted
```

Release candidates run expanded platform, artifact, signal/shutdown, and listener-transfer tests.

## Required acceptance tests

Implementation must test:

- Server state transitions, freeze-before-bind, failed-start cleanup, signal ownership, loop restrictions, and idempotent close;
- script/`-m` command parity;
- strict target grammar and instance/factory validation;
- no parent Application-state inheritance;
- spawn behavior on Tier 1 systems;
- one Supervisor bind and listener transfer;
- identical RevisionId for ready Workers;
- deterministic startup failures, restart budgets, termination escalation, and exit codes;
- reload single-Worker restriction and child replacement;
- Python implementation/version diagnostics;
- Hatchling wheel/sdist metadata and inventory;
- installed version/tag consistency;
- clean non-editable installation outside checkout;
- absence of forbidden files from artifacts;
- required CI matrix and visible preview result.

## Rejected alternatives

- Application as process Supervisor;
- Kernel importing Server;
- initial public multi-Worker root API;
- fork-only correctness or inherited mutable Application state;
- Worker bind races or `SO_REUSEPORT` as correctness baseline;
- arbitrary target-expression evaluation or implicit app guessing;
- in-process or multi-Worker development reload;
- Python 3.11 as initial minimum;
- unsupported PyPy/free-threaded/32-bit claims;
- initial `setup.py`/`setup.cfg`;
- duplicated version literals or unapproved dynamic versioning;
- editable installation as release evidence;
- publishing tests, tools, records, caches, credentials, or secrets in wheel.

## Intentionally deferred

- actual first development version and exact numeric defaults;
- health endpoint paths;
- SIGHUP and production multi-Worker configuration rollout transport;
- advanced commands and async/parameterized factories;
- public multi-Worker Supervisor API;
- PyPy, free-threaded, 32-bit, extra architectures;
- native extensions/platform wheels;
- exact OS version floors;
- License and public governance;
- PyPI publication, signing, and attestation.
