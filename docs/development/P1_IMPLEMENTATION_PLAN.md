# P1 Implementation Plan

- Status: Authorized when PR #51 is merged
- Authorization event: project-lead merge of PR #51
- Authoritative P0 freeze commit: PR #51 merge commit
- Parent P0 Issue: #25 (closed by PR #51)
- Final P0 decision Issue: #49 (closed by PR #51)
- Phase: P1 - Single-Worker Minimum Vertical Slice
- First development version: `0.1.0.dev0`
- First executable Issue: P1-00, created only after PR #51 merges

## 1. Objective

P1 creates the first independently implemented, installable, tested LingShu vertical slice:

```text
package + CI
→ core primitives
→ runtime scopes
→ HTTP data model
→ Router/Middleware
→ Application Kernel
→ minimum Runtime Record
→ single-Worker HTTP/1.1 Server
→ CLI run/check/version with --workers 1
→ clean wheel/sdist verification
```

P1 proves the frozen architecture through one narrow real request path. It is not a production-ready or public stable release.

## 2. User-visible success case

After P1 acceptance, a clean environment can install the wheel and run:

```python
from lingshu import LingShu, Request, Response

app = LingShu()

@app.get("/")
async def index(request: Request) -> Response:
    return Response.text("hello")
```

```text
lingshu check example:app
lingshu run example:app --workers 1
```

A basic HTTP/1.1 client receives a correct response while RequestId, Runtime Record, absolute Deadline, cancellation, cleanup, bounded resources, safe errors, and package boundaries remain observable and tested.

## 3. Explicit scope

P1 includes:

- root `pyproject.toml` with Hatchling and version `0.1.0.dev0`;
- root package layout `lingshu/`, never `src/lingshu/`;
- initial component packages and explicit root exports;
- CI/tooling/package-governance foundations;
- wall/monotonic time, typed identifiers, framework errors, stable error codes, and safe problem details;
- immutable configuration Snapshot sufficient for static startup configuration;
- Deadline, cancellation reason, Scope ownership, registered child tasks, bounded cleanup, and admission;
- HTTP method, target, version, headers, Request, Response, body, and commit-state foundations;
- bounded single-consumer request body;
- deterministic Router with static and path-parameter routes;
- 404 versus 405;
- Application and Route Middleware with deterministic onion ordering;
- asynchronous Handler contract and supported return normalization;
- Application Revision, freeze, immutable Plan, and lifecycle transitions;
- minimum required Runtime Record reservation, append-only events, bounded queue, and safe local writer;
- one active HTTP/1.1 request per connection;
- basic bounded Keep-Alive;
- protocol parse limits and safe failure for the supported subset;
- single-Worker `Server`, `ServerConfig`, and `serve`;
- CLI `version`, `check`, and `run --workers 1`;
- wheel/sdist, clean non-editable install, outside-checkout smoke tests, and artifact inventory.

## 4. Explicit exclusions

P1 does not include:

- public PyPI production publication;
- production-readiness or performance claims;
- multi-Worker Supervisor implementation;
- listener handle transfer between processes;
- development file watcher/reload;
- production configuration hot reload or multi-Worker rollout;
- HTTP pipelined concurrent execution;
- HTTP/2, HTTP/3, WebSocket, ASGI, or WSGI adapters;
- public streaming response API beyond internal bounded body primitives;
- form, multipart, file uploads, compression, or content encodings;
- automatic HEAD/OPTIONS;
- host routing, reverse routing, mounts, or sub-applications;
- sync Handler adaptation;
- dependency injection;
- OpenAPI;
- official Auth, Tenant, RBAC, SQL, Redis, Cache, Scheduler, Storage, or Observability integrations;
- changes to frozen P0 decisions without a new Issue and ADR.

## 5. Issue graph

Exact GitHub numbers are created after PR #51 merges. Symbolic IDs become Issue-title prefixes and dependency contracts.

### P1-00: Package, tooling, CI, and governance enforcement

Task class: cross-cutting exclusive.

Base commit:

```text
PR #51 merge commit
```

Write scope:

```text
pyproject.toml
lingshu/__init__.py
lingshu/__main__.py
initial empty component package markers
initial tests/package harness
.github/workflows/
tooling configuration
README setup section
package inventory/governance checks
```

Delivers:

- version `0.1.0.dev0`;
- Hatchling build and PEP 621 metadata;
- Apache-2.0 metadata and NOTICE inclusion rules;
- root package with no `src/` directory;
- root export placeholder contract;
- base test, lint, type, build, DCO, license, and package-boundary commands;
- initial CI matrix and clean-install job;
- no framework behavior assigned to later Issues.

All later P1 work depends on P1-00.

### P1-01: Core time, identifiers, errors, and safe problem details

Task class: foundation provider.

Write scope:

```text
lingshu/core/time*.py
lingshu/core/ident*.py
lingshu/core/errors*.py
corresponding tests
```

Delivers:

- wall and monotonic clock interfaces;
- typed secure identifiers;
- stable framework-error metadata and dotted codes;
- safe problem details and redaction primitives;
- cancellation-preserving exception boundaries.

Depends on P1-00.

### P1-02: Static configuration Snapshot and schema validation

Task class: independent provider after P1-01.

Write scope:

```text
lingshu/core/config*.py
configuration tests
```

Delivers:

- P1 startup configuration source precedence;
- schema normalization and unknown-key rejection;
- immutable typed Snapshot;
- protected-value redaction;
- canonical Revision input material.

Does not implement runtime hot reload.

Depends on P1-01.

### P1-03: Runtime Deadline, Scope, cancellation, tasks, and admission

Task class: foundation provider.

Write scope:

```text
lingshu/runtime/
runtime tests
```

Delivers:

- absolute Deadline;
- cancellation reason and propagation;
- Application, Connection, Request, and Operation Scope ownership;
- registered child-task lifecycle;
- bounded cleanup and admission primitives;
- leak and race tests.

Depends on P1-01.

### P1-04: HTTP value model and bounded body/response state

Task class: foundation provider.

Write scope:

```text
lingshu/http/message*.py
lingshu/http/request*.py
lingshu/http/response*.py
lingshu/http/body*.py
HTTP model tests
```

Delivers:

- immutable Request metadata;
- normalized bounded headers;
- single-consumer bounded body;
- Response factories;
- NEW, PREPARED, COMMITTED, COMPLETED, and ABORTED states;
- exactly-once normalization for Response, str, and bytes-like values.

Depends on P1-01 and stable Scope contracts from P1-03.

### P1-05: Router and Middleware compiler

Task class: ordered provider.

Write scope:

```text
lingshu/http/router*.py
lingshu/http/middleware*.py
router/middleware tests
```

Delivers:

- static and path-parameter matching;
- method matching, 404, and 405;
- duplicate/ambiguity validation;
- deterministic priority and registration ordering;
- Application and Route Middleware chains;
- single-use Scope-bound `call_next`.

Depends on P1-04.

### P1-06: Application Kernel, Revision, freeze, and lifecycle

Task class: cross-cutting integration provider.

Write scope:

```text
lingshu/core/application*.py
lingshu/core/plan*.py
root facade integration
Application tests
```

Delivers:

- `LingShu` and route decorators;
- registration catalogs;
- immutable Application Revision and Plan;
- atomic/idempotent freeze for unchanged Revision;
- lifecycle states;
- Handler signature and return-contract validation;
- extension placeholder protocol;
- exception-mapper resolution.

Depends on P1-02, P1-03, P1-04, and P1-05.

### P1-07: Minimum Runtime Record subsystem

Task class: provider after core/runtime contracts.

Write scope:

```text
lingshu/record/
record tests
```

Delivers:

- RecordId reservation before Handler;
- versioned event envelope and per-record sequence;
- bounded queue and required/best-effort policy primitives;
- append-only JSON Lines segments;
- safe path containment and atomic manifest;
- soft/hard watermark behavior;
- bounded shutdown flush and minimal crash-tail recovery;
- redaction and saturation tests.

Depends on P1-01 and P1-03. Integration with Kernel/Server occurs after P1-06.

### P1-08: Native single-Worker HTTP/1.1 Server

Task class: ordered integration.

Write scope:

```text
lingshu/server/
HTTP/1.1 parser/transport implementation paths
server/protocol tests
```

Delivers:

- one event loop and listener;
- bounded connections;
- accepted HTTP/1.1 parse subset;
- one active request per connection;
- basic bounded Keep-Alive;
- Request pipeline integration;
- Deadline, cancellation, disconnect, commit, write, and cleanup behavior;
- drain and idempotent close;
- no global signal installation by default.

Depends on P1-03, P1-04, P1-06, and P1-07.

### P1-09: CLI version/check/run for one Worker

Task class: ordered integration.

Write scope:

```text
lingshu/cli/
lingshu/__main__.py
CLI tests
```

Delivers:

- strict `module:attribute` parsing;
- synchronous zero-argument `--factory`;
- `version`, `check`, and `run --workers 1`;
- applicable stable exit codes;
- main-thread blocking `serve`;
- safe diagnostics.

`--workers > 1` fails explicitly as deferred rather than changing semantics.

Depends on P1-06 and P1-08.

### P1-10: Vertical-slice integration, security, packaging, and documentation

Task class: cross-cutting exclusive final integration.

Write scope:

```text
integration/contract/security tests
examples/
README and user documentation
CHANGELOG.md
package inventory rules
P1 acceptance evidence
```

Delivers:

- end-to-end request/response path;
- cancellation/disconnect and graceful shutdown tests;
- Runtime Record and hard-watermark tests;
- package install and CLI tests;
- required cross-platform checks;
- negative security/redaction tests;
- final P1 documentation and explicit deferrals.

Depends on all preceding P1 Issues.

## 6. Parallel waves

```text
Wave 0
  P1-00

Wave 1
  P1-01

Wave 2 after P1-01
  P1-02 configuration
  P1-03 runtime

Wave 3 after stable P1-03 contracts
  P1-04 HTTP model
  P1-07 Record core

Wave 4
  P1-05 Router/Middleware

Wave 5
  P1-06 Application Kernel

Wave 6
  P1-08 Server

Wave 7
  P1-09 CLI

Wave 8
  P1-10 final integration
```

Development may overlap only when:

- declared write scopes do not overlap;
- provider contracts are already merged;
- Issues explicitly declare the parallel relationship;
- integration into `main` remains serial.

## 7. Branch and integration rules

Every P1 task uses:

```text
one Issue
one writer-prefixed branch
one primary writer
one isolated worktree/clone
one virtual environment
one Pull Request
```

Every Issue must include:

- exact `base_commit`;
- `primary_writer`;
- `write_scope`;
- `read_dependencies`;
- `depends_on`;
- `conflicts_with`;
- `integration_order`;
- `required_checks`;
- explicit exclusions.

No direct commits to `main`, shared writable workspace, multi-writer branch, auto-merge, or consumer-before-provider merge.

## 8. Acceptance matrix

### Packaging

- isolated build produces one pure wheel and one sdist;
- non-editable wheel installs in a fresh CPython 3.12 environment outside checkout;
- `import lingshu`, `lingshu version`, and `python -m lingshu version` succeed;
- version is `0.1.0.dev0` from installed metadata;
- artifact inventory excludes tests, tools, secrets, Runtime Records, caches, and local configuration;
- wheel reconstructed from sdist has expected metadata/inventory;
- editable developer install is tested separately;
- uninstall removes package-owned files cleanly.

### Public imports

```python
from lingshu import LingShu, Request, Response, HTTPException
from lingshu.server import Server, ServerConfig, serve
```

No import starts tasks, opens files, binds sockets, or imports user applications.

### Application and routing

- freeze is atomic and idempotent for unchanged Revision;
- mutation after freeze fails;
- static and path-parameter routes work;
- duplicate/ambiguous routes fail before startup;
- 404 and 405 are distinct;
- Middleware ordering and short-circuiting are deterministic;
- `call_next` cannot be used twice or outside its Scope.

### Request and Response

- Request metadata is immutable;
- body is bounded, backpressured, and single-consumer;
- supported Handler results normalize exactly once;
- unsupported returns fail safely;
- response head commits once;
- post-commit errors abort rather than generate a second response.

### Runtime

- Deadline uses monotonic budget and never resets in nested layers;
- cancellation propagates;
- request-owned tasks are awaited or cancelled during cleanup;
- no task, connection, request, body, context, or state leak under stress;
- admission, queues, and cleanup are bounded.

### Runtime Record

- required record reservation precedes business handling;
- event sequence is monotonic per record;
- sensitive values are not emitted by default;
- queue/storage saturation has explicit behavior;
- partial final lines recover safely;
- hard watermark marks not-ready and rejects required requests.

### Server

- one active HTTP/1.1 request per connection;
- supported parser subset rejects ambiguous or oversized input;
- Keep-Alive remains bounded;
- client disconnect cancels the request path;
- drain stops admission and completes/cancels within budgets;
- startup failure leaves no partial listener;
- close is idempotent.

### CLI

- target grammar cannot evaluate expressions or scan implicitly;
- instance and factory modes work;
- `check` binds no listener;
- `run --workers 1` serves the example;
- `--workers > 1` fails explicitly as deferred;
- exit codes and diagnostics match the frozen contract;
- diagnostics expose no traceback, secret, path, raw body, or protected configuration by default.

### Cross-platform and quality

- required Linux, Windows, and macOS checks pass according to P1 CI scope;
- preview Python result is visible;
- public API/export and package-boundary checks pass;
- no mandatory runtime dependency exists unless separately approved;
- DCO, license, NOTICE, changelog, and package inventory checks pass.

## 9. Exit condition

P1 completes only after P1-10 is merged and the project lead confirms this acceptance matrix.

P1 completion does not automatically authorize public package publication, production-readiness claims, multi-Worker implementation, or changes outside the frozen architecture.
