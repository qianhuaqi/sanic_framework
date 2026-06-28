# Concurrent Development in the LingShu Repository

- Status: Active after ADR-001 merge
- Decision Issue: #31
- Applies to: human and AI developers

## 1. Purpose

LingShu uses one canonical repository while allowing several developers or AI models to work at the same time.

Concurrency is achieved through isolation and task ownership, not by sharing a branch or working directory.

## 2. Non-negotiable rules

1. One Issue, one branch, one primary writer, one Pull Request.
2. One writable worktree or clone per concurrent developer.
3. One virtual environment and runtime directory per worktree.
4. Every Issue declares its write scope and dependencies before coding.
5. Overlapping write scopes do not run concurrently unless the project lead explicitly approves the overlap.
6. Public contracts and shared foundations merge before dependent features.
7. Parallel development is allowed; integration into `main` is serial.
8. The project lead is the final merger.
9. Never auto-merge, force-push, rewrite shared history, or commit directly to `main`.

## 3. Task declaration template

Every implementation Issue must include a block equivalent to:

```yaml
primary_writer: qwen
base_commit: <full-main-sha>
write_scope:
  - lingshu/http/**
  - tests/unit/http/**
read_dependencies:
  - lingshu/core/**
depends_on:
  - issue: 40
conflicts_with: []
integration_order: after-40
required_checks:
  - unit-http
  - contract-http
  - typing
```

A missing task declaration means the task is not ready for implementation.

## 4. Concurrency classification

### A. Independent tasks

Parallel work is allowed when:

- write scopes do not overlap;
- neither task changes a public contract consumed by the other;
- shared root files are not modified;
- both tasks have independent acceptance tests.

Example:

```text
Qwen:    lingshu/http/request.py + tests/unit/http/
GLM:     docs/tutorials/ + examples/
Gemini:  lingshu/testing/client.py + tests/unit/testing/
```

This example is valid only after those directories and contracts have been approved by P0 and created by an implementation Issue.

### B. Ordered tasks

Parallel research may occur, but implementation merge is ordered when one task depends on another contract.

Example:

```text
Task A: define Request contract
Task B: implement Router using Request
```

Task A merges first. Task B then synchronizes with current `main`, resolves any changes, and reruns all required checks.

### C. Conflicting tasks

Parallel implementation is prohibited when two tasks:

- modify the same file or path;
- define the same interface or schema;
- change the same public import;
- alter the same lifecycle state machine;
- change root packaging or repository-wide configuration.

The project lead chooses the order or combines the work.

### D. Cross-cutting exclusive tasks

These files and areas are exclusive by default:

```text
pyproject.toml
AGENTS.md
docs/development/DEVELOPMENT_CONSTITUTION.md
docs/architecture/LINGSHU_FRAMEWORK_BLUEPRINT.md
docs/architecture/P0_DECISION_STATUS.md
public package exports
shared exception taxonomy
shared lifecycle state definitions
root CI and release configuration
```

Only one active Issue may write an exclusive area at a time.

## 5. Recommended Windows worktree setup

Keep the main project-lead directory clean:

```powershell
cd D:\webapps\lingshu
git fetch github --prune
git switch main
git pull --ff-only github main
```

Create separate worktrees:

```powershell
git worktree add D:\webapps\lingshu-qwen -b qwen/phase-p1-example github/main
git worktree add D:\webapps\lingshu-glm -b glm/phase-p1-example github/main
git worktree add D:\webapps\lingshu-gemini -b gemini/phase-p1-example github/main
```

Inside each worktree:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Each worktree must use separate local ports, `.env` files, caches, runtime directories, and temporary files.

## 6. Start-of-task checklist

Before writing:

```powershell
git fetch github --prune
git status
git branch --show-current
git rev-parse HEAD
git rev-parse github/main
```

Then verify:

- the current Issue is open;
- the branch name matches the primary writer;
- the worktree is clean;
- the branch starts from the approved base commit;
- the declared write scope does not overlap active Issues or PRs;
- dependencies are already merged or explicitly ordered;
- the correct virtual environment is active.

## 7. While working

- Commit only files inside the declared write scope.
- Do not edit another task's branch or worktree.
- Do not copy uncommitted source between worktrees.
- Do not use another task's stash.
- Do not create duplicate public contracts.
- Record newly discovered cross-task dependencies in GitHub before continuing.
- Stop when an undeclared path or contract change becomes necessary.

## 8. Pull Request readiness

A Pull Request must report:

- base commit;
- primary writer;
- declared write scope;
- actual changed paths;
- dependency and integration order;
- test commands and exact results;
- known conflicts and risks;
- whether another PR merged after the branch base.

If another relevant Pull Request merged, synchronize first and rerun all checks.

## 9. Integration sequence

The integration sequence is:

```text
foundation contract
    ↓
component implementation
    ↓
component integration
    ↓
repository-wide acceptance
```

Do not merge a consumer before its provider contract.

Do not resolve a shared contract by accepting whichever parallel branch merges first. Shared contracts require an explicit foundation Issue.

## 10. Handoff between models

Before handing a task from one model to another:

1. stop writing;
2. run required checks;
3. update `HANDOFF.md` or the Issue handoff section;
4. commit and push all intended changes;
5. confirm the remote branch is current;
6. create a new writer-prefixed branch unless the Issue explicitly allows continuation;
7. record the inherited commit and remaining scope.

The new writer must not continue from uncommitted local files.

## 11. Conflict handling

When a conflict is detected:

1. stop both affected writers from changing the overlapping area;
2. identify the owning Issue and dependency order;
3. merge the foundation or earlier task first;
4. synchronize the dependent branch from current `main`;
5. let the dependent task's primary writer resolve the conflict;
6. rerun all required checks;
7. update the Pull Request with the new base and evidence.

Never resolve concurrency conflicts by editing `main`, force-pushing, or silently changing another developer's branch.

## 12. Future machine enforcement

P1 governance tooling must add checks for:

- branch naming;
- changed paths outside Issue `write_scope`;
- overlapping active write scopes;
- edits to exclusive files without authorization;
- stale dependency bases;
- missing required checks;
- public contract changes without an ADR or contract Issue.

Until those checks exist, the reviewer performs this validation manually.

## 13. Runtime concurrency is separate

This document controls developer concurrency.

Framework runtime concurrency will have a separate architecture decision covering event loops, task ownership, workers, processes, threads, blocking work, backpressure, cancellation, deadlines, context isolation, shutdown, and overload tests.

The minimum invariant is already fixed: runtime concurrency must be bounded, isolated, cancellable, observable, and deterministically cleaned up.
