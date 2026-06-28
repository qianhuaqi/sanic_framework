# ADR-001: Single repository and concurrent development model

- Status: Accepted
- Date: 2026-06-28
- Parent architecture Issue: #25
- Decision Issue: #31 (completed)
- Implemented by: PR #32
- Effective merge commit: `92d6c0795fd5a6d21841a8ac3a1896d703809e40`

## Context

LingShu will be developed by human contributors and multiple AI developers such as Qwen, GLM, Gemini, and Codex. Splitting early framework work across multiple repositories would fragment architecture, tests, documentation, version history, and review authority. However, placing everything in one repository creates a different risk: multiple developers may overwrite each other, modify the same contract in parallel, or merge incompatible assumptions.

The project lead has confirmed that LingShu uses a single repository and requires concurrency to be handled explicitly.

## Decision

### 1. One canonical repository

The canonical repository is:

`qianhuaqi/lingshu`

Framework core, official capabilities, tests, documentation, examples, build tooling, protocol tests, security tests, and release metadata are governed in this repository unless a future accepted ADR proves that a separate repository is necessary.

This decision confirms one repository. It does not yet decide whether the repository publishes one Python distribution or multiple distributions, and it does not decide whether a `src/` layout is used.

### 2. Development concurrency is isolated

Parallel developers must never share the same writable working directory.

Every concurrent task requires:

- one GitHub Issue;
- one writer-prefixed branch;
- one primary writer;
- one independent Git worktree or separate clone;
- one independent virtual environment;
- one declared write scope;
- one Pull Request.

A branch may have only one primary writer at a time. A model handoff requires a committed handoff and a new writer branch unless the Issue explicitly authorizes continuation.

### 3. Task concurrency classes

Every Issue must be classified before implementation.

#### Independent

Write scopes do not overlap and neither task changes a contract consumed by the other. Tasks may run in parallel.

#### Ordered dependency

One task defines a contract, schema, public API, package boundary, or shared fixture consumed by another task. The provider task merges first. The dependent task must synchronize with the resulting `main` and rerun all required checks before review.

#### Conflicting

Tasks modify overlapping write scopes or competing versions of the same behavior. They must not run in parallel. The project lead chooses an order or combines them into one Issue.

#### Cross-cutting exclusive

Changes to architecture contracts, public API exports, root packaging configuration, shared CI policy, repository-wide test fixtures, security policy, or release metadata acquire an exclusive integration slot. No parallel task may modify the same cross-cutting files.

### 4. Write-scope contract

Every implementation Issue must declare:

- `primary_writer`;
- `base_commit`;
- `write_scope` using explicit paths or globs;
- `read_dependencies`;
- `depends_on` Issues or Pull Requests;
- `conflicts_with` active tasks, if any;
- `integration_order`;
- `required_checks`.

Two active Issues with overlapping `write_scope` are conflicting by default. Parallel execution requires an explicit project-lead exception.

### 5. Serial integration into main

Development may be parallel, but integration into `main` is serial.

- `main` is never a shared development branch.
- No developer commits directly to `main`.
- Automatic merge is disabled.
- Each Pull Request is reviewed independently.
- The project lead performs the final merge.
- After another Pull Request merges, every still-open dependent or potentially conflicting Pull Request must synchronize with current `main` and rerun required checks.
- Merge conflicts are resolved by the primary writer in the task branch, never by editing `main` directly.
- Shared foundation changes merge before feature changes that depend on them.

### 6. Worktree and environment isolation

On one computer, concurrent developers use separate directories, for example:

```text
D:\webapps\lingshu                 main inspection and project-lead workspace
D:\webapps\lingshu-qwen           Qwen task worktree
D:\webapps\lingshu-glm            GLM task worktree
D:\webapps\lingshu-gemini         Gemini task worktree
```

Each worktree has its own:

- branch;
- `.venv`;
- local environment file;
- runtime directory;
- test cache;
- assigned local ports and temporary paths.

No developer may run `git stash pop` from another task into its worktree or copy an unreviewed source tree between worktrees.

### 7. Shared-contract rule

A public contract is implemented once.

When multiple tasks need the same new contract, the contract is created in a small foundation Issue and merged first. Dependent tasks consume the merged contract. Developers must not independently create duplicate interfaces and reconcile them later.

Cross-branch cherry-picking of active implementation commits is prohibited unless the active Issue explicitly records the reason and integration owner. The preferred flow is foundation merge followed by synchronization from `main`.

### 8. Collision detection and review

Before starting a task, the developer checks active Issues and Pull Requests for overlapping paths and contract changes.

Until automated enforcement exists, the architect or reviewer validates declared write scopes manually. P1 quality tooling must add machine checks for:

- undeclared changed paths;
- overlapping active write scopes;
- forbidden branch names;
- direct changes to protected cross-cutting files without Issue authorization;
- stale base commits on dependent Pull Requests.

### 9. Runtime concurrency is a separate architecture decision

This ADR governs development concurrency. It does not choose the framework runtime concurrency implementation.

LingShu runtime concurrency must later define and test:

- event-loop and task model;
- structured task ownership;
- worker and process model;
- blocking-work isolation;
- request and context isolation;
- bounded concurrency and backpressure;
- cancellation and deadline propagation;
- graceful shutdown and task draining;
- race, deadlock, leak, and overload behavior.

Regardless of the later implementation choice, runtime concurrency must be bounded, isolated, cancellable, observable, and deterministically cleaned up.

## Consequences

### Benefits

- one architecture and version history;
- one review and governance system;
- parallel development without shared-worktree corruption;
- clear merge order for dependent tasks;
- lower risk of duplicate contracts and incompatible implementations;
- easier repository-wide testing and release preparation.

### Costs

- Issues require explicit path ownership and dependency metadata;
- parallel work is limited when contracts or shared files overlap;
- dependent branches must resynchronize after upstream merges;
- automated collision checks must be built during P1 governance tooling.

## Rejected alternatives

- separate repositories for Core, HTTP, Server, Record, or official extensions at the beginning of development;
- multiple developers writing in the same working directory;
- multiple primary writers on one branch;
- parallel branches editing the same public contract;
- long-lived shared `develop` branch;
- automatic merge of concurrent Pull Requests;
- resolving conflicts by force-pushing or rewriting shared history.
