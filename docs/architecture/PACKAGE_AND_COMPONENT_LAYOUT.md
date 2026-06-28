# LingShu Package and Component Layout

- Status: Accepted through P0-D3
- Decision Issue: #37 (completed)
- Pull Request: #38
- Effective merge commit: `66c977f435c23fc9aaa35c4f085a7ca20a81879a`
- Parent Issue: #25
- Related ADR: `docs/decisions/ADR-003-package-source-layout-and-component-boundaries.md`

## 1. Canonical names

```text
Repository:           qianhuaqi/lingshu
Distribution:         lingshu
Import package:       lingshu
Root packaging file:  pyproject.toml
Production source:    lingshu/
src layout:           prohibited
```

LingShu begins as one distribution, one import package, one packaging file, one authoritative version, and one release cadence.

## 2. Target repository tree

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

This document accepts the architecture only. The production tree is created later by an explicitly authorized implementation Issue after P0 exits.

## 3. Component responsibilities

### 3.1 `lingshu.core`

Purpose: framework-wide stable kernel mechanisms and contracts.

Owns:

- Application Kernel;
- base lifecycle states and contracts;
- base exception taxonomy;
- configuration contracts;
- identifiers and immutable common values;
- extension protocol contracts;
- capability registration contracts;
- generic audit and telemetry sink protocols;
- protocol-neutral primitives.

Dependency rule:

```text
core → no other LingShu component
```

Must not contain HTTP parsing, listeners, database/auth/tenant/cache policy, concrete record storage, or test helpers.

### 3.2 `lingshu.runtime`

Purpose: asynchronous execution, ownership, and resource control.

Owns:

- Scope hierarchy;
- Deadline and cancellation mechanics;
- managed tasks and supervision;
- admission control and bounded waiters;
- backpressure coordination;
- bounded thread/process executor interfaces;
- drain and shutdown primitives;
- runtime-local context mechanisms.

Dependency rule:

```text
runtime → core
```

### 3.3 `lingshu.http`

Purpose: application-facing HTTP semantics independent of listener and process management.

Owns:

- Request and Response abstractions;
- headers, cookies, body streams, and response streams;
- route definitions and matching;
- middleware execution;
- HTTP status and error mapping;
- HTTP-specific context;
- later-approved serialization and content-negotiation extension contracts.

Dependency rule:

```text
http → runtime + core
```

Forbidden:

```text
http → server/cli/testing/concrete integrations
```

### 3.4 `lingshu.server`

Purpose: native transport, parser integration, Worker, and process execution.

Owns:

- listeners and transports;
- HTTP/1.1 parser integration;
- connection lifecycle and keep-alive;
- bounded read-ahead and transport flow control;
- Supervisor and Worker execution;
- readiness, drain, stop, restart, and crash handling;
- dispatch from an accepted request to the HTTP application pipeline.

Dependency rule:

```text
server → http + runtime + core
```

It must not define authentication, tenant, database, cache, or project business policy.

### 3.5 `lingshu.record`

Purpose: default request-level Runtime Record implementation.

Owns:

- record events and envelopes;
- request, connection, trace, and operation identity mapping;
- parent-child and monotonic ordering data;
- default redaction and truncation;
- bounded record queues;
- retention and cleanup contracts;
- default safe local writer;
- flush, drop, truncation, and failure reporting.

Dependency rule:

```text
record → core + stable runtime contracts
```

Runtime Record mechanisms are installed by default. Heavy external storage exporters remain optional and attach through later extension decisions.

Lower components use protocols and event contracts rather than importing concrete record writers.

### 3.6 `lingshu.extensions`

Purpose: extension hosting and capability composition.

Owns:

- extension registration and discovery;
- dependency ordering;
- capability binding;
- extension startup and shutdown integration;
- health and cleanup hooks;
- lazy optional capability activation.

Dependency rule:

```text
extensions → core + runtime
```

An HTTP-specific extension may use documented HTTP contracts without making `http` depend on `extensions`.

This component does not automatically contain Auth, Tenant, RBAC, SQL, Redis, OpenAPI, or other policy implementations.

### 3.7 `lingshu.cli`

Purpose: installed command-line interface.

Rules:

- use documented composition and public APIs;
- do not bypass lifecycle, validation, or cleanup rules;
- do not become an import dependency of production runtime components;
- command implementation internals are private by default.

### 3.8 `lingshu.testing`

Purpose: supported deterministic testing utilities.

Owns:

- test client contracts;
- fake transports;
- fake monotonic clock;
- deterministic cancellation and task barriers;
- application test harnesses;
- runtime resource snapshots;
- leak assertions.

Production components must never depend on `testing`. Test-only third-party tools remain development dependencies.

## 4. Dependency graph

Primary production graph:

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

Architecture violations include:

- `core` importing another LingShu component;
- `runtime` importing `http`, `server`, `record`, `cli`, or `testing`;
- `http` importing `server`, `cli`, or `testing`;
- `server` importing business integrations or `testing`;
- production code importing `testing`;
- lower components importing the root `lingshu` facade;
- circular imports or dependency cycles;
- cross-component private-module imports without an approved architecture change.

P1 must add machine-enforced import-boundary checks. A boundary exception requires an Issue and ADR amendment, not a local ignore.

## 5. Root facade and public API

`lingshu/__init__.py` is the controlled public facade.

Rules:

- explicit `__all__`;
- no wildcard re-export chains;
- only documented names are public;
- deep paths remain private unless explicitly promoted;
- names beginning with `_` are private;
- public exports require contract tests;
- import time must not open files or connections, start tasks, spawn processes, or mutate process-global state;
- optional integrations must not load during `import lingshu`;
- lower layers must not import the facade to access higher layers.

Concrete public class and function names are intentionally deferred to a later public-API decision.

Possible stability levels:

```text
Public facade
Public documented subpackage
Extension-author contract
Test-support API
Internal implementation
```

Each public level must be explicitly declared and tested.

## 6. Optional dependency rules

One distribution does not mean all integrations are mandatory.

- importing `lingshu` must not require database, Redis, cloud, tracing, or authentication libraries;
- optional dependencies load only when their capability is activated;
- missing optional dependencies produce a focused activation error;
- optional integrations do not become hidden transitive core requirements;
- importing one optional capability must not load unrelated integrations;
- extras must represent coherent capabilities rather than undocumented dependency buckets.

Exact extras and the official extension catalog remain deferred.

## 7. Packaging configuration

The repository has one root `pyproject.toml`.

It will eventually own:

- build-system configuration;
- distribution metadata;
- authoritative version configuration;
- mandatory runtime dependencies;
- optional dependency groups;
- development dependency groups;
- CLI entry points;
- package discovery;
- included resources and typing metadata;
- relevant test, lint, typing, and build-tool configuration.

P0-D3 does not choose the build backend or minimum Python version.

All internal components share one distribution version. Independent component versions, tags, and partial releases are prohibited.

## 8. Repository support directories

### `tests/unit/`

Fast component-local behavior.

### `tests/contract/`

Public facade, extension, lifecycle, and cross-component contracts.

### `tests/integration/`

Real composition among components and resources.

### `tests/protocol/`

HTTP parsing, framing, malformed input, keep-alive, and transport behavior.

### `tests/concurrency/`

Task ownership, Deadline, cancellation, backpressure, saturation, Worker, shutdown, and leak behavior.

### `tests/security/`

Trust boundaries, redaction, protocol ambiguity, resource limits, and safe defaults.

### `tests/packaging/`

Wheel, sdist, metadata, file inventory, entry points, isolated installation, and import checks.

### `tests/compatibility/`

Supported Python and platform behavior after the support matrix is accepted.

### `benchmarks/`

Reproducible performance measurement. Benchmarks do not replace correctness tests.

### `fuzz/`

Fuzz harnesses, corpora, crash artifacts, and minimized regression cases.

### `examples/`

Executable examples using documented public APIs only.

### `tools/`

Repository maintenance and release-support tools. Runtime code must never import from this directory.

### `docs/`

The authoritative architecture, decision, development, API, and user documentation.

## 9. Mandatory wheel and sdist isolation gate

Because source is at repository root, passing tests from the checkout is insufficient.

Packaging-sensitive acceptance must use this sequence:

```text
checkout
  ↓
build wheel + sdist
  ↓
create clean virtual environment
  ↓
install built wheel without editable mode
  ↓
change to a directory outside the checkout
  ↓
run isolated import and smoke tests
  ↓
validate installed inventory and metadata
```

Required checks:

- no repository `PYTHONPATH` injection;
- no editable install as release evidence;
- import works outside checkout;
- package resources and typing metadata are included;
- tests, tools, caches, credentials, and local files are excluded;
- CLI entry points resolve when defined;
- wheel and sdist metadata agree;
- sdist can rebuild the expected wheel;
- editable installation is tested separately for developer experience.

## 10. Parallel-development implications

The layout supports path-isolated work, for example:

```text
lingshu/http/** + tests/unit/http/**
lingshu/record/** + tests/unit/record/**
examples/** + docs/guides/**
```

Cross-cutting exclusive files include:

```text
lingshu/__init__.py
pyproject.toml
public API manifest
shared exceptions and identifiers
cross-component contract fixtures
root CI and release configuration
```

These remain serialized under ADR-001.

## 11. Future split criteria

A component may become a separate distribution only when a new ADR demonstrates:

- independent external consumers;
- a meaningful installation-size or dependency benefit;
- stable component contracts;
- independent release ownership;
- compatibility and version rules;
- isolated tests and CI;
- migration from the monolithic distribution;
- no loss of default framework usability.

Developer preference or theoretical purity is not sufficient.

## 12. Deferred decisions

- minimum Python version and platform matrix;
- build backend;
- exact public application/request/response and runtime API names;
- public API manifest mechanism;
- authoritative version-file mechanism;
- optional extras and official integrations;
- typing-marker details;
- first PyPI release timing;
- post-v1.0 compatibility guarantees.
