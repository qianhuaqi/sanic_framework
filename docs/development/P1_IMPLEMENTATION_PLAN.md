# P1 Implementation Plan

- Status: Proposed by P0-D7; not executable until Final Freeze
- Parent architecture Issue: #25
- Decision Issue: #49
- Planned phase: P1 - Single-Worker Minimum Vertical Slice
- Planned first development version: `0.1.0.dev0`

## 1. P1 objective

P1 creates the first independently implemented, installable, tested LingShu vertical slice:

```text
package + CI
→ core primitives
→ runtime scopes
→ HTTP data model
→ Router/Middleware
→ Application Kernel
→ Runtime Record minimum
→ single-Worker HTTP/1.1 Server
→ CLI run/check/version with --workers 1
→ clean wheel/sdist verification
```

P1 proves the accepted architecture through a narrow but real request path. It is not a production-ready public release.

## 2. P1 user-visible success case

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

A client can send a basic HTTP/1.1 request and receive a correct response while RequestId, Runtime Record, Deadline, cancellation, cleanup, and package-boundary rules remain observable and tested.

## 3. Explicit P1 scope

P1 includes:

- root `pyproject.toml` with Hatchling and version `0.1.0.dev0`;
- root package layout `lingshu/`, never `src/lingshu/`;
- initial package components and explicit root exports;
- CI foundations for required Python/platform matrix as capacity permits;
- time, typed identifiers, framework errors, error codes, and safe problem response primitives;
- immutable configuration Snapshot sufficient for static startup configuration;
- Deadline, cancellation reason, Scope ownership, structured task registry, and bounded admission primitives;
- HTTP method/target/version/header/request/response/body foundations;
- bounded request body and response commit state;
- deterministic Router with static and path-parameter routes;
- 404 versus 405;
- Application and Route Middleware with deterministic onion ordering;
- asynchronous Handler contract and supported return normalization;
- Application Revision, freeze, immutable Plan, and lifecycle transitions;
- minimum required Runtime Record reservation, append-only events, bounded queue, and safe local writer;
- one HTTP/1.1 request at a time per connection;
- basic Keep-Alive under bounded policy;
- protocol parse limits and safe failure for the supported subset;
- single-Worker `Server`, `ServerConfig`, and `serve`;
- CLI `version`, `check`, and `run --workers 1`;
- wheel/sdist, clean non-editable install, outside-checkout smoke tests, and artifact inventory.

## 4. Explicitly not in P1

- multi-Worker Supervisor implementation;
- listener handle transfer between processes;
- development file watcher/reload;
- production configuration hot reload or multi-Worker rollout;
- HTTP pipelined concurrent execution;
- HTTP/2, HTTP/3, WebSocket, ASGI, or WSGI adapters;
- streaming response API beyond internal bounded body primitives;
- form, multipart, file uploads, compression, or content encodings;
- automatic HEAD/OPTIONS;
- host routing, reverse routing, mounts, or sub-applications;
- sync Handler adaptation;
- dependency injection;
- OpenAPI;
- official Auth, Tenant, RBAC, SQL, Redis, Cache, Scheduler, Storage, or Observability extensions;
- public PyPI production release;
- performance claims or benchmark promises.

## 5. P1 Issue graph

The exact GitHub numbers are created only after Final Freeze. Symbolic IDs become Issue titles and dependency contracts.

### P1-00: Package, tooling, CI, and governance enforcement

Task class: cross-cutting exclusive.

Write scope:

```text
pyproject.toml
lingshu/__init__.py
lingshu/__main__.py
initial empty component package markers
tests packaging/test harness foundations
.github/workflows/
tooling configuration
README setup section
```

Delivers:

- `0.1.0.dev0` metadata;
- Hatchling build;
- DCO/license/package inventory checks;
- no-src package skeleton;
- root export placeholder contract;
- base test/lint/type/build commands;
- initial CI matrix and clean-install job.

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

Delivers wall/monotonic interfaces, typed identifiers, secure generation, stable error metadata, cancellation-preserving exception boundaries, and safe details/redaction primitives.

Depends on P1-00.

### P1-02: Static configuration Snapshot and schema validation

Task class: independent after core contracts.

Write scope:

```text
lingshu/core/config*.py
configuration tests
```

Delivers defaults/file-environment-programmatic normalization contracts needed for P1 startup, immutable Snapshot, secret redaction, unknown-key rejection, and Revision input material.

Does not implement runtime hot reload.

Depends on P1-01.

### P1-03: Runtime Deadline, Scope, cancellation, tasks, and admission

Task class: foundation provider.

Write scope:

```text
lingshu/runtime/
runtime tests
```

Delivers absolute Deadline, cancellation reason, Application/Connection/Request/Operation Scope ownership, registered child tasks, bounded cleanup, and bounded admission primitives.

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

Delivers immutable request metadata, normalized headers, single-consumer bounded body, Response factories, NEW/PREPARED/COMMITTED/COMPLETED/ABORTED state, and return normalization for Response/str/bytes-like.

Depends on P1-01 and stable Scope contracts from P1-03.

### P1-05: Router and Middleware compiler

Task class: ordered dependency.

Write scope:

```text
lingshu/http/router*.py
lingshu/http/middleware*.py
router/middleware tests
```

Delivers static and path-parameter matching, method matching, 404/405, ambiguity validation, deterministic priority/registration ordering, route/application chains, and single-use Scope-bound `call_next`.

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

Delivers `LingShu`, route decorators, registration catalogs, immutable Application Revision/Plan, freeze atomicity, lifecycle states, Handler signature validation, extension placeholder protocol, and exception-mapper resolution.

Depends on P1-02, P1-03, P1-04, and P1-05.

### P1-07: Minimum Runtime Record subsystem

Task class: independent provider after core/runtime contracts.

Write scope:

```text
lingshu/record/
record tests
```

Delivers RecordId reservation before Handler, versioned event envelope, bounded queue, required/best-effort policy primitives, append-only JSON Lines segments, safe path containment, atomic manifest, soft/hard watermark handling, bounded shutdown flush, and minimal crash-tail recovery.

Depends on P1-01 and P1-03. Integration with Kernel/Server occurs after P1-06.

### P1-08: Native single-Worker HTTP/1.1 Server

Task class: ordered integration.

Write scope:

```text
lingshu/server/
HTTP/1.1 parser/transport implementation paths
server/protocol tests
```

Delivers one event loop, listener, bounded connections, request parse subset, one active request per connection, basic Keep-Alive, Request pipeline integration, Deadline/cancellation, response commit/write, disconnect behavior, drain, idempotent close, and no global signals by default.

Depends on P1-03, P1-04, P1-06, and P1-07.

### P1-09: CLI version/check/run for one Worker

Task class: ordered integration.

Write scope:

```text
lingshu/cli/
lingshu/__main__.py
CLI tests
```

Delivers strict `module:attribute`, synchronous zero-argument `--factory`, `version`, `check`, `run --workers 1`, stable applicable exit codes, main-thread blocking `serve`, and safe diagnostics.

Rejects `--workers > 1` with a documented not-yet-implemented diagnostic rather than silently changing semantics.

Depends on P1-06 and P1-08.

### P1-10: Vertical-slice integration, security, packaging, and documentation

Task class: cross-cutting exclusive final integration.

Write scope:

```text
integration/contract/security tests
examples/
README and user docs
CHANGELOG.md
packaging inventory rules
release-candidate evidence
```

Delivers end-to-end request, cancellation/disconnect, record, shutdown, package install, CLI, Windows/Linux/macOS, and negative security tests. It removes no P0 requirement and documents all P1 deferrals.

Depends on all preceding P1 Issues.

## 6. Parallel execution waves

```text
Wave 0
  P1-00

Wave 1
  P1-01

Wave 2, parallel after stable contracts
  P1-02 configuration
  P1-03 runtime

Wave 3
  P1-04 HTTP model (after P1-03 Scope contract)
  P1-07 Record core (after P1-03)

Wave 4
  P1-05 Router/Middleware (after P1-04)

Wave 5
  P1-06 Application Kernel (after P1-02/03/04/05)

Wave 6
  P1-08 Server (after P1-06 and P1-07)

Wave 7
  P1-09 CLI

Wave 8
  P1-10 final integration
```

Provider Issues merge before consumers. Development may overlap only where declared write scopes do not overlap and consumed contracts are already merged.

## 7. Branch and integration rules

Each P1 Issue uses:

```text
one Issue
one writer-prefixed branch
one primary writer
one isolated worktree/clone
one virtual environment
one Pull Request
```

Every P1 Issue body must copy its symbolic dependency, exact base commit, write scope, conflicts, required checks, and integration order from this plan.

No P1 Issue is opened before Final Freeze unless marked `planning-only` and blocked.

## 8. P1 acceptance matrix

### Packaging

- `python -m build` produces one pure wheel and one sdist;
- non-editable wheel installs into a fresh CPython 3.12 environment outside checkout;
- `import lingshu`, `lingshu version`, and `python -m lingshu version` succeed;
- artifact inventory excludes tests/tools/secrets/records/caches;
- version is `0.1.0.dev0` from installed metadata.

### Public imports

```python
from lingshu import LingShu, Request, Response, HTTPException
from lingshu.server import Server, ServerConfig, serve
```

No import starts tasks, opens files, binds sockets, or imports user applications.

### Application and routing

- freeze is atomic and idempotent for unchanged Revision;
- mutation after freeze fails;
- static/path-parameter routes work;
- duplicate/ambiguous routes fail before startup;
- 404 and 405 are distinct;
- Middleware ordering and short-circuiting are deterministic;
- `call_next` cannot be called twice or after Scope completion.

### Request and Response

- Request metadata is immutable;
- body is bounded, backpressured, and single-consumer;
- supported Handler results normalize once;
- unsupported returns fail safely;
- response head commits once;
- post-commit errors abort rather than generate a second response.

### Runtime

- Deadline uses monotonic budget and is not reset by nested layers;
- cancellation propagates;
- request-owned tasks are awaited/cancelled during cleanup;
- no task, connection, request, body, or state leak under stress tests;
- admission and queues are bounded.

### Runtime Record

- business handling does not start before required record reservation;
- event sequence is monotonic per record;
- sensitive values are not emitted by default;
- queue/storage saturation produces explicit behavior;
- partial final lines recover safely;
- hard watermark marks not-ready and rejects required requests.

### Server

- one active HTTP/1.1 request per connection;
- supported parser subset rejects ambiguous/oversized input;
- basic Keep-Alive remains bounded;
- client disconnect cancels the request path;
- drain stops admission and completes/cancels within budgets;
- startup failure leaves no partial listener;
- Server close is idempotent.

### CLI

- target grammar cannot evaluate expressions;
- instance/factory modes work;
- `check` binds no listener;
- `run --workers 1` serves the example;
- `--workers > 1` fails explicitly as deferred;
- exit codes and redacted diagnostics match contracts.

### Cross-platform and quality

- required Linux, Windows, and macOS checks pass according to the P1 CI scope;
- preview Python result is visible;
- public API and package-boundary checks pass;
- no mandatory runtime dependency exists unless separately approved;
- security negative tests show no traceback, secret, path, raw body, or configuration leak.

## 9. P1 exit condition

P1 completes only after P1-10 is merged and the project lead confirms the vertical slice meets this acceptance matrix.

P1 completion does not automatically authorize public PyPI publication or multi-Worker implementation.
