# ADR-006：简化包根目录并建立官方扩展体系

- Status: Proposed
- Decision owner: Project Lead
- Issue: #26
- Target acceptance: merge of the planning PR created from `research/directory-release-roadmap`
- Date: 2026-06-28

## Context

LingShu Framework currently uses a `src/lingshu/` package layout. This layout is a valid Python packaging technique, but it is not a runtime architecture requirement. The repository also contains a reviewed C2-R1–R6 migration roadmap whose target paths assume that `src/lingshu/` remains the permanent framework root.

The project lead has approved a simpler long-term repository structure. The framework package should live directly at repository root as `lingshu/`, while the runtime architecture is divided into a small mandatory kernel and official extension packages.

The decision has two goals:

1. make the repository easier for human developers and multiple AI developers to understand and operate;
2. prevent optional infrastructure capabilities from accumulating inside the mandatory framework kernel.

This ADR records a change to the package-root and extension-ownership assumptions. It does not authorize an immediate physical directory move.

## Decision

### 1. Permanent package root

The long-term framework package root is:

```text
lingshu/
```

The permanent target does not include a top-level `src/` wrapper.

The physical move from `src/lingshu/` to `lingshu/` must be performed only in the release phase assigned to package-layout migration. Until that phase is accepted, the current `src/lingshu/` tree remains the code-state source of truth.

### 2. Mandatory kernel

The smallest mandatory framework runtime is placed under:

```text
lingshu/core/
```

`core` owns only capabilities that remain necessary when all optional integrations are absent, including application lifecycle contracts, configuration contracts, context boundaries, service-container contracts, extension registration contracts, base exception semantics, time and ID abstractions, serialization rules, protocols, and other dependency-free primitives.

`core` must not import:

- Sanic;
- database drivers;
- Redis clients;
- JWT implementations;
- storage SDKs;
- task-queue implementations;
- any module under `lingshu.extensions`.

### 3. Official extensions

Official integrations maintained in the LingShu repository are placed under:

```text
lingshu/extensions/
```

Expected official extension families include:

```text
sanic/
auth/
tenant/
database/
redis/
cache/
storage/
scheduler/
logging/
openapi/
```

Not every directory must be created immediately. A directory is introduced only when its extension is implemented or migrated.

An official extension may depend on public `core` contracts and explicitly documented extension dependencies. `core` must never depend on an extension.

### 4. Third-party extensions

Community or product-specific extensions do not enter `lingshu.extensions`. They are distributed as independent packages using names such as:

```text
lingshu-ext-kafka
lingshu-ext-elasticsearch
lingshu-ext-wechat
```

The import package may use the normalized Python form, for example `lingshu_ext_kafka`.

### 5. Repository support areas

The target repository keeps these top-level areas:

```text
lingshu/   framework package
tests/     repository verification
docs/      architecture, guides, decisions, examples
```

Additional rules:

- runnable examples belong under `docs/examples/` rather than a top-level `examples/` directory;
- a generic top-level `scripts/` dumping ground is not part of the permanent target;
- real development, migration, release, or verification utilities may be organized under `tools/` when they exist;
- `tests/` remains separate from `lingshu/testing/`: the former tests LingShu itself, while the latter contains testing helpers exposed to framework users.

### 6. Stable API protection

The physical repository layout may change without changing the public Python package name. Existing Stable import paths must remain available through the repository's public-facade and deprecation policies.

No Stable path may be removed merely because internal files move. Compatibility shims and migration documentation remain mandatory where required by the Development Constitution.

## Release strategy

This decision is implemented in stages:

1. freeze documentation, ownership, and release mapping;
2. contain legacy modules and establish compatibility shims;
3. extract a dependency-free core and official extensions while code still lives under `src/lingshu/`;
4. stabilize extension lifecycle and package contracts;
5. move the already-converged package physically from `src/lingshu/` to `lingshu/`;
6. update packaging, tools, scaffolds, tests, and documentation;
7. stabilize the public extension SDK before v1.0.

The physical removal of `src/` is intentionally delayed until internal boundaries are stable. This prevents a package-root migration from being mixed with large behavioral refactors.

## Consequences

### Positive

- The repository has fewer permanent top-level layers.
- Framework-essential code and optional integrations have a visible boundary.
- Official and third-party extensions have different ownership and release rules.
- The package-root move becomes a mechanical migration after internal convergence.
- AI developers receive a simpler and more enforceable directory model.

### Costs

- Existing constitution, architecture contracts, ownership documents, tests, scaffolds, and packaging configuration must be updated over multiple phases.
- The repository temporarily contains documents describing the current `src/lingshu/` state and documents describing the approved target state.
- Compatibility modules may survive for several minor releases.
- The current C2-R1–R6 roadmap must be mapped into release versions rather than executed literally as a permanent `src/` design.

## Supersession and compatibility with existing documents

This ADR supersedes only the permanent package-root assumption that `src/lingshu/` is the final target. Existing reviewed work remains useful as follows:

- dependency-direction rules remain valid conceptually;
- compatibility and deprecation rules remain valid;
- C2-R1–R6 task analysis remains implementation input;
- paths in existing documents are current-state or transitional paths until their assigned release updates them.

The canonical release sequence is defined in `docs/roadmap/RELEASE_ROADMAP.md`. The canonical target tree is defined in `docs/architecture/target-directory-plan.md`.

## Non-decisions

This ADR does not freeze:

- the final public class names of the extension SDK;
- whether each official extension is installed by constructor, registration function, or entry point;
- the exact optional-dependency groups in `pyproject.toml`;
- release dates;
- removal dates for Deprecated APIs beyond the existing deprecation policy.

Those details require their own implementation Issues and, where necessary, additional ADRs.