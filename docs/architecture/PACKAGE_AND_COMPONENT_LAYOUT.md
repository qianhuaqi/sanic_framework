# LingShu Package and Component Layout

- Status: Proposed for P0-D3
- Decision Issue: #37
- Parent Issue: #25
- Related ADR: `docs/decisions/ADR-003-package-source-layout-and-component-boundaries.md`

## 1. Purpose

This document translates the P0-D3 package and source-layout decision into an implementation-ready architecture contract without creating the package itself.

It defines:

- repository layout;
- distribution and import names;
- component responsibilities;
- allowed and forbidden dependency directions;
- public API boundaries;
- optional dependency behavior;
- test and packaging quality gates.

## 2. Canonical names

```text
Repository:           qianhuaqi/lingshu
Distribution:         lingshu
Import package:       lingshu
Root packaging file:  pyproject.toml
Production source:    lingshu/
src layout:           prohibited
```

The repository, distribution, and import package intentionally use the same name to reduce cognitive overhead.

## 3. Target repository tree

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

This is a target layout only. P0 must not create the production tree. P1 creates it under an implementation Issue after P0 is frozen.

## 4. Component map

### 4.1 `core`

Role: stable framework kernel mechanisms.

Owns:

- application lifecycle contracts;
- base state models;
- common immutable values and identifiers;
- base exception taxonomy;
- configuration contracts;
- extension contracts;
- generic capability registration;
- audit and telemetry sink interfaces;
- protocol-neutral shared primitives.

Must not own:

- HTTP parsing;
- network listeners;
- routing policy tied to HTTP;
- database, authentication, tenant, cache, or business policy;
- concrete record storage;
- test helpers.

Allowed internal dependencies: none.

### 4.2 `runtime`

Role: asynchronous execution and resource ownership.

Owns:

- Scope hierarchy;
- Deadline and cancellation behavior;
- managed task creation and supervision;
- admission limiters;
- bounded waiter queues;
- backpressure coordination;
- thread/process executor boundaries;
- shutdown and drain primitives;
- runtime-local context mechanisms.

Allowed dependencies:

```text
runtime → core
```

Forbidden dependencies:

```text
runtime → http/server/record/extensions/cli/testing
```

### 4.3 `http`

Role: application-facing HTTP semantics independent of listener/process management.

Owns:

- request and response abstractions;
- headers, cookies, body streams, and response streams;
- route definitions and matching;
- middleware execution plan;
- HTTP status and error mapping;
- content-type and serialization extension contracts;
- HTTP-specific application context.

Allowed dependencies:

```text
http → core
http → runtime
```

Forbidden dependencies:

```text
http → server/cli/testing
http → concrete database/auth/cache integrations
```

### 4.4 `server`

Role: native transport, parser, Worker, and process runtime.

Owns:

- TCP listeners and transports;
- HTTP/1.1 parsing integration;
- connection lifecycle;
- keep-alive and read-ahead limits;
- Supervisor and Worker execution;
- readiness, drain, stop, restart, and crash handling;
- transport-level flow control;
- dispatch from accepted request to the HTTP application pipeline.

Allowed dependencies:

```text
server → core
server → runtime
server → http
```

Forbidden dependencies:

```text
server → cli/testing
server → business policy or concrete external integrations
```

### 4.5 `record`

Role: default request-level Runtime Record implementation.

Owns:

- record event envelopes;
- request/connection/trace/operation identity mapping;
- parent-child ordering metadata;
- default redaction and truncation;
- bounded write queues;
- safe local writer mechanism;
- retention and cleanup contracts;
- flush, failure, drop, and truncation reporting.

The module ships in the default distribution because request-level auditability is a confirmed invariant.

Allowed dependencies:

```text
record → core
record → stable runtime contracts
```

Interaction rule:

- `core`, `runtime`, `http`, and `server` emit through generic protocols or event contracts;
- lower layers do not import concrete storage writers;
- external exporters attach later through extension mechanisms.

### 4.6 `extensions`

Role: extension hosting, discovery, lifecycle, and capability composition.

Owns:

- extension registration;
- dependency ordering;
- capability binding;
- startup and shutdown integration;
- health and cleanup hooks;
- lazy optional capability activation.

Does not own concrete Auth, Tenant, RBAC, SQL, Redis, OpenAPI, or cloud integrations by default.

Allowed dependencies:

```text
extensions → core
extensions → runtime
extensions → documented http contracts when required
```

Constraint:

```text
http ↛ extensions
```

HTTP-specific extension implementations may depend on both, but HTTP itself does not depend on the host package.

### 4.7 `cli`

Role: installed command-line interface.

Owns:

- command parsing;
- project and configuration validation commands;
- run and development commands after later approval;
- human-readable diagnostics.

Rules:

- uses public composition surfaces;
- does not bypass lifecycle and validation rules;
- does not become an import dependency of production runtime components;
- command implementation details are not public Python API by default.

### 4.8 `testing`

Role: framework-supported deterministic test utilities.

Owns:

- test client;
- fake transport;
- fake monotonic clock;
- deterministic task barriers and cancellation injection;
- runtime resource snapshots;
- leak assertions;
- application test harnesses.

Rules:

- no production component may depend on `testing`;
- heavy test tools are development dependencies, not mandatory runtime dependencies;
- test-support public API may have a separate stability level from production API.

## 5. Dependency graph

Primary production graph:

```text
             core
            ↗  ↑  ↖
      runtime  │  record
       ↑   ↖   │
      http  extensions
       ↑
     server
```

More explicitly:

```text
runtime     → core
http        → runtime + core
server      → http + runtime + core
record      → core + stable runtime contracts
extensions  → core + runtime (+ documented http contracts when needed)
cli         → public composition surface
testing     → public/test-support surfaces
```

No component may import upward merely to reuse a convenience function. Shared lower-level behavior moves to the correct lower component only after architectural review.

## 6. Cycle prevention

Dependency cycles are prohibited even inside one distribution.

P1 must introduce machine checks that validate import boundaries. At minimum, the checks must detect:

- `core` importing another LingShu component;
- `runtime` importing higher components;
- `http` importing `server`;
- production modules importing `testing`;
- lower modules importing the root `lingshu` facade;
- cross-component private-module imports;
- newly introduced cycles.

A boundary exception requires an Issue and ADR amendment, not a local ignore comment.

## 7. Root facade

`lingshu/__init__.py` is a controlled export facade.

Rules:

- explicit `__all__` only;
- no wildcard import chains;
- no connection, task, process, file, environment, or logging side effects at import time;
- no optional integration import at package import time;
- only intentionally documented names are public;
- deep module paths are private unless documentation explicitly promotes them;
- names beginning with `_` are private;
- public exports require contract tests.

This decision does not freeze concrete class names such as the application, request, or response class. Those names are decided later.

## 8. Public and private subpackages

A subpackage being visible does not automatically make all of it public.

Possible stability levels:

```text
Public facade       documented and compatibility-managed
Public subpackage   explicitly documented and contract-tested
Extension contract  public for extension authors
Test-support API    public with separate stability statement
Internal            no compatibility promise before v1.0
```

The exact public API manifest is a later decision, but P1 must make public exports explicit and reviewable.

## 9. Optional capability rules

One distribution is compatible with optional capabilities.

Rules:

- core import must remain lightweight;
- optional dependencies load only when the capability is activated;
- a missing optional dependency produces a focused activation error;
- database, Redis, cloud, tracing, and authentication libraries are not mandatory merely because an extension exists;
- extras must be coherent capability groups, not undocumented dependency buckets;
- importing one optional capability must not load unrelated integrations.

The exact extras and official extension catalog remain deferred.

## 10. Packaging configuration

The repository has one root `pyproject.toml`.

It eventually owns:

- build system configuration;
- distribution metadata;
- authoritative version configuration;
- runtime dependencies;
- optional dependency groups;
- development dependency groups;
- CLI entry points;
- package discovery;
- included resources and type information;
- test, lint, typing, and build-tool configuration where appropriate.

This decision does not choose a build backend or Python minimum version.

## 11. Version rule

All internal components share the distribution version.

Prohibited:

- independent `core`, `http`, or `server` version constants;
- manually duplicated version strings;
- component-specific release tags;
- partial release of only one internal component.

A later packaging Issue chooses one authoritative version source.

## 12. Wheel isolation gate

Root-level source creates a risk that tests import the checkout instead of the built artifact. Therefore every packaging-sensitive acceptance run must use this sequence:

```text
checkout
  ↓
build wheel + sdist
  ↓
create clean virtual environment
  ↓
install built wheel
  ↓
change to a temporary directory outside checkout
  ↓
run isolated import and smoke tests
  ↓
validate installed file inventory and metadata
```

Required checks:

- no repository `PYTHONPATH` injection;
- no editable installation as release evidence;
- import works from outside the checkout;
- package resources and type metadata are included;
- tests, tools, caches, credentials, and local files are excluded;
- CLI entry points resolve after installation when defined;
- wheel and sdist metadata agree;
- sdist can rebuild the expected wheel;
- editable installation is tested separately for developer experience.

## 13. Test directory responsibilities

### `tests/unit/`

Fast component-local behavior with controlled dependencies.

### `tests/contract/`

Public facade, extension, lifecycle, and cross-component contracts.

### `tests/integration/`

Real composition between framework components and resources.

### `tests/protocol/`

HTTP parsing, framing, malformed input, keep-alive, and transport behavior.

### `tests/concurrency/`

Scope ownership, cancellation, Deadline, Worker, backpressure, saturation, shutdown, and leak behavior.

### `tests/security/`

Trust boundaries, redaction, resource limits, protocol ambiguity, and unsafe defaults.

### `tests/packaging/`

Wheel, sdist, metadata, package inventory, entry points, isolated install, and import checks.

### `tests/compatibility/`

Python/platform compatibility after the support matrix is confirmed.

## 14. Other root directories

### `benchmarks/`

Reproducible performance measurement. Benchmarks do not replace correctness tests.

### `fuzz/`

Fuzz harnesses, corpora, crash artifacts, and minimized regression cases.

### `examples/`

Executable examples using documented public APIs only. Examples must not import private implementation modules.

### `tools/`

Repository maintenance and release-support tools. The runtime distribution must never import from this directory.

### `docs/`

The authoritative architecture, decision, development, API, and user documentation.

## 15. Parallel development write scopes

The chosen layout supports path-isolated work after P1 creates it.

Example independent scopes:

```text
lingshu/http/** + tests/unit/http/**
lingshu/record/** + tests/unit/record/**
examples/** + docs/guides/**
```

Potentially conflicting scopes:

```text
lingshu/__init__.py
pyproject.toml
shared exceptions and identifiers
public API manifest
cross-component contract fixtures
root CI configuration
```

Cross-cutting files retain exclusive integration status under ADR-001.

## 16. Future split criteria

A component may become a separate distribution only when an ADR demonstrates all of:

- independent external consumers;
- a meaningful installation-size or dependency benefit;
- stable component contract;
- independent release ownership;
- version compatibility rules;
- test and CI isolation;
- migration path from the monolithic distribution;
- no loss of default framework usability.

Developer preference or theoretical purity is not sufficient evidence.

## 17. Deferred decisions

- minimum Python version and platform matrix;
- build backend;
- public application/request/response API names;
- public API manifest format;
- exact version source;
- optional extras and official integration catalog;
- type stub and typing-marker details;
- first PyPI release timing;
- post-v1.0 compatibility guarantees.

## 18. Acceptance rule

Merging the P0-D3 decision PR accepts the package and component architecture. It does not authorize creation of the production package. Directory and packaging implementation begins only after the full P0 Blueprint is frozen and P1 is explicitly authorized.
