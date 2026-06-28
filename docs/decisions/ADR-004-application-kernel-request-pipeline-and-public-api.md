# ADR-004: Application Kernel, request pipeline, and minimum public API

- Status: Proposed
- Date: 2026-06-28
- Parent architecture Issue: #25
- Decision Issue: #40

## Context

LingShu has accepted repository, runtime-concurrency, and physical component boundaries. The next architecture boundary is the application itself: how configuration is composed, when routes and middleware become immutable, how a request moves through the framework, when a response becomes irreversible, and which names form the minimum public API.

Without a fixed execution contract, concurrent implementation could produce incompatible middleware ordering, route mutation races, ambiguous handler returns, double responses, hidden import-time registration, and exception behavior that changes after bytes are sent.

## Decision

### 1. Public composition root and internal Kernel

The public application type is `LingShu`.

`LingShu` is the composition root exposed by the root package. It assembles approved Core, Runtime, HTTP, Server, Record, Extension, CLI, and Testing surfaces without forcing lower components to import the root facade.

The low-level Application Kernel remains an internal `lingshu.core` mechanism. It owns lifecycle state, registration catalogs, revision identity, freeze validation, compiled-plan ownership, and resource lifecycle contracts. It does not own TCP listeners, HTTP parsing, or business policy.

The public composition root may delegate to Server capabilities through a documented facade. The internal Kernel must not import `lingshu.server`.

### 2. Application lifecycle

The application lifecycle is:

```text
CREATED → CONFIGURING → FROZEN → STARTING → RUNNING
                                      ↓          ↓
                                   STOPPING ← DRAINING
                                      ↓
                                   STOPPED
```

Rules:

- construction creates no connection, task, listener, file, or process side effect;
- registration is allowed only in `CREATED` and `CONFIGURING`;
- the first accepted registration moves the application to `CONFIGURING`;
- `freeze` validates and compiles one immutable Application Plan;
- `freeze` is idempotent for an unchanged revision;
- failed freeze publishes no partial plan and leaves the previous valid plan unchanged;
- startup operates only on a frozen plan;
- running registries are immutable;
- drain stops new admission before shutdown cleanup;
- shutdown is idempotent and follows ADR-002;
- fatal failure is recorded as an outcome and still enters bounded cleanup rather than skipping directly to process exit.

### 3. Application revision and freeze boundary

Configuration, routes, middleware, exception mappers, extensions, and lifecycle hooks belong to an Application Revision.

Freeze performs at least:

1. configuration validation;
2. extension dependency resolution;
3. route conflict and ambiguity validation;
4. middleware ordering and phase validation;
5. exception-mapper validation;
6. public handler signature validation;
7. resource-budget validation;
8. compilation of immutable route, middleware, exception, extension, and lifecycle plans;
9. generation of a revision identifier and diagnostics;
10. atomic publication of the complete plan.

After freeze, direct mutation is rejected with a configuration-state error.

Future hot reload must create and validate a new revision and atomically switch plans. In-place mutation of a running plan is prohibited. Full reload semantics are deferred.

### 4. Route model

A route declaration contains at least:

- normalized path template;
- explicit HTTP method set;
- handler;
- optional route name;
- route-local middleware;
- route metadata and capability requirements;
- explicit body and response policy references when later approved.

Rules:

- route registration order is not a hidden conflict-resolution policy;
- duplicate and ambiguous routes fail during freeze;
- static routes are more specific than dynamic segments through explicit matcher rules, not registration order;
- method-not-allowed and not-found results are distinct;
- automatic `HEAD` or `OPTIONS` behavior is deferred unless separately approved;
- the running Router is immutable and safe for concurrent reads;
- reverse routing and mount/sub-application semantics are deferred.

### 5. Handler contract

The initial handler contract is asynchronous:

```python
async def handler(request: Request) -> Response | SupportedReturnValue:
    ...
```

Rules:

- the initial Kernel does not execute synchronous handlers directly on the event loop;
- automatic sync-handler executor adaptation is deferred;
- the request is the explicit handler input;
- route parameters are exposed through the Request instead of implicit function-argument injection;
- dependency injection is not a Core Kernel responsibility;
- handler signatures are validated during freeze;
- unsupported signatures fail before startup.

### 6. Middleware model

LingShu uses deterministic onion-style middleware with two HTTP scopes:

- application middleware wraps route matching, route middleware, handler execution, and return normalization;
- route middleware runs only after a route match and wraps the selected handler plus normalization.

Middleware contract:

```python
async def middleware(request: Request, call_next: Next) -> Response:
    ...
```

Ordering rules:

- lower numeric priority executes earlier on ingress and later on egress;
- equal priority uses explicit registration sequence within the same Application Revision;
- import order is not middleware order;
- application middleware ingress runs outer to inner;
- route middleware ingress runs outer to inner after route matching;
- egress unwinds in exact reverse order;
- middleware may short-circuit by returning a Response without calling `call_next`;
- calling `call_next` more than once is prohibited;
- retaining or invoking `call_next` after the middleware Scope completes is prohibited;
- middleware failures follow the same exception path as handler failures.

Connection/protocol hooks, lifecycle hooks, and Runtime Record sinks are not disguised as HTTP middleware; they use their own contracts.

### 7. Request pipeline

The canonical request pipeline is:

```text
1. protocol request accepted by Server
2. create Request Scope and absolute Deadline
3. assign Request/Connection/Trace identities and open Runtime Record
4. create immutable request metadata and bounded body stream
5. perform Worker/Application admission
6. enter application middleware
7. route match
8. perform route admission and capability checks
9. enter route middleware
10. invoke asynchronous handler
11. normalize handler return to Response
12. unwind route middleware
13. unwind application middleware
14. resolve an unhandled exception when needed
15. finalize response metadata and body policy
16. commit response head
17. stream/write response with backpressure
18. finalize Runtime Record
19. cancel/await remaining request-owned tasks
20. release body, admission, context, and other request resources
```

Every stage is observable and records start, outcome, failure, cancellation, and cleanup as applicable.

A stage may not silently bypass Deadline, cancellation, admission, or cleanup rules.

### 8. Request semantics

A Request is owned by one Request Scope and is invalid after that Scope completes.

Read-only request metadata includes method, target, scheme, authority/host, path, query representation, protocol version, headers, client/server connection metadata, and assigned identities.

Rules:

- metadata is immutable to application code;
- route match adds read-only route identity and path parameters;
- request-local mutable application data uses an explicit scoped state container;
- extensions use namespaced state keys or typed capability access to avoid collisions;
- the request body is a bounded, backpressured, single-consumer stream;
- convenience buffering or decoding is explicit, cached only within configured limits, and owned by the Request Scope;
- body consumption after completion or cancellation fails explicitly;
- application code must not retain the Request object beyond Scope completion;
- sensitive header and body data is redacted from records by default.

The exact query, cookie, form, multipart, and structured-body APIs are deferred to serialization and HTTP-detail decisions.

### 9. Handler return normalization

Every handler result passes through one explicit Response Normalizer before middleware egress completes.

Initial supported result categories are:

- an existing `Response`;
- `str`, normalized as a text response under explicit default encoding rules;
- bytes-like data, normalized as a binary response;
- structured values only after the serialization decision approves their serializer and media type.

Rules:

- `None` is not an implicit empty success response;
- tuple magic such as `(body, status, headers)` is rejected;
- arbitrary iterables are not silently treated as streaming bodies;
- unsupported values raise a clear return-type framework error;
- middleware must return a Response, not an unnormalized handler value;
- normalization occurs exactly once.

### 10. Response states and commit point

Response state is:

```text
NEW → PREPARED → COMMITTED → COMPLETED
                  ↘          ↘
                   ABORTED ← ABORTED
```

Rules:

- status, headers, cookies, and body policy may be changed only before `COMMITTED`;
- `PREPARED` means normalization and framework finalization have completed but bytes are not irreversible;
- `COMMITTED` begins when the finalized response head is accepted by the Transport for transmission;
- after commit, status and headers are immutable;
- only one response may be committed per request;
- a pre-commit exception may replace the pending response through exception mapping;
- a post-commit exception cannot create a second HTTP response; the stream/connection is aborted according to protocol policy and the failure is recorded;
- streaming producers are request-owned unless explicitly transferred through a bounded streaming contract;
- response completion requires body completion or an explicitly recorded abort;
- double commit, write-after-completion, and mutation-after-commit are framework errors.

### 11. Exception resolution

Exception mapping is deterministic.

Resolution order:

1. route-scoped mapper for the most specific exception type;
2. application-scoped mapper for the most specific exception type;
3. built-in mapping for intentional `HTTPException` values;
4. safe default internal-error response before commit.

Rules:

- most specific exception class wins; equal ambiguity fails during freeze;
- middleware may catch and convert exceptions before framework fallback mapping;
- mapper output must be a Response and is not passed through handler-return normalization;
- mapper failure records both the original exception and mapper exception, then uses the safe default response when still pre-commit;
- sensitive exception details are not exposed by default;
- cancellation is not converted into an ordinary error response unless an explicit protocol-safe rule applies;
- after response commit, exception mapping cannot replace the response;
- fatal process errors are not broadly converted into HTTP success/failure responses.

The full exception taxonomy and error payload schema remain a later hardening decision.

### 12. Extension participation

Extensions may contribute through explicit contracts during `CONFIGURING`:

- configuration schema and validation;
- capabilities;
- routes;
- application or route middleware;
- exception mappers;
- lifecycle hooks;
- Runtime Record/telemetry sinks through approved protocols.

Freeze resolves extension dependencies and compiles all contributions into the immutable plan.

During startup and shutdown, extension resources follow dependency order on startup and reverse order on cleanup.

Extensions may not mutate route, middleware, or exception registries while the plan is running. Per-request extension work uses compiled hooks, capabilities, and scoped context.

### 13. Minimum public API

The root facade initially exposes only:

```python
from lingshu import LingShu, Request, Response, HTTPException
```

Minimum usage shape:

```python
from lingshu import LingShu, Request, Response

app = LingShu()

@app.get("/")
async def index(request: Request) -> Response:
    return Response.text("hello")
```

Confirmed public concepts:

- `LingShu`: composition root and registration facade;
- `Request`: scoped immutable request interface with bounded body access;
- `Response`: response construction and explicit factory interface;
- `HTTPException`: intentional HTTP failure signal handled by the exception pipeline;
- route decorators including `route` and common method conveniences;
- explicit application and route middleware registration;
- explicit exception-mapper registration;
- explicit extension registration.

Not confirmed by this ADR:

- exact constructor parameters;
- `run`/`serve` method names and CLI command details;
- lifecycle-hook decorator names;
- automatic dependency injection;
- sync handler adaptation;
- automatic JSON/form/multipart APIs;
- OpenAPI behavior.

Root exports use explicit `__all__`. Internal Kernel, plan, matcher, middleware compiler, normalizer, commit controller, and transport types remain private unless separately promoted.

### 14. Contract and state-machine tests

Implementation acceptance must include tests for:

- legal and illegal Application state transitions;
- idempotent freeze and no partial plan publication after failed freeze;
- mutation rejection after freeze;
- route conflict and ambiguity detection independent of registration order;
- deterministic middleware ingress/egress order and priority ties;
- short-circuit middleware and double-`call_next` rejection;
- request metadata immutability and scoped-state isolation;
- single-consumer body behavior and bounded caching;
- handler signature validation and unsupported return types;
- one-time normalization;
- pre-commit exception replacement;
- mutation-after-commit, double-commit, and write-after-completion rejection;
- post-commit streaming failure abort behavior;
- exception mapper specificity and mapper-failure fallback;
- cancellation not being swallowed or converted incorrectly;
- extension contribution freeze and reverse cleanup;
- no request, body, state, task, or response object leakage after Scope completion;
- root public-export manifest and import-side-effect checks.

## Rejected alternatives

- route and middleware mutation while RUNNING;
- import-time route or extension registration;
- registration order as hidden route conflict resolution;
- unordered middleware execution;
- calling `call_next` multiple times;
- implicit sync-handler execution on the event loop;
- implicit tuple response magic;
- implicit `None` success responses;
- mutable request metadata;
- multiple response commits;
- replacing an HTTP response after it is committed;
- exposing all deep implementation modules as public API;
- allowing extensions to mutate the compiled plan per request.

## Intentionally deferred

- complete configuration reload and atomic multi-Worker rollout;
- full exception taxonomy and error body schema;
- identifier formats;
- structured serialization and content negotiation details;
- cookies, form, multipart, and upload APIs;
- reverse routing, sub-applications, and route mounts;
- automatic `HEAD` and `OPTIONS` policy;
- public `run`/`serve` API and CLI semantics;
- synchronous handler adaptation;
- dependency injection;
- OpenAPI and official extension implementations;
- exact numeric limits and timeouts.
