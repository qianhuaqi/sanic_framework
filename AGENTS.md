# Repository Agent Rules

This repository uses a strict GitHub-first workflow for LingShu Framework development.
These rules apply to **all** developers — human, AI, and future tools alike.

## Sources Of Truth

1. GitHub Issue for the current phase
2. Remote branch on `github`
3. Pull Request and its review comments
4. Development Constitution: `docs/development/DEVELOPMENT_CONSTITUTION.md`
5. Current phase: `docs/development/CURRENT_PHASE.md`
6. Architecture contracts: `docs/architecture/architecture-contract.json`
7. Related ADRs: `docs/decisions/`

**Chat history and model memory are NOT sources of truth.** If something is
not written in the above artifacts, it does not exist as a rule.

## Before Starting Work

1. Read `docs/development/DEVELOPMENT_CONSTITUTION.md`.
2. Read `docs/development/CURRENT_PHASE.md`.
3. Read the current GitHub Issue.
4. Read related ADRs in `docs/decisions/`.
5. Fetch from `github` remote: `git fetch github --prune`.
6. Verify local HEAD equals `github/<branch>`.
7. Confirm worktree is clean: `git status --short`.

## Before Leaving Or Switching Computers

1. Run relevant tests for the current work.
2. Update `docs/development/HANDOFF.md`.
3. Commit all intended changes.
4. Push to `github`.
5. Confirm worktree is clean.
6. Confirm local HEAD equals `github/<branch>`.

## Hard Rules

1. **One phase, one Issue, one branch, one PR.**
2. **A branch may have only one writer at a time.**
3. **Never commit directly to `main`.**
4. **Never auto-merge a PR.** Xiao Gu performs independent acceptance; the
   user performs the final merge.
5. **Never start the next phase until the current phase is accepted.**
6. **Always use the `github` remote** (never `origin`).
7. **Synchronize with fast-forward only.**

## Branch Naming

Every implementation branch must be prefixed by the **primary writer** of that
branch. The prefix identifies who is actively writing the branch and is
enforced by the architecture contract.

| Writer | Branch prefix |
|---|---|
| Codex | `codex/phase-<phase>-<slug>` |
| Qwen | `qwen/phase-<phase>-<slug>` |
| Gemini | `gemini/phase-<phase>-<slug>` |
| GLM | `glm/phase-<phase>-<slug>` |
| Claude | `claude/phase-<phase>-<slug>` |
| Human (named) | `human/<name>/phase-<phase>-<slug>` |
| Research (non-implementation) | `research/<slug>` — only for Issue-approved non-implementation research tasks |

Rules:

1. **Branch prefix = primary writer.** The writer who creates the branch owns
   its prefix.
2. **Xiao Gu is NOT an implementation branch prefix.** Xiao Gu performs
   planning, review, and acceptance — never writes implementation branches.
3. **When switching developers:** the old developer must test, update HANDOFF,
   commit, push, and stop writing. The new developer must create a new
   prefix branch and record the inherited baseline in HANDOFF.
4. **Without explicit Issue approval**, no developer may continue writing
   another developer's branch.

## Prohibited Git Actions

- Do not run `git reset --hard`.
- Do not run `git clean -fd`.
- Do not rebase a phase branch.
- Do not force push.
- Do not auto-save local changes outside an explicit commit.

## Roles

| Role | Responsibility |
|---|---|
| **User / Project Lead** | Final scope decision. Final merge authority. |
| **Xiao Gu** | Architecture planning. Issue and PR creation. Independent review and acceptance. Does NOT merge. |
| **Developer** (human or AI) | Executes the current Issue only. Does not exceed scope. Does not self-accept or auto-merge. |
