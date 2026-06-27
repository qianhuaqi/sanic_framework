# ADR-001: Framework-Project Ownership

## Status

Proposed — accepted by merge of the C2-RC PR

## Context

The LingShu Framework ships as an installable Python package (`src/lingshu/`).
Projects scaffolded from it generate application code (`app/`, `config/`).
Without a clear ownership boundary, developers may be tempted to modify the
installed framework to implement business requirements, creating
unmaintainable forks.

The PR #20 architecture audit (`src-convergence-audit.md` §1–§2) documented
the complete directory inventory and confirmed:
- `src/lingshu/**` is framework-owned.
- `app/**` and `config/**` are project-owned.
- Scaffold templates are framework source; generated files are project-owned.
- `app/resources/` does not exist.
- Language files exist in both locations (framework defaults + project overrides).

## Decision

1. `src/lingshu/**` is exclusively framework-maintained. Projects must not
   modify the installed package.
2. `app/**` and `config/**` are exclusively project-maintained.
3. Scaffold templates (`src/lingshu/scaffold/*.j2`) are framework source.
   Generated output is project-owned after generation.
4. `src/lingshu/language/` provides framework defaults; `app/language/`
   provides project overrides. Loading order: project → framework.
5. Business developers use `app/` or `config/` for all customization.

## Consequences

- Framework upgrades are safe — they never touch project code.
- Projects must sync their `app/language/` copies when new framework error
  codes are added (or rely on the fallback mechanism).
- No `public/` directory is created. Top-level facades remain the stable API.
- Machine boundary tests verify that `app/**` does not import `lingshu.system.*`
  and that `src/lingshu/**` does not import `app.*` or `config.*`.

## Rejected Alternatives

- **Allow project modifications to framework:** Creates unmaintainable forks,
  makes upgrades impossible. Rejected.
- **Create a `public/` package:** Adds a third layer (facade → public → system)
  without clear benefit. Rejected in PR #20 review (Option A chosen).

## Change Conditions

- This decision may be revisited if a requirement emerges for downstream
  projects to extend framework internals in a controlled way (e.g., plugin
  system). That would require a new ADR.
