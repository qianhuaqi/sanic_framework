# LingShu Application Kernel and Request Pipeline

- Status: Proposed for P0-D4
- Decision Issue: #40
- Parent Issue: #25
- Related ADR: `docs/decisions/ADR-004-application-kernel-request-pipeline-and-public-api.md`

## 1. Purpose

This document turns P0-D4 into an implementation-ready contract without creating production code.

It defines:

- the public composition root and internal Application Kernel;
- Application Revision and freeze semantics;
- Route, Middleware, Handler, Request, Response, and Exception contracts;
- the exact request execution sequence;
- extension participation;
- minimum public exports;
- contract and state-machine acceptance tests.

## 2. Composition model

```text
Public LingShu facade
├─ internal Application Kernel
├─ immutable Application Plan
├─ HTTP application plan
├─ Runtime ownership plan
├─ Runtime Record protocols
├─ Extension plan
└─ Server delegation surface
```

The root facade is the only layer allowed to assemble higher and lower components. Lower components must not import the root facade.

The internal Kernel owns state and compiled plans, not network listeners or protocol parsing.

## 3. Application states

```text
CREATED
  ↓
CONFIGURING
  ↓
FROZEN
  ↓
STARTING
  ↓
RUNNING
  ↓
DRAINING
  ↓
STOPPING
  ↓
STOPPED
```

Permitted transitions are explicit. Illegal transitions fail with a state error and produce no partial mutation.

### State permissions

| State | Register config/routes/middleware/extensions | Freeze | Start | Accept requests | Stop |
|---|---:|---:|---:|---:|---:|
| CREATED | yes | yes | no | no | yes |
| CONFIGURING | yes | yes | no | no | yes |
| FROZEN | no | idempotent | yes | no | yes |
| STARTING | no | no | no | no | yes |
| RUNNING | no | no | no | yes | yes |
| DRAINING | no | no | no | existing only | yes |
| STOPPING | no | no | no | no | idempotent |
| STOPPED | no | no | no | no | idempotent |

Construction and import must have no runtime side effects.

## 4. Application Revision

Every accepted configuration mutation belongs to a revision draft.

A revision includes:

- configuration values and schemas;
- route declarations;
- application middleware;
- route middleware;
- exception mappers;
- extension declarations and dependencies;
- lifecycle hooks;
- capability declarations;
- runtime budget references;
- metadata required for diagnostics.

Freeze compiles a complete immutable `Application Plan` conceptually containing:

```text
revision_id
validated_config
route_matcher
route_execution_plans
application_middleware_chain
exception_mapper_table
extension_lifecycle_plan
capability_plan
runtime_budget_plan
public_diagnostics
```

No plan is published until all validation and compilation succeeds.

## 5. Freeze validation

Freeze rejects at least:

- duplicate route identity;
- ambiguous path templates;
- overlapping method declarations without an explicit rule;
- invalid handler signatures;
- invalid middleware signatures;
- ambiguous exception mappings;
- missing extension dependencies;
- extension dependency cycles;
- duplicate capability providers without an explicit selection rule;
- invalid lifecycle ordering;
- missing required resource budgets;
- any mutation attempt against an already frozen revision.

Freeze output is immutable and safe for concurrent reads.

## 6. Route declaration contract

A Route Declaration conceptually contains:

```text
path_template
methods
handler
name?
route_middleware[]
metadata
required_capabilities[]
body_policy?
response_policy?
```

Initial routing rules:

- methods are explicit and normalized;
- static segments outrank dynamic segments by matcher rules;
- registration order is never used to hide ambiguity;
- duplicate names and conflicting declarations fail at freeze;
- 404 and 405 remain distinct;
- path parameters become read-only Request data after match;
- the compiled matcher is immutable.

Sub-app mounting, reverse routing, host routing, version routing, automatic `HEAD`, and automatic `OPTIONS` remain deferred.

## 7. Handler contract

Initial public handler shape:

```python
async def handler(request: Request) -> Response | SupportedReturnValue:
    ...
```

Rules:

- one explicit Request argument;
- asynchronous callable required initially;
- no automatic positional injection of path parameters;
- no Core dependency-injection container;
- signature validated at freeze;
- handler executes in the Request Scope;
- child tasks are request-owned unless explicitly transferred through an approved runtime API;
- sync callable adaptation is deferred.

## 8. Middleware scopes

### 8.1 Application middleware

Wraps:

```text
route matching
route admission
route middleware
handler
return normalization
```

Application middleware can:

- inspect request metadata before routing;
- add scoped state;
- short-circuit with a Response;
- catch and convert exceptions;
- modify an uncommitted Response during egress.

### 8.2 Route middleware

Runs only after a successful route match and wraps:

```text
handler
return normalization
```

Route middleware can access route identity and path parameters.

### 8.3 Ordering

For each scope:

```text
priority ascending → registration sequence ascending
```

Ingress follows this order. Egress is exact reverse order.

Example:

```text
app A ingress
  app B ingress
    route X ingress
      route Y ingress
        handler + normalization
      route Y egress
    route X egress
  app B egress
app A egress
```

`call_next` is single-use and Scope-bound.

## 9. Canonical request pipeline

### Stage 1: protocol acceptance

Server validates framing sufficiently to create an application request. Protocol rejection before this point is a Server/Protocol result, not an application exception.

### Stage 2: Request Scope

Runtime creates the Request Scope, absolute Deadline, cancellation linkage, and resource ownership.

### Stage 3: identity and record

The framework assigns required identities and opens the bounded Runtime Record.

### Stage 4: Request construction

Immutable request metadata and bounded body stream are attached to the Scope.

### Stage 5: application admission

Worker/Application concurrency limits admit, queue within bounds, reject, or cancel the request.

### Stage 6: application middleware ingress

Application middleware begins in deterministic order.

### Stage 7: route match

The immutable matcher returns a selected route, 404, or 405 outcome.

### Stage 8: route admission and capabilities

Route-level capacity and required capabilities are resolved before handler execution.

### Stage 9: route middleware ingress

Selected route middleware begins in deterministic order.

### Stage 10: handler

The asynchronous handler runs under the Request Scope and inherited Deadline.

### Stage 11: normalization

The handler result becomes exactly one Response.

### Stage 12: route middleware egress

Route middleware unwinds in reverse order.

### Stage 13: application middleware egress

Application middleware unwinds in reverse order.

### Stage 14: exception fallback

Any unhandled pre-commit exception is resolved by the exception mapper table.

### Stage 15: response preparation

Status, headers, cookies, media type, length/framing policy, and body producer are finalized.

### Stage 16: commit

The finalized response head is accepted by the Transport. Status and headers become immutable.

### Stage 17: body transmission

Body or stream is written under backpressure and Deadline rules.

### Stage 18: response outcome

Response becomes COMPLETED or ABORTED.

### Stage 19: record finalization

Outcome, errors, cancellations, bytes, timing, and cleanup begin final record completion.

### Stage 20: Scope cleanup

Remaining request tasks are cancelled/awaited, admission tokens and buffers are released, context is cleared, and the Runtime Record is flushed according to bounded policy.

## 10. Request contract

Conceptual Request data:

```text
method
target
scheme
authority
path
query
protocol_version
headers
client
server
connection_id
request_id
trace_id
route
path_params
state
body
scope/deadline access through approved surface
```

Rules:

- protocol and metadata fields are read-only;
- headers are exposed through a read-only multi-value interface;
- route and path parameters appear only after route match;
- `state` is request-scoped mutable data and is cleared at completion;
- extension state must be namespaced or typed;
- body stream is single-consumer and bounded;
- buffering is explicit and fails when configured limits are exceeded;
- cached decoded data is Scope-owned and bounded;
- access after Scope completion fails;
- Request objects are not serializable long-lived business objects.

## 11. Response contract

Conceptual Response construction supports:

```text
status
headers
cookies
body or stream
media_type
encoding policy
trailers only after later protocol approval
```

State machine:

```text
NEW → PREPARED → COMMITTED → COMPLETED
  ↘       ↘           ↘
   ABORTED ←────────── ABORTED
```

Rules:

- NEW is application/middleware construction state;
- PREPARED is framework-finalized but replaceable before commit;
- COMMITTED makes status and headers irreversible;
- COMPLETED means body output completed successfully;
- ABORTED records incomplete output and cause;
- only one commit is allowed;
- body writes require committed state;
- writes after COMPLETED or ABORTED fail;
- streaming failure after commit aborts output and does not invoke a second response mapper;
- disconnect and cancellation remain distinct from application exceptions.

## 12. Return normalization

Normalizer input categories:

```text
Response
str
bytes-like
approved structured values in a future serialization decision
```

Rejected by default:

```text
None
tuple response magic
arbitrary iterator/generator
unknown object
multiple response values
```

Text uses an explicit default media type and encoding policy. Bytes use an explicit binary media type policy. Exact defaults are deferred to the HTTP/serialization decision.

Normalization happens once before middleware egress completes.

## 13. Exception mapping

Exception registry entries contain:

```text
scope: route or application
exception_type
mapper
priority only when a future explicit use case is accepted
```

Resolution:

1. route scope, most specific type;
2. application scope, most specific type;
3. built-in `HTTPException` mapping;
4. safe internal-error response when pre-commit.

Rules:

- duplicate equally specific mappers fail at freeze;
- mapper must be asynchronous unless later adaptation is approved;
- mapper returns Response directly;
- mapper errors are recorded with the original error;
- error details are hidden from clients by default;
- cancellation is re-raised after bounded cleanup unless an explicit transport-safe mapping exists;
- after commit, only abort/close and recording are permitted.

## 14. Extension integration

### Configuration time

Extensions may declare:

- dependencies;
- configuration schema;
- capabilities;
- routes;
- middleware;
- exception mappers;
- lifecycle hooks;
- record/telemetry protocol implementations.

### Freeze time

The Kernel resolves dependencies, validates all contributions, and compiles them into the immutable plan.

### Startup

Resources start in dependency order. Readiness is announced only after required extensions are ready.

### Request time

Extensions participate through compiled middleware, capabilities, mappers, and scoped state. They do not mutate global registries.

### Shutdown

Resources stop in reverse dependency/startup order within bounded budgets.

## 15. Minimum public facade

Root exports proposed by P0-D4:

```python
from lingshu import LingShu, Request, Response, HTTPException
```

Minimal usage:

```python
from lingshu import LingShu, Request, Response

app = LingShu()

@app.get("/")
async def index(request: Request) -> Response:
    return Response.text("hello")
```

Public concepts:

- `LingShu` composition/registration facade;
- `Request` scoped request interface;
- `Response` construction/factory interface;
- `HTTPException` intentional HTTP error signal;
- route and common method decorators;
- middleware registration;
- exception-mapper registration;
- extension registration.

Deferred public names:

- server run/serve methods;
- lifecycle hook decorators;
- configuration reload surface;
- Scope, Deadline, limiter, and cancellation types;
- serializers and upload types;
- dependency injection;
- sub-application/mount types.

## 16. Public/private boundary

Public:

- names explicitly exported in root `__all__`;
- later documented public subpackages;
- explicitly documented extension-author contracts;
- explicitly documented testing support.

Private:

- Kernel internals;
- Application Plan and compilers;
- route matcher nodes;
- middleware chain implementation;
- response commit controller;
- transport and parser internals;
- record storage internals;
- names beginning with `_`;
- any deep import not documented as public.

## 17. Required tests

### Kernel state

- every legal transition;
- every illegal transition;
- idempotent freeze and shutdown;
- failed freeze publishes no plan;
- running mutation rejection.

### Routing

- duplicate and ambiguous route failure;
- deterministic specificity;
- 404 versus 405;
- concurrent immutable matcher reads.

### Middleware

- application and route ordering;
- priority tie behavior;
- reverse egress;
- short-circuit;
- exception unwinding;
- double and delayed `call_next` rejection.

### Request

- metadata immutability;
- route-data availability timing;
- scoped state isolation;
- body single-consumer behavior;
- bounded buffering;
- access after completion failure.

### Response

- state transitions;
- exactly one commit;
- mutation-after-commit failure;
- pre-commit replacement;
- post-commit abort;
- streaming completion and cancellation.

### Exceptions

- mapper specificity;
- route versus application precedence;
- mapper failure fallback;
- sensitive-detail suppression;
- cancellation behavior before and after commit.

### Extensions

- dependency resolution;
- contribution compilation;
- startup order;
- reverse shutdown;
- no running registry mutation.

### Public facade

- exact `__all__` manifest;
- public import smoke test;
- no import-time I/O, tasks, processes, or global runtime mutation;
- private deep paths not accidentally documented as public.

## 18. Deferred decisions

- full configuration reload and multi-Worker plan rollout;
- complete exception taxonomy and client error schema;
- identifier formats;
- JSON and other serialization rules;
- cookies, form, multipart, and upload APIs;
- automatic `HEAD` and `OPTIONS`;
- host routing, mounting, reverse routing, and sub-applications;
- server `run`/`serve` and CLI API;
- synchronous handler adaptation;
- dependency injection;
- OpenAPI and official capability implementations;
- default media types, limits, and timeouts.

## 19. Acceptance rule

Merging the P0-D4 decision PR accepts the semantics in ADR-004 and this document. It still does not authorize production implementation. P1 remains blocked until the complete P0 Blueprint is frozen and explicitly authorized.
