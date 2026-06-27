# LingShu Development Constitution V1

Status: Active
Version: 1.0
Phase established: C2-RC (Issue #21, PR pending)

> This constitution governs all development on the LingShu Framework repository.
> It applies to every developer — human, AI, or future tool. Developers are
> replaceable; these rules are not.

## 1. Scope

This constitution applies to:

- All source code under `src/lingshu/` (framework).
- All source code under `app/` and `config/` (project).
- All test code under `tests/`.
- All documentation under `docs/`.
- All GitHub Issues, branches, and pull requests.

It does NOT govern:

- End-user application logic written by downstream projects using LingShu.
- Third-party packages installed via pip.

## 2. Roles And Permissions

### 2.1 User / Project Lead

- Holds final authority over project scope and priorities.
- Holds final merge authority for all pull requests.
- May override any decision, including this constitution, with explicit written instruction.

### 2.2 Xiao Gu (Architect)

- Responsible for architecture planning and design documents.
- Creates and maintains GitHub Issues and Pull Requests.
- Performs independent code and documentation review.
- Performs phase acceptance (confirms a phase meets its Issue requirements).
- Does **NOT** perform the final merge — that is the user's authority.

### 2.3 Developer (human or AI)

- May be any person or any AI tool (Qwen, GLM, Codex, Claude, Gemini, etc.).
- Executes only the current Issue's scope.
- Must not exceed the Issue's defined boundaries.
- Must not modify acceptance criteria to accommodate an implementation.
- Must not self-declare acceptance or auto-merge.
- Must read the constitution, CURRENT_PHASE, the current Issue, and relevant
  ADRs before starting work.

### 2.4 Separation Of Duties

- **Review and implementation must be separated.** The developer who wrote the
  code cannot declare acceptance.
- Only Xiao Gu can declare acceptance. Only the user can merge.

## 3. Sources Of Truth (Priority Order)

1. **GitHub Issue** for the current phase — defines scope, deliverables, tests.
2. **Remote branch** on `github` — the authoritative code state.
3. **Pull Request** and its review comments — review findings and decisions.
4. **This constitution** — stable development rules.
5. **`docs/development/CURRENT_PHASE.md`** — current phase tracking.
6. **`docs/architecture/architecture-contract.json`** — machine-readable rules.
7. **ADRs in `docs/decisions/`** — architectural decision records.

**Chat history, model memory, and session context are NOT sources of truth.**
If a rule is not in the above artifacts, it does not exist.

### 3.1 Issue Scope And Constitution Authority

- The Issue defines the **current task scope**, but does NOT automatically
  override the constitution.
- A deviation from the constitution requires an approved **ADR or Deviation
  record** referenced in the Issue.
- The user can authorize a deviation verbally or in chat, but it only becomes
  a repository fact after being recorded in both the Issue **and** an ADR or
  constitution update.
- Chat instructions (including model session context) are NOT permanent
  repository rules.
- If an Issue conflicts with the constitution and no approved deviation ADR
  exists: **STOP**. Do not proceed until Xiao Gu or the user resolves the
  conflict and records the decision.

## 4. Phase Lifecycle

1. **Issue creation:** Xiao Gu creates a GitHub Issue defining scope,
   deliverables, test contract, and prohibitions.
2. **Branch creation:** Developer creates a branch named per the prefix rules
   in §5.1 (writer prefix + `phase-<phase>-<slug>`).
3. **Implementation:** Developer works on the branch, following all rules.
4. **Verification:** Developer runs all required tests and checks.
5. **PR creation:** Xiao Gu creates and maintains the PR by default (see §5.2).
6. **Review:** Xiao Gu reviews the branch/PR independently.
7. **Acceptance:** Xiao Gu declares acceptance or requests changes.
8. **Merge:** User performs the final merge.
9. **Unblock:** The next phase may start only after merge.

**No phase may be skipped, parallelized without explicit Issue permission,
or started before the previous phase is merged.**

## 5. Branch And PR Rules

- One phase = one Issue = one branch = one PR.
- A branch has exactly one writer at a time.
- Always use the `github` remote (never `origin`).
- Synchronize with `git merge --ff-only` (fast-forward only).
- Never commit directly to `main`.
- Never force push.
- Never rebase a phase branch.
- Never run `git reset --hard` or `git clean -fd`.
- Before switching devices or developers: test, update HANDOFF, commit, push,
  confirm clean worktree.

### 5.1 Branch Prefixes

Every implementation branch must be prefixed by the **primary writer** of
that branch. The prefix identifies who is actively writing the branch and is
enforced by the architecture contract (`architecture-contract.json`).

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
3. The current writer is **qwen**; the current branch is
   `qwen/phase-c2-rc-development-constitution`.
4. **When switching developers:** the old developer must test, update HANDOFF,
   commit, push, and stop writing. The new developer must create a new
   prefix branch and record the inherited baseline in HANDOFF.
5. **Without explicit Issue approval**, no developer may continue writing
   another developer's branch.

### 5.2 PR Creation

- Xiao Gu creates and maintains PRs by default.
- The developer only commits and pushes the branch.
- The developer may create a PR only when the Issue explicitly authorizes it.
- The user performs the final merge.

## 6. Directory Ownership

| Path | Owner | Modifiable by project? |
|---|---|---|
| `src/lingshu/**` | Framework maintainers | **No** |
| `src/lingshu/language/**` | Framework | Override only via `app/language/` |
| `src/lingshu/resources/**` | Framework | **No** |
| `src/lingshu/scaffold/*.j2` | Framework | **No** |
| `app/**` | Project developers | **Yes** |
| `config/**` | Project developers | **Yes** |
| Scaffold-generated files | **Project** after generation | **Yes** |

Business developers must never modify `site-packages/lingshu/` to implement
business requirements. All business customization goes in `app/` or `config/`.

See: `docs/architecture/ownership-boundaries.md`

## 7. Dependency Direction

Current codebase (pre-refactor):

- `system/` contains most framework logic.
- `middleware/` contains legacy modules.
- `exception` depends on `system.context` and `system.sanic_adapter` (static).
- `system.auth.middleware` depends on `exception` (lazy import) — potential
  lazy cycle.

Target layer dependency rules (for future refactoring phases):

| Layer | May import | Must NOT import |
|---|---|---|
| `core/` | Standard library only | Sanic, JWT, DB drivers, any lingshu package |
| `security/auth/` | `core/`, PyJWT | Sanic, adapters, tenant, data, compat |
| `contrib/tenant/` | `core/`, `security/auth/` | Sanic, adapters, data, compat |
| `data/` | `core/`, third-party drivers | Sanic, request proxy, security, tenant, compat |
| `adapters/sanic/` | `core/`, `security/auth/`, `contrib/tenant/`, Sanic | data, compat |
| `compat/` | Legacy implementations | Must not be imported by core/security/contrib/data/adapters |
| Top-level facades | All framework packages | compat (directly) |

See: `docs/architecture/dependency-rules.md`

## 8. Public API And Deprecation

### 8.1 API Tiers

| Tier | Definition | Deletion procedure |
|---|---|---|
| **Stable** | Documented public API that is not provisional. Includes top-level facades, `RoutePolicy`, `Principal`, `Authenticator` (protocol), `configure_authentication`, `get_principal`, `require_principal`, `TenantContext`, `TenantResolver` (protocol), `configure_tenant_resolution`, `get_tenant`, `require_tenant`, and outcome/result types. | Compat shim + DeprecationWarning + migration docs + 2 minor version minimum + scaffold update |
| **Experimental** | Public but provisional. Includes the chain and concrete-resolver implementations: `AuthenticatorChain`, `JwtBearerAuthenticator`, `TenantResolverChain`, `ClaimTenantResolver`. Subject to signature changes. | PendingDeprecationWarning + 1 minor version + migration docs |
| **Internal** | `system.*` subpackages not documented as public | Free to move; delete if zero consumers confirmed |
| **Legacy** | Old importable entry points still in use | Move to `compat/` with DeprecationWarning |
| **Deprecated** | Already in `compat/` or marked deprecated | Remove at next major version |

**Plan A (conservative classification):** chain and concrete-implementation
symbols are classified as **Experimental**, not Stable. This ensures that
the interfaces most likely to evolve (auth chains, JWT bearer, tenant
resolver chains, claim-based resolver) carry the lighter stability guarantee
while the protocols, facades, and accessor functions they build on remain
Stable. Rationale: ADR-002.

### 8.2 Rules

- No import path is deleted until it is classified into a tier.
- Legacy entry points cannot be deleted based solely on "zero internal consumers."
- Stable API deletion requires a version/deprecation cycle, never an ad-hoc removal.
- `data_state`, `created_time`, `updated_time`, logical-delete fields are
  backend conventions — they do NOT enter the generic data core.

See: `docs/architecture/public-api-contract.md`

## 9. Safety, Cancellation, Cleanup, And Exception Handling

### 9.1 Cancellation

- `asyncio.CancelledError` must always be propagated. Never caught as a
  generic exception. Never swallowed.
- Never use bare `except` that catches `CancelledError`.

### 9.2 Cleanup

- Cleanup hooks use an app-scoped registry (per-app instance, not module-level
  global). See `src-target-boundaries.md` §2.
- Per-hook completion tracking: each hook is marked complete only after it runs.
- No pre-set "done" flag before hooks execute.
- `except Exception: pass` is **forbidden** in cleanup code.

### 9.3 Exception handling

- Security-sensitive data (tokens, passwords, API keys) must be redacted
  before logging.
- Exception summaries must use sanitized messages, not raw `str(exc)`.

### 9.4 Secrets

- Never read, log, or commit real `.env` files, database credentials, or API keys.
- Tests must not depend on real credentials.

## 10. Testing And Verification

- Every phase must pass the full test suite before PR.
- The full suite (`python -m pytest -q`) is mandatory — specialty suites alone
  are insufficient.
- `python -m pip check` must report no broken requirements.
- `git diff --check` must pass (no whitespace errors).
- Architecture boundary tests (`tests/architecture/`) must pass.
- Tests must not be modified to mask real violations.
- No `pytest.skip` to bypass an entire rule module.
- No empty assertions that always pass.

## 11. ADR And Documentation

- Architectural decisions are recorded as ADRs in `docs/decisions/`.
- Each ADR must contain: Status, Context, Decision, Consequences, Rejected
  alternatives, Change conditions.
- ADRs must not implement production code.
- Documentation must not create duplicate facts sources. When a fact moves,
  old locations become compatibility pointers only.

## 12. Deviation Approval

Any deviation from this constitution requires:

1. A new ADR documenting the deviation and its justification.
2. Explicit approval from Xiao Gu (review) and the user (scope decision).
3. Update to the constitution or architecture contract to reflect the approved
   deviation.

Deviations must not be made unilaterally by the developer.

## 13. Violation Handling

If a developer violates this constitution:

1. The violation is reported in the PR review.
2. The violating change must be corrected before acceptance.
3. If already merged, the change is reverted in a follow-up PR.
4. Repeated violations may result in the developer being barred from the
   repository (at the user's discretion).

## 14. Constitution Version And Revision

- This is Constitution V1, established in C2-RC.
- Revisions require a new ADR + Xiao Gu review + user approval.
- The version number is recorded in `docs/architecture/architecture-contract.json`
  under `constitution_version`.
- Non-breaking clarifications (typos, formatting) may be made by Xiao Gu
  without a new ADR, but the change must be noted in the PR description.
