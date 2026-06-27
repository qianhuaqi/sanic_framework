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

## Phase C1 Boundaries

- Business code must not import `lingshu.system`.
- The current work is phase C1 only.
- Do not start phases C2, C3, C4, C5, C6, D, E, or F.
- Do not implement JWT, API Key, Session authentication, authorization, tenant resolution, HMAC, nonce, replay protection, rate limiting, idempotency stores, database backend redesign, Pydantic Schema facade, OpenAPI, TypeScript SDK, full DI, extension manifest runtime, Outbox, Audit, OTel exporters, lingshu-ms, Go runtime, Vue runtime, or device gateway in C1.
- Do not use unowned `asyncio.create_task()`.
- Do not swallow `CancelledError`.
