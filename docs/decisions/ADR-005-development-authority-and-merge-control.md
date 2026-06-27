# ADR-005: Development Authority And Merge Control

## Status

Proposed — accepted by merge of the C2-RC PR

## Context

The LingShu Framework repository is developed by multiple parties: human
developers, AI assistants (Qwen, GLM, Codex, Claude, Gemini, etc.), and
future tools. Without explicit role definitions and merge authority rules,
there is a risk of unauthorized merges, self-acceptance, and scope creep.

The C2-R0 phase established that chat history and model memory are not
sources of truth. This ADR formalizes the role model.

## Decision

1. **User / Project Lead** holds final scope decision and merge authority.
   No PR is merged without the user's explicit action.

2. **Xiao Gu (Architect)** is responsible for:
   - Architecture planning and design.
   - Creating and maintaining Issues and PRs.
   - Independent code and documentation review.
   - Phase acceptance (confirming a phase meets its Issue requirements).
   - Xiao Gu does NOT perform the final merge.

3. **Developer** (human or AI) executes the current Issue only:
   - Must not exceed the Issue's defined scope.
   - Must not self-declare acceptance.
   - Must not auto-merge or create PRs without explicit permission.
   - Must not modify acceptance criteria to accommodate implementation.

4. **Review and implementation must be separated.** The developer who wrote
   the code cannot declare acceptance.

5. **All rules apply equally** regardless of whether the developer is human
   or AI. The repository rules do not change when developers change.

## Consequences

- No unauthorized merges can occur.
- Acceptance is always independent.
- Any AI or human developer can be swapped in without changing the process.
- The process is fully documented in the Development Constitution and does
  not depend on any specific model or tool.

## Rejected Alternatives

- **Allow developer self-acceptance:** Creates a conflict of interest.
  Rejected.
- **Allow AI auto-merge:** Removes human oversight. Rejected.
- **Model-specific rules:** Rules tied to a specific AI tool become stale
  when the tool changes. Rejected.

## Change Conditions

- If the team structure changes (e.g., multiple architects), a new ADR must
  define the updated review and acceptance workflow.
- The merge authority always remains with the user/project lead unless
  explicitly delegated in writing.
