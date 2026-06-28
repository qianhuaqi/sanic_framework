# ADR-003: Package, source layout, and component boundaries

- Status: Proposed
- Date: 2026-06-28
- Parent architecture Issue: #25
- Decision Issue: #37

## Context

LingShu now has accepted decisions for repository governance and runtime concurrency. Before production implementation begins, all developers must use one physical source layout and one dependency model. Otherwise parallel contributors may create incompatible package structures, duplicate public contracts, or circular component dependencies.

The project lead has explicitly rejected adding a `src/` directory. The project also favors a simple initial release surface and does not want premature multi-distribution maintenance.

## Decision

### 1. One initial distribution

The initial framework is published as one Python distribution:

```text
lingshu
```

The import package is also:

```text
lingshu
```

The initial framework implementation uses one repository-level `pyproject.toml` and one version for the distribution.

Core, Runtime, HTTP, Server, Runtime Record, extension mechanisms, CLI, and test support are internal components of this distribution, not separately versioned or published distributions.

Splitting a component into another distribution later requires a dedicated ADR with evidence of independent consumers, dependency cost, release ownership, compatibility policy, and migration impact.

### 2. No `src/` layout

Production source is placed directly at the repository root:

```text
lingshu/
```

The repository must not create:

```text
src/lingshu/
packages/lingshu/
```

for the initial framework layout.

The absence of `src/` is compensated by mandatory wheel and isolated-install verification rather than by relying on repository-root imports.

### 3. Repository layout

The approved target layout is:

```text
lingshu/
├─ lingshu/
│  ├─ core/
│  ├─ runtime/
│  ├─ http/
│  ├─ server/
│  ├─ record/
│  ├─ extensions/
│  ├─ cli/
│  ├─ testing/
│  └─ __init__.py
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

This ADR authorizes the layout as architecture only. The directories and files are created later by an explicitly authorized P1 implementation Issue.

### 4. Component responsibilities

#### `lingshu.core`

Owns framework-wide stable mechanisms and contracts:

- Application Kernel;
- base lifecycle contracts and states;
- base exception taxonomy;
- configuration mechanism contracts;
- identifiers and common immutable value types;
- extension protocol contracts;
- generic audit and telemetry sink protocols;
- public capability registration contracts.

`core` must not depend on another LingShu component.

#### `lingshu.runtime`

Owns runtime execution semantics from ADR-002:

- Scope ownership;
- Deadline and cancellation mechanics;
- managed task groups and task supervision;
- admission control and bounded waiters;
- backpressure coordination;
- blocking-work executors;
- shutdown coordination primitives.

`runtime` may depend only on `core`.

#### `lingshu.http`

Owns HTTP application semantics independent of a specific network listener:

- Request and Response models;
- Headers, cookies, body and streaming contracts;
- routing and route matching;
- middleware pipeline;
- HTTP exception-to-response mapping;
- content negotiation and serialization interfaces approved later.

`http` may depend on `core` and `runtime`. It must not depend on `server`, `cli`, `testing`, or concrete official integrations.

#### `lingshu.server`

Owns native network and process execution:

- listeners and transports;
- HTTP/1.1 parser integration;
- connections and keep-alive;
- Supervisor and Worker execution;
- server startup, readiness, draining, stopping, and crash handling;
- transport read/write flow control.

`server` may depend on `core`, `runtime`, and `http`. It must not define business routing, authentication, database, tenant, or application policy.

#### `lingshu.record`

Owns the default request-level Runtime Record implementation:

- Request, Connection, Trace, and Operation identifiers after their standards are accepted;
- event envelopes and parent-child ordering;
- redaction and truncation mechanisms;
- bounded record queues;
- retention and cleanup contracts;
- default safe local writer mechanism;
- record failure and flush reporting.

`record` is installed as part of the default `lingshu` distribution because request-level auditability is a confirmed framework invariant.

Heavy external storage exporters are not core record dependencies. They attach through later extension decisions.

`record` may depend on `core` and stable `runtime` contracts. Lower components interact with record behavior through protocols rather than importing storage implementations.

#### `lingshu.extensions`

Owns extension hosting and composition mechanisms:

- extension registration and discovery mechanisms;
- dependency ordering and capability binding;
- extension lifecycle integration;
- health and cleanup hooks;
- optional capability activation.

It does not contain Auth, Tenant, RBAC, SQL, Redis, OpenAPI, or other policy implementations merely because those may later be extensions.

`extensions` may depend on `core` and `runtime`. HTTP-specific extensions may use documented `http` contracts without causing `http` to depend on `extensions`.

#### `lingshu.cli`

Owns the installed command-line interface and developer commands.

`cli` calls documented framework composition and public APIs. It must not bypass lifecycle rules or import private implementation details as a shortcut.

#### `lingshu.testing`

Owns framework-supported testing utilities:

- test client contracts;
- fake transports;
- fake monotonic clock support;
- deterministic cancellation and task barriers;
- application test harnesses;
- resource-leak assertions.

Production components must never depend on `testing`. Test-only third-party dependencies belong to development dependency groups, not mandatory runtime dependencies.

### 5. Dependency direction

The required primary direction is:

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
extensions  → core + runtime; optional documented http contracts
cli         → public composition surface
 testing    → public and explicit test-support surfaces
```

The package facade or composition root may assemble components, but lower components must not import the facade to reach higher layers.

Forbidden examples include:

```text
core → runtime/http/server/record/extensions/cli/testing
runtime → http/server/record/cli/testing
http → server/cli/testing
server → cli/testing or business integrations
production component → testing
```

Circular imports and dependency cycles are architecture violations.

### 6. Public API surface

The root package `lingshu` is the controlled public facade.

Only explicitly documented exports are public. No class or function name is frozen by this ADR; concrete names require later public-API decisions.

Rules:

- root exports use an explicit `__all__`;
- documented public subpackage imports may be supported when intentionally approved;
- deep internal imports are not public merely because Python can import them;
- modules or names beginning with `_` are private;
- wildcard re-export chains are prohibited;
- import-time side effects, connection creation, task startup, and process-global mutation are prohibited;
- private modules may change before v1.0 without compatibility guarantees.

### 7. Optional dependencies

One distribution does not mean every integration dependency is mandatory.

Later approved optional capabilities may use dependency extras or extension discovery, but:

- importing `lingshu` must not require database, Redis, cloud, tracing, or authentication packages;
- missing optional dependencies must fail only when the related capability is activated;
- optional integrations must not be imported at top-level package import time;
- an optional dependency must not become a hidden transitive core requirement.

The exact extras and official integration list are deferred.

### 8. Tests and repository support directories

- `tests/unit/`: component-local behavior;
- `tests/contract/`: public and cross-component contracts;
- `tests/integration/`: real component composition;
- `tests/protocol/`: HTTP and transport protocol behavior;
- `tests/concurrency/`: task, cancellation, backpressure, Worker, and shutdown behavior;
- `tests/security/`: malformed input, boundary, redaction, and trust tests;
- `tests/packaging/`: wheel, sdist, metadata, file inventory, and clean-install tests;
- `tests/compatibility/`: supported Python and platform behavior after support policy is accepted;
- `benchmarks/`: reproducible performance measurement, not correctness assertions;
- `fuzz/`: fuzz harnesses, corpora, and minimized regressions;
- `examples/`: executable user examples using only public APIs;
- `tools/`: repository maintenance tools, never imported by the runtime package;
- `docs/`: architecture, development, API, guides, and decisions.

### 9. Mandatory packaging quality gate

Because the source package is at repository root, passing tests from the checkout is insufficient.

Before a package-related change is accepted, CI must:

1. build both wheel and source distribution;
2. create a fresh isolated virtual environment;
3. install the built wheel without editable mode;
4. change the working directory outside the repository;
5. run import and smoke tests without repository `PYTHONPATH` injection;
6. validate installed package file inventory and metadata;
7. verify that excluded tests, tools, caches, secrets, and local files are not shipped;
8. verify CLI entry points when they exist;
9. repeat relevant checks against the source distribution;
10. test editable installation separately without treating it as release evidence.

The release smoke test should use isolated interpreter behavior where practical so the current checkout cannot mask missing package files.

### 10. Version ownership

The distribution has one authoritative version source. Individual internal components do not carry independent versions.

The exact version file or metadata mechanism is deferred to the packaging implementation Issue, but duplicated manually edited version strings are prohibited.

## Consequences

### Benefits

- direct and readable repository structure;
- one install command and one compatibility surface;
- lower release and dependency-management complexity;
- clear boundaries for parallel development;
- no premature component packaging;
- wheel isolation tests prevent repository-root imports from hiding packaging defects;
- future splitting remains possible through evidence-based ADRs.

### Costs

- all internal components share one release cadence;
- component boundaries require import checks because distribution boundaries do not enforce them;
- the root package can be accidentally imported from checkout unless CI isolation is strict;
- optional integration packaging requires careful extras and lazy imports.

## Rejected alternatives

- `src/lingshu/` layout;
- `packages/` monorepo layout for the initial framework;
- multiple initial distributions such as `lingshu-core` and `lingshu-server`;
- multiple component-level `pyproject.toml` files;
- independent internal component versions;
- production components importing `lingshu.testing`;
- considering every importable deep module part of the public API;
- relying only on editable installation or repository-root test runs as packaging evidence.

## Intentionally deferred

- minimum Python version;
- build backend;
- exact public class and function names;
- exact optional dependency extras;
- official extension implementations;
- PyPI release timing;
- public compatibility policy after v1.0.
