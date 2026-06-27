# Ownership Boundaries

Status: Proposed — frozen by merge of the C2-RC PR
Source: `docs/architecture/src-convergence-audit.md` §1–§2

## 1. Framework-Owned Paths

| Path | Description |
|---|---|
| `src/lingshu/**` | All framework source code |
| `src/lingshu/language/**` | Framework built-in error-code messages (defaults) |
| `src/lingshu/resources/**` | Framework built-in error-code module registry |
| `src/lingshu/scaffold/*.j2` | Scaffold templates (framework source) |

Framework maintainers own these paths. Projects must not modify the installed
`lingshu` package to implement business requirements.

## 2. Project-Owned Paths

| Path | Description |
|---|---|
| `app/**` | All project application code |
| `app/language/**` | Project error-code overrides and additions |
| `config/**` | Project-level configuration |

Project developers own these paths. Framework upgrades do not overwrite them.

## 3. Scaffold Boundary

- Scaffold templates (`src/lingshu/scaffold/*.j2`) are **framework source**.
- Generated files (output of scaffolding) are **project-owned** after generation.
- Framework upgrades do not touch already-generated files.
- Scaffold templates must generate code using Stable import paths only.

## 4. Language Double-Source

- `src/lingshu/language/` provides framework defaults.
- `app/language/` provides project overrides and additions.
- Loading order: `app/<version>/language/` → `app/language/` → `src/lingshu/language/`.
- When new error codes are added to the framework, projects must sync their
  copies or rely on the fallback mechanism.

## 5. Key Rules

1. Business developers must never modify `site-packages/src/lingshu/`.
2. All business customization goes in `app/` or `config/`.
3. No `public/` directory will be created — top-level facades stay in place.
4. `BusinessModel` and backend conventions (`data_state`, `created_time`,
   `updated_time`, logical delete) do NOT belong in the generic data core.
5. Importable entry points cannot be deleted based solely on "zero internal
   consumers" — they must be classified and follow the deprecation cycle.
