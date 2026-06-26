# Repository Agent Rules

This repository uses a strict GitHub-first workflow for LingShu Framework development.

## Stable Sources Of Truth

- GitHub remote is always `github`, not `origin`.
- Each development phase must use its own branch and pull request.
- Do not merge a pull request or start the next phase until Xiao Gu has completed independent acceptance.
- A phase branch may be written by only one computer at a time.
- Codex chat history is not a source of truth.
- The only sources of truth are the Git remote branch, GitHub PR, GitHub Issue, this `AGENTS.md`, and `docs/codex/HANDOFF.md`.

## Before Starting Work

- Check the worktree.
- Fetch from the `github` remote.
- Synchronize with fast-forward only.
- Verify local `HEAD` equals `github/<branch>`.
- Read `docs/codex/HANDOFF.md`.
- Read the latest comments on the current GitHub PR.

## Before Leaving Or Switching Computers

- Run the relevant tests for the current work.
- Update `docs/codex/HANDOFF.md`.
- Commit all intended changes.
- Push to `github`.
- Confirm the worktree is clean.
- Confirm local `HEAD` equals `github/<branch>`.

## Prohibited Git Actions

- Do not run `git reset --hard`.
- Do not run `git clean -fd`.
- Do not rebase this phase branch.
- Do not force push.
- Do not automatically save local changes outside an explicit commit.

## Phase B Boundaries

- Business code must not import `lingshu.system`.
- The current work is phase B only.
- Do not start phases C, D, E, or F.
