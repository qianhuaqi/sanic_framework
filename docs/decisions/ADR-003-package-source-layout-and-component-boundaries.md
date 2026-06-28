# ADR-003: Package, source layout, and component boundaries

- Status: Accepted
- Date: 2026-06-28
- Parent architecture Issue: #25
- Decision Issue: #37 (completed)
- Implemented by: PR #38
- Effective merge commit: `66c977f435c23fc9aaa35c4f085a7ca20a81879a`
- Detailed model: `docs/architecture/PACKAGE_AND_COMPONENT_LAYOUT.md`

## Context

LingShu requires one physical source layout and one dependency model before production implementation begins. Without a fixed layout, concurrent developers could create incompatible package structures, duplicate public contracts, circular dependencies, and conflicting release assumptions.

The project lead explicitly rejected adding a `src/` directory and approved a simple initial release surface without premature multi-distribution maintenance.

## Decision

### 1. One initial distribution

LingShu initially uses:

```text
Repository:      qianhuaqi/lingshu
Distribution:    lingshu
Import package:  lingshu
Packaging file:  pyproject.toml
Version:         one shared framework version
```

Core, Runtime, HTTP, Server, Runtime Record, extension mechanisms, CLI, and testing support are internal components of this one distribution. They are not separately versioned or published.

A future split requires a dedicated ADR demonstrating independent consumers, a material dependency or installation benefit, stable contracts, release ownership, compatibility rules, CI isolation, and a migration path.

### 2. No `src/` or initial `packages/` layout

Production source is located directly at repository root:

```text
lingshu/
```

The initial framework must not use:

```text
src/lingshu/
packages/lingshu/
```

The no-`src` choice is protected by mandatory wheel and isolated-install verification.

### 3. Target repository layout

```text
.
├─ lingshu/
│  ├─ __init__.py
│  ├─ core/
│  ├─ runtime/
│  ├─ http/
│  ├─ server/
│  ├─ record/
│  ├─ extensions/
│  ├─ cli/
│  └─ testing/
├─ tests/
│  ├─ unit/
│  ├─ contract/
│  ├─ integration/
│  ├─ protocol/
│  ├─ concurrency/
│  ├─ security/
│  ├─ packaging/
│  └─ compatibility/
├─ docs/
├─ examples/
├─ tools/
├─ benchmarks/
├─ fuzz/
├─ pyproject.toml
├─ README.md
├─ LICENSE
└─ AGENTS.md
```

This ADR accepts the architecture only. The production directories and packaging file are created by a later explicitly authorized implementation Issue.

### 4. Component responsibilities

#### `lingshu.core`

Owns the Application Kernel, base lifecycle contracts, base exception taxonomy, configuration contracts, identifiers and immutable common values, extension protocol contracts, capability registration, and generic audit/telemetry protocols.

`core` depends on no other LingShu component.

#### `lingshu.runtime`

Owns Scope ownership, Deadline, cancellation, managed task supervision, admission control, bounded waiters, backpressure coordination, blocking-work executors, and shutdown primitives.

```text
runtime → core
```

#### `lingshu.http`

Owns Request and Response semantics, headers, cookies, body and streaming contracts, routing, middleware, HTTP error mapping, and later-approved serialization/content-negotiation interfaces.

```text
http → runtime + core
```

`http` does not depend on `server`.

#### `lingshu.server`

Owns listeners, transports, HTTP/1.1 parser integration, connections, keep-alive, Supervisor, Worker, readiness, drain, stop, restart, crash handling, and transport flow control.

```text
server → http + runtime + core
```

#### `lingshu.record`

Owns the default request-level Runtime Record implementation, including event envelopes, identity mapping, parent-child ordering, redaction, truncation, bounded queues, retention, cleanup, safe local writing, and failure/flush reporting.

Runtime Record mechanisms ship in the default distribution because request-level auditability is a confirmed invariant. Heavy external storage exporters remain optional.

```text
record → core + stable runtime contracts
```

Lower components interact with recording through protocols rather than concrete storage writers.

#### `lingshu.extensions`

Owns extension registration, dependency ordering, capability binding, lifecycle integration, health, cleanup, and optional capability activation.

It does not itself contain Auth, Tenant, RBAC, SQL, Redis, OpenAPI, or other policy implementations merely because they may later be extensions.

```text
extensions → core + runtime
```

HTTP-specific extension implementations may use documented HTTP contracts without making `http` depend on `extensions`.

#### `lingshu.cli`

Owns installed command-line behavior and uses documented public composition surfaces. It must not bypass lifecycle rules or rely on private internals as shortcuts.

#### `lingshu.testing`

Owns test client support, fake transports, fake monotonic clocks, deterministic cancellation and task barriers, test harnesses, resource snapshots, and leak assertions.

Production components must not depend on `testing`.

### 5. Dependency rules

Primary direction:

```text
core
  ↑
runtime
  ↑
http
  ↑
server
```

Side components:

```text
record      → core + stable runtime contracts
extensions  → core + runtime (+ documented HTTP contracts when required)
cli         → public composition surface
testing     → public and explicit test-support surfaces
```

Forbidden:

- dependency cycles;
- `core` importing another LingShu component;
- `runtime` importing higher components;
- `http` importing `server`;
- production code importing `testing`;
- lower components importing the root `lingshu` facade;
- cross-component private-module imports without an architecture decision.

P1 must add machine-enforced import-boundary checks.

### 6. Controlled public API

`lingshu/__init__.py` is the controlled public facade.

Rules:

- explicit `__all__`;
- no wildcard re-export chains;
- only intentionally documented exports are public;
- deep imports are private unless explicitly promoted;
- names beginning with `_` are private;
- import time must not start tasks, create connections, open files, or mutate process-global state;
- optional integrations must not load during `import lingshu`;
- public exports require contract tests.

This ADR does not freeze concrete public class or function names.

### 7. Optional dependency behavior

One distribution does not make every integration mandatory.

- `import lingshu` must not require database, Redis, cloud, tracing, or authentication packages;
- optional dependencies load only when the capability is activated;
- missing optional dependencies fail with a focused activation error;
- optional integrations must not become hidden core requirements;
- exact extras and the official extension catalog are decided later.

### 8. Repository support directories

- `tests/unit/`: component-local behavior;
- `tests/contract/`: public and cross-component contracts;
- `tests/integration/`: real composition;
- `tests/protocol/`: protocol and malformed-input behavior;
- `tests/concurrency/`: ownership, Deadline, cancellation, backpressure, Worker, shutdown, and leak behavior;
- `tests/security/`: trust boundaries, redaction, limits, and safe defaults;
- `tests/packaging/`: wheel, sdist, metadata, inventory, entry points, and isolated installation;
- `tests/compatibility/`: supported Python/platform checks after the support matrix is accepted;
- `benchmarks/`: performance measurement, not correctness evidence;
- `fuzz/`: fuzz harnesses, corpora, and minimized regressions;
- `examples/`: executable examples using public APIs only;
- `tools/`: repository maintenance tools not imported by runtime code;
- `docs/`: authoritative architecture, development, API, and user documentation.

### 9. Mandatory packaging quality gate

Because source is located at repository root, checkout test success is insufficient.

Packaging-related acceptance must:

1. build wheel and source distribution;
2. create a fresh isolated virtual environment;
3. install the wheel without editable mode;
4. run from a directory outside the repository;
5. avoid repository `PYTHONPATH` injection;
6. run import, smoke, and later CLI checks;
7. validate installed file inventory and metadata;
8. verify tests, tools, caches, secrets, and local files are not shipped;
9. verify the source distribution can rebuild the expected wheel;
10. test editable installation separately without treating it as release evidence.

### 10. Version ownership

The distribution has one authoritative version source. Internal components do not have independent version constants, release tags, or partial releases.

The exact version-source mechanism and build backend are deferred.

## Rejected alternatives

- `src/lingshu/`;
- initial `packages/` monorepo layout;
- multiple initial distributions such as `lingshu-core` and `lingshu-server`;
- multiple component-level `pyproject.toml` files;
- independent component versions;
- production components importing `lingshu.testing`;
- treating every importable deep module as public API;
- relying only on editable installation or checkout-root tests as packaging evidence.

## Intentionally deferred

- minimum Python version and platform matrix;
- build backend;
- exact public classes, functions, and API manifest;
- authoritative version-file mechanism;
- optional extras and official integration implementations;
- first PyPI release timing;
- post-v1.0 compatibility policy.
