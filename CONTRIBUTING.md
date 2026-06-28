# Contributing to LingShu

Thank you for helping build LingShu.

## Before contributing

Please read:

- `AGENTS.md`;
- `docs/architecture/LINGSHU_FRAMEWORK_BLUEPRINT.md`;
- `docs/architecture/P0_DECISION_STATUS.md`;
- `docs/development/CURRENT_PHASE.md`;
- `CODE_OF_CONDUCT.md`;
- `SECURITY.md`.

Do not report an unpatched vulnerability in a public issue.

## Contribution model

LingShu uses:

```text
one task
→ one GitHub Issue
→ one primary writer
→ one isolated branch/worktree/environment
→ one Pull Request
```

The Issue must declare:

- objective and acceptance criteria;
- `primary_writer`;
- `base_commit`;
- `write_scope`;
- `read_dependencies`;
- `depends_on`;
- `conflicts_with`;
- `integration_order`;
- `required_checks`.

Do not share a writable worktree or branch. Do not commit directly to `main`. Do not use a long-lived `develop` branch. The project lead performs the final merge.

## Developer Certificate of Origin

LingShu uses Developer Certificate of Origin 1.1 and does not require a Contributor License Agreement initially.

Every commit must include a sign-off:

```text
Signed-off-by: Your Name <your.email@example.com>
```

Create signed commits with:

```bash
git commit -s
```

The sign-off certifies the statements in `DCO`. A bot or maintainer may block a Pull Request containing unsigned commits.

## Licensing of contributions

Unless explicitly marked otherwise before submission, contributions accepted into this repository are licensed under Apache License 2.0 under the terms described in `LICENSE`.

Do not submit code, documentation, generated assets, data, or dependencies that you do not have the right to contribute.

## Branch naming

Use a writer prefix and task purpose:

```text
human/<name>/<task>
qwen/<task>
glm/<task>
gemini/<task>
```

Branch names must map to a dedicated Issue.

## Pull Requests

A Pull Request must:

- reference its Issue;
- remain inside the declared write scope;
- explain behavior, risks, and intentionally deferred work;
- include or update tests for behavior changes;
- update public documentation and `CHANGELOG.md` when user-visible behavior changes;
- avoid unrelated formatting, generated, dependency, or refactor changes;
- pass required checks;
- remain mergeable without force-pushing shared history.

Do not enable auto-merge. Do not merge your own Pull Request unless the project lead explicitly delegates that action.

## Commit guidance

Prefer focused commits with imperative subjects, for example:

```text
feat(router): add deterministic static-route matching
fix(runtime): preserve cancellation during cleanup
 docs(governance): define release policy
```

Fixup commits are acceptable during review, but the final history must remain understandable. Rewriting a shared branch requires explicit agreement from all affected writers.

## Development setup

The implementation baseline after P0 freeze will use:

```text
CPython >= 3.12
root package layout: lingshu/
no src/ directory
Hatchling build backend
```

Exact setup commands belong to the first P1 package/CI Issue and must be verified from the repository rather than guessed.

## Tests and quality

Changes must run the checks declared by their Issue. Depending on scope, checks may include:

- unit and contract tests;
- concurrency, cancellation, and leak tests;
- protocol/security tests;
- type and lint checks;
- package-boundary checks;
- wheel/sdist inventory and clean-install tests;
- Windows, Linux, and macOS compatibility checks.

A passing editable installation is not release evidence.

## Public API changes

Public API is what the documentation and explicit export manifests declare, not every importable name.

Before changing a public contract:

- follow `docs/governance/RELEASE_AND_COMPATIBILITY_POLICY.md`;
- document compatibility impact;
- add migration guidance for breaking changes;
- add deprecation warnings and tests where required;
- update the changelog.

## Security-sensitive changes

Security-sensitive changes need explicit threat analysis, safe failure behavior, negative tests, and review of logs, errors, records, traces, configuration dumps, and package artifacts for secret leakage.

## Code of Conduct

All participation is governed by `CODE_OF_CONDUCT.md`.
