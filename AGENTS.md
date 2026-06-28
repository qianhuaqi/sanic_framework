# Repository Agent Rules

## Highest-priority project fact

LingShu is a greenfield, independently implemented Python Web/API framework.

It must not depend on Sanic, FastAPI, Flask, Django, Starlette, or another upper-level Web framework. The archived repository creates no compatibility obligation.

Any task, document, test, or implementation that assumes Sanic migration, Sanic adaptation, old API compatibility, continuation of the legacy runtime, or reuse of the archived source tree must stop and be reported as a scope conflict.

## Required reading order

Before any work, read:

1. `docs/development/DEVELOPMENT_CONSTITUTION.md`;
2. the active GitHub Issue;
3. `docs/development/CURRENT_PHASE.md`;
4. `docs/development/CONCURRENT_DEVELOPMENT.md` when any other task is active;
5. `docs/architecture/P0_DECISION_STATUS.md` during P0;
6. accepted ADRs under `docs/decisions/`;
7. confirmed sections of `docs/architecture/LINGSHU_FRAMEWORK_BLUEPRINT.md`;
8. `docs/development/HANDOFF.md`;
9. the active remote branch and Pull Request.

Chat history, model memory, archived branches, closed legacy Issues, and historical Pull Requests are not active implementation authority.

When active sources conflict, stop. Do not guess which rule should win.

## Current P0 restriction

P0 is architecture and governance consolidation only.

Until the project lead confirms the complete Blueprint and a P1 Issue is created, do not:

- create production framework source code;
- create package or directory skeletons that imply an unresolved layout choice;
- introduce runtime dependencies;
- implement Core, HTTP runtime, native server, router, middleware, extension runtime, CLI, or official extensions;
- publish packages;
- treat candidate package, multi-package, `src/`, directory, extension, runtime-concurrency, or release plans as frozen.

## Single repository and concurrent work

The canonical repository is `qianhuaqi/lingshu`.

Single repository does not mean shared branch or shared working directory. For concurrent work:

- one task uses one Issue, one writer-prefixed branch, one primary writer, one worktree or clone, one virtual environment, and one Pull Request;
- every Issue declares `base_commit`, `write_scope`, dependencies, conflicts, integration order, and required checks;
- two active tasks with overlapping write scopes are conflicting by default;
- shared public contracts and foundations merge before dependent features;
- multiple developers must not write in the same worktree;
- multiple primary writers must not write the same branch;
- parallel development is allowed only for independent tasks;
- integration into `main` is serial and controlled by the project lead;
- after a relevant upstream merge, dependent branches synchronize with current `main` and rerun checks;
- no developer may copy uncommitted code, stashes, caches, or virtual environments between task worktrees.

Use `docs/development/CONCURRENT_DEVELOPMENT.md` and ADR-001 as the operational authority.

## Workflow

- One active task scope, one Issue, one branch, and one Pull Request.
- Use a writer-prefixed branch unless an approved research Issue allows `research/<slug>`.
- A branch has one primary writer at a time.
- Never commit directly to `main`.
- Never force-push or rewrite shared history.
- Never enable automatic merge.
- The project lead holds final merge authority.
- Developers implement only the active Issue.
- Implementation and acceptance remain separate.
- Update `HANDOFF.md` before switching developers, models, or computers.
- Run the Issue-required checks and report exact evidence; never claim tests that were not run.

## Architecture gate

Candidate text is not executable architecture.

The current Blueprint contains unresolved distribution, directory, `src/`, component-boundary, extension, runtime-concurrency, and release choices. Use `docs/architecture/P0_DECISION_STATUS.md` to determine which decisions are confirmed, rejected, or still open.

No developer may create P1 directories or runtime code from an unresolved Blueprint section.

## Dependency gate

- Do not add an upper-level Web framework.
- Core third-party dependencies require an accepted ADR.
- Optional integrations must not become hidden mandatory dependencies.
- Do not copy dependencies from the archived project.

## Security gate

Never commit or reproduce real tokens, API keys, passwords, private keys, personal data, or production secrets. Redact sensitive values from logs, runtime records, examples, fixtures, Issues, and Pull Requests.

## Legacy archive

The previous Sanic-based repository state is frozen at:

`archive/legacy-sanic-20260628`

Archive commit:

`b869270e0ec7cbc324d17ef246e39d0873aab14f`

The archive is reference material only. Do not copy its source, tests, scaffolds, dependency files, compatibility rules, or public API assumptions into the greenfield branch without an explicit Issue and architecture review.
