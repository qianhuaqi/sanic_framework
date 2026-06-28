# LingShu Development Constitution

- Status: Active for P0 governance
- Version: 2.1-draft
- Effective baseline: latest accepted `main`
- Applies to: all work in the greenfield LingShu repository

## 1. Project identity

LingShu is a greenfield, independently implemented Python Web/API framework.

LingShu is not a wrapper around, migration from, adapter for, or compatibility layer for Sanic, FastAPI, Flask, Django, Starlette, or any other upper-level Web framework.

The archived repository state creates no compatibility obligation for the new framework. The legacy implementation is preserved only as non-authoritative reference material in `archive/legacy-sanic-20260628`.

Any task or implementation that assumes continuation of the legacy runtime must stop and be reported as a scope conflict.

The canonical repository is `qianhuaqi/lingshu`. A separate repository for a framework component or official capability requires a future accepted ADR.

## 2. Roles and authority

### 2.1 Project lead

The project lead:

- decides product scope, priorities, and unresolved architecture choices;
- confirms or rejects Blueprint decisions;
- approves deviations from this constitution;
- holds final merge authority;
- may stop any phase when evidence is incomplete or risk is unacceptable.

### 2.2 Architect and reviewer

The architect:

- prepares architecture proposals, Issues, acceptance criteria, and ADRs;
- maintains governance and phase documents;
- reviews implementation independently from its author;
- records acceptance findings;
- coordinates concurrent task boundaries and integration order;
- does not silently change confirmed product decisions.

### 2.3 Developer

A developer may be a human or an AI tool. A developer:

- executes only the active Issue and branch scope;
- must read the current Issue, this constitution, `AGENTS.md`, `CURRENT_PHASE.md`, applicable concurrency rules, accepted ADRs, and applicable architecture decisions before writing;
- must not expand scope, redefine acceptance criteria, or begin the next phase;
- must not write outside the declared write scope;
- must not self-declare final acceptance;
- must stop when fact sources or task ownership conflict.

### 2.4 Separation of duties

Implementation and acceptance must be separated. The implementation author provides evidence; an independent reviewer evaluates it; the project lead performs the final merge.

## 3. Sources of truth and conflict order

The repository, not chat memory, is the permanent source of truth.

When facts conflict, use this order:

1. explicit project-lead decision recorded in an accepted ADR or constitution amendment;
2. this constitution;
3. accepted ADRs and the P0 decision-status register;
4. the active GitHub Issue and its acceptance criteria;
5. `docs/development/CURRENT_PHASE.md`;
6. `docs/development/CONCURRENT_DEVELOPMENT.md` for concurrent task operations;
7. the active remote branch and Pull Request;
8. `docs/development/HANDOFF.md`;
9. confirmed sections of the Blueprint;
10. other documentation and examples.

Chat history, model memory, archived branches, closed legacy Issues, and old Pull Requests are not active implementation authority.

If two active fact sources conflict, development stops until the conflict is resolved in GitHub.

## 4. Greenfield policy

Before v1.0:

- legacy APIs have no automatic compatibility guarantee;
- obsolete or experimental designs may be replaced directly;
- no permanent compatibility package is created without a real released consumer and an accepted ADR;
- legacy source, tests, scaffolds, configuration, and dependency files are not implementation baselines;
- useful ideas from the archive must be re-evaluated against the current Blueprint and reimplemented under a new Issue;
- no Sanic adapter, migration layer, or old-import forwarding layer may be introduced.

After v1.0, compatibility policy must be defined by semantic versioning and a dedicated public API policy before release.

## 5. Phase lifecycle

Every implementation or architecture subphase follows this lifecycle:

1. create or select one active Issue;
2. define scope, exclusions, deliverables, acceptance evidence, prohibited actions, base commit, write scope, dependencies, conflicts, integration order, and required checks;
3. create one dedicated branch from the approved baseline;
4. assign one primary writer;
5. create an independent worktree or clone and virtual environment when work is concurrent;
6. perform only the approved work;
7. run required checks and record evidence;
8. update `HANDOFF.md` before handing work to another writer;
9. open one Pull Request;
10. perform independent review;
11. resolve all blocking findings;
12. synchronize dependent work with current `main` after relevant upstream merges;
13. obtain project-lead merge approval;
14. merge;
15. synchronize `CURRENT_PHASE.md`, ADR status, and handoff state;
16. only then open the next dependent phase.

No phase may be skipped or started early. Parallel work requires explicit Issue approval, non-overlapping write scopes, and a recorded integration order.

## 6. Branch, worktree, and Pull Request rules

- Never commit directly to `main`.
- Never force-push or rewrite shared history.
- Never enable automatic merge.
- A branch has one primary writer at a time.
- Concurrent developers must not share one writable worktree or clone.
- Each concurrent worktree has its own branch, virtual environment, local environment file, runtime directory, caches, temporary paths, and local ports.
- Branch names identify the writer and phase, for example `qwen/phase-p1-...`, `glm/phase-p1-...`, `gemini/phase-p1-...`, `codex/phase-p1-...`, or `human/<name>/phase-p1-...`.
- Research-only branches may use `research/<slug>` when the Issue explicitly declares non-implementation research.
- A developer change requires a committed handoff and, unless the Issue says otherwise, a new writer-prefixed branch.
- Pull Requests must link the active Issue and list base commit, primary writer, declared write scope, actual changed paths, dependencies, integration order, tests, known risks, and remaining work.
- A Pull Request with unresolved blocking review findings must not be merged.
- Development may be parallel; integration into `main` is serial.
- After a relevant upstream merge, dependent or potentially conflicting Pull Requests must synchronize with current `main` and rerun required checks.

Accidental direct commits must be disclosed. They must be corrected without history rewriting unless the project lead explicitly approves a safe recovery procedure.

## 7. Concurrent task ownership

Every active task is classified as one of:

- independent;
- ordered dependency;
- conflicting;
- cross-cutting exclusive.

Independent tasks may run in parallel only when write scopes do not overlap and neither changes a contract consumed by the other.

Ordered tasks may be researched in parallel, but the provider contract merges before the consumer. The consumer then synchronizes and reruns checks.

Conflicting tasks do not run in parallel. Cross-cutting exclusive changes to architecture, public exports, root packaging, repository-wide CI, shared exceptions, lifecycle contracts, security policy, or release metadata allow only one writer Issue at a time.

Two Issues with overlapping write scopes are conflicting by default. An exception requires explicit project-lead approval recorded in both Issues.

Multiple tasks must not implement duplicate versions of the same public contract. Shared contracts are created by a foundation Issue and merged first.

Cross-branch cherry-picking of active implementation commits is prohibited unless the active Issue records the reason and integration owner. The normal path is foundation merge followed by synchronization from `main`.

Operational details are defined in ADR-001 and `docs/development/CONCURRENT_DEVELOPMENT.md`.

## 8. Issue contract

Every active Issue must define:

- objective and user value;
- exact in-scope work;
- explicit out-of-scope work;
- target branch and primary writer;
- approved base commit;
- write scope using paths or globs;
- read dependencies;
- dependent Issues or Pull Requests;
- conflicting active tasks;
- integration order;
- deliverables;
- acceptance criteria;
- required tests and evidence;
- security, compatibility, and migration impact;
- prohibited actions;
- prerequisite merge or commit.

A missing ownership or dependency declaration means the Issue is not ready for concurrent implementation.

Vague instructions such as “optimize the framework” are not sufficient implementation authority.

## 9. Architecture decision policy

Architecture decisions that affect repository structure, package structure, dependency direction, runtime semantics, concurrency, public API, persistence format, protocol behavior, security, compatibility, or release policy require:

1. a GitHub Issue;
2. an ADR or explicit Blueprint amendment;
3. project-lead confirmation;
4. a reviewed Pull Request.

Candidate text is not executable architecture. Any Blueprint section marked candidate, unresolved, pending confirmation, or not frozen must not be used to create source directories or public APIs.

Core mechanisms and optional policies must remain separate. Dependency direction must be explicit, cycle-free, and machine-testable once implementation begins.

## 10. Quality and test gates

Each implementation Issue defines its own exact checks. At minimum, applicable work must cover:

- unit tests for local behavior;
- contract tests for public or extension-facing behavior;
- integration tests for cross-component behavior;
- protocol and malformed-input tests for network parsers;
- security tests for trust boundaries and sensitive data;
- concurrency, race, deadlock, cancellation, timeout, cleanup, overload, and resource-leak tests where applicable;
- packaging and clean-install tests before a package is published;
- supported Python and platform checks before a compatibility claim is made;
- documentation and examples that match the implementation.

Tests must prove behavior, not merely object construction or field presence. Skipped, flaky, or unavailable tests must be disclosed and cannot be represented as passing.

## 11. Code and documentation standards

- Public identifiers, source comments, public Docstrings, and error keys use English unless an accepted ADR changes the rule.
- Architecture and user-facing guides may be written in Chinese.
- Public APIs require type annotations and useful Docstrings.
- Complex lifecycle, concurrency, cancellation, security, and resource-ownership behavior requires design comments.
- TODO and FIXME entries require an Issue reference and removal condition.
- Generated files must identify their generator and must not be edited manually.
- Documentation, tests, and implementation must change together when behavior changes.

## 12. Dependency policy

- No upper-level Web framework may be introduced.
- Core third-party dependencies require a dedicated ADR explaining necessity, alternatives, security, maintenance, licensing, and fallback behavior.
- Optional integrations must not become hidden mandatory dependencies.
- Dependency versions and supported Python versions must be explicit before package publication.
- A dependency may not be added merely because a developer is familiar with it.
- Cryptography and TLS primitives must use established, reviewed libraries rather than custom algorithms.

## 13. Security and sensitive information

- Never commit API keys, tokens, passwords, private keys, production endpoints, personal data, or real credentials.
- Examples use placeholders and safe local defaults.
- Logs, telemetry, runtime records, exceptions, test fixtures, and review comments must redact secrets and sensitive request data.
- Security-relevant defaults must fail closed where ambiguity would create exposure.
- Security exceptions require an Issue, risk explanation, owner, expiration or removal condition, and project-lead approval.
- Public vulnerability reporting and supported-version policy must be documented before public release.

## 14. Runtime invariants

Applicable runtime designs must preserve these invariants:

- app, worker, request, operation, and extension state are isolated according to scope;
- queues, buffers, bodies, connections, tasks, retries, timeouts, logs, and disk use are bounded;
- concurrency has explicit admission control, ownership, and backpressure;
- blocking work cannot silently block the event loop;
- startup failure rolls back acquired resources;
- shutdown is ordered, bounded, drains or cancels tasks, and is observable;
- cancellation and deadlines propagate and are not silently swallowed;
- cleanup is deterministic and idempotent where required;
- no process-wide mutable request state;
- sensitive data is not recorded by default;
- protocol ambiguity is rejected rather than guessed.

The concrete runtime concurrency model requires a separate P0 decision.

## 15. Handoff and device switching

Before switching computers, developers, or models:

1. stop writing;
2. run the required checks;
3. confirm the worktree is clean;
4. update `HANDOFF.md` with branch, commit, completed work, test evidence, risks, and next action;
5. commit and push;
6. verify the remote branch contains the handoff commit.

The receiving developer must read the handoff and active Issue before continuing. It must not continue from another writer's uncommitted files, stash, virtual environment, or runtime cache.

## 16. Deviations and emergency changes

A deviation from this constitution requires:

- a written reason;
- affected rules and risks;
- scope and expiration;
- project-lead approval;
- an ADR or constitution amendment when the deviation has lasting effect.

Emergency fixes must still be documented after the immediate risk is contained. “The tool suggested it” or “the old code did it” is not an acceptable justification.

## 17. Current P0 restriction

P0 is architecture and governance consolidation only.

Until the project lead confirms the complete Blueprint and a P1 Issue is created:

- do not create production source packages;
- do not create package skeletons that imply an unconfirmed directory decision;
- do not publish packages;
- do not introduce runtime dependencies;
- do not implement the HTTP runtime, native server, router, middleware, extension runtime, or official extensions;
- do not implement an unresolved event-loop, worker, process, thread, or Task Group model;
- do not treat candidate distribution, `src/`, directory, runtime-concurrency, or release layouts as frozen.
