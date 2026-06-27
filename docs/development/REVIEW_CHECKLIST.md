# Review Checklist

Use this checklist for every phase review (by Xiao Gu or any reviewer).

## Scope

- [ ] All changes are within the Issue's allowed scope.
- [ ] No production code modified outside the allowed file list.
- [ ] No new third-party dependencies added.

## Security

- [ ] No secrets, API keys, or credentials committed.
- [ ] No `.env` files read or committed.
- [ ] `CancelledError` is propagated, never swallowed.
- [ ] No `except Exception: pass` in cleanup paths.
- [ ] Security-sensitive data is redacted in logs.

## API

- [ ] No Stable API deleted without deprecation cycle.
- [ ] No Stable API behavior changed without compat shim.
- [ ] No non-existent import paths classified as Stable.
- [ ] Legacy entry points classified before any deletion.

## Dependencies

- [ ] No new circular dependencies introduced.
- [ ] Dependency direction per `docs/architecture/dependency-rules.md`.
- [ ] No `compat/` import from core/security/contrib/data/adapters.

## Ownership

- [ ] No `app/` or `config/` code importing `lingshu.system.*`.
- [ ] No scaffold templates importing `lingshu.system.*`.
- [ ] No `src/lingshu/` code importing `app.*` or `config.*`.
- [ ] No `BusinessModel` or backend conventions placed in generic data core.

## Tests

- [ ] Full suite passes (≥446 passed, 1 skipped, 0 failed).
- [ ] Architecture boundary tests pass.
- [ ] No tests modified to mask real violations.
- [ ] No `pytest.skip` to bypass a rule.
- [ ] No empty always-pass assertions.

## Documentation

- [ ] No duplicate fact sources created.
- [ ] Old doc paths converted to compatibility pointers.
- [ ] ADRs created for architectural decisions.
- [ ] HANDOFF.md updated with current state.

## Rollback

- [ ] Changes are revertable via `git revert`.
- [ ] No destructive git operations used.

## Merge Authority

- [ ] Developer did NOT self-declare acceptance.
- [ ] Developer did NOT auto-merge.
- [ ] Xiao Gu has reviewed and declared acceptance (or requested changes).
- [ ] Final merge is the user's responsibility.
