# LingShu Framework Release Roadmap

- Status: Proposed
- Issue: #26
- Baseline blueprint: v0.7
- Target: v1.0.0 stable
- Dates: intentionally not scheduled; release gates are quality-based

## 1. Roadmap purpose

This document answers one question for every planned version:

> What must be completed and accepted before this version may be released?

The roadmap maps the reviewed C2-R1–R6 technical work into product releases and incorporates the approved target package layout:

```text
lingshu/
├─ core/
├─ extensions/
├─ cli/
└─ testing/
```

The version numbers below describe release outcomes. A release may contain multiple separately reviewed phases, but every phase still follows one Issue, one branch, one PR, independent review, and final user merge.

No implementation phase may begin until its prerequisite planning or implementation PR has been accepted and merged.

## 2. Global release gates

Every version must satisfy all applicable gates:

1. full repository test suite passes;
2. architecture boundary tests pass;
3. `pip check` passes;
4. package build/install smoke tests pass when packaging is touched;
5. no Stable public API is removed without the constitution's deprecation process;
6. new behavior has tests and documentation;
7. the phase Issue's forbidden scope remains untouched;
8. migration and rollback notes are present for structural changes;
9. Xiao Gu performs independent acceptance;
10. the project lead performs the final merge and release decision.

## 3. Release sequence overview

| Version | Theme | Existing roadmap mapping | Release outcome |
|---|---|---|---|
| v0.7.x | Architecture and governance freeze | C2-R0, C2-RC, Blueprint v0.7 | rules and machine boundaries exist before refactoring |
| v0.8.0 | Legacy containment and compatibility baseline | C2-R1 | legacy middleware is isolated; stable imports remain intact |
| v0.9.0 | Dependency-free core and Sanic extension | C2-R2 + core part of C2-R4 | core kernel exists; Sanic integration is outside core |
| v0.10.0 | Official auth, tenant, and route-policy extensions | C2-R3 + remaining C2-R4 | security and tenant capabilities use official extension boundaries |
| v0.11.0 | Config, database, Redis, cache, and model decoupling | C2-R5 + C2-R6 | infrastructure capabilities are extension-owned and globals are reduced |
| v0.12.0 | Extension lifecycle and optional-dependency contract | new phase after R1–R6 convergence | official extensions share one install/lifecycle/config contract |
| v0.13.0 | Physical no-`src` package migration | new dedicated packaging phase | `src/lingshu` becomes root `lingshu` without public import changes |
| v0.14.0 | CLI, scaffold, testing, docs, and tool consolidation | scaffold/tooling follow-up | generated projects and contributor workflow match the target tree |
| v0.15.0 | Third-party extension SDK and ecosystem validation | new SDK phase | external `lingshu-ext-*` packages can integrate through public contracts |
| v0.16.0 | Beta/RC hardening | stabilization phase | performance, security, observability, packaging, and upgrade readiness |
| v1.0.0 | Stable release | final acceptance | stable public framework and extension contract |

## 4. Version details

---

## v0.7.x — Architecture and governance freeze

### Goal

Freeze the rules that all later refactoring must obey.

### Included work

- LingShu Development Constitution V1;
- machine-readable architecture contract;
- ownership, dependency, API-tier, and handoff rules;
- machine architecture boundary tests;
- Blueprint v0.7 time, ID, exception, configuration, serialization, context, telemetry, and resource-budget rules;
- reviewed C2-R1–R6 technical migration analysis;
- approved simplified target package decision through ADR-006 and Issue #26.

### Must be completed before release closure

- Current phase documents accurately reflect merged work;
- package-root conflict is recorded explicitly rather than silently overwriting old documents;
- release roadmap and target directory plan are merged;
- no production directory move occurs in this version.

### Exit gate

The repository has one accepted target direction and implementation may begin with v0.8.0.

---

## v0.8.0 — Legacy containment and compatibility baseline

### Goal

Reduce structural debt before creating permanent extension packages.

### Main work

- execute the intent of C2-R1;
- classify remaining legacy import paths;
- move legacy middleware behavior into `compat/` or clearly owned extension preparation areas;
- add `DeprecationWarning` shims where required;
- preserve all current Stable public facades;
- establish tests that fail when permanent layers import compatibility code;
- document migration paths for legacy auth, cache, signing, maintenance, parameter, and JSON helpers.

### Specifically not included

- physical removal of `src/`;
- Stable API deletion;
- full extension lifecycle SDK;
- database/model behavioral redesign.

### Exit gate

- legacy code is no longer an unclassified dependency of permanent architecture;
- all compatibility shims are tested;
- full suite and architecture gates pass;
- v0.9 work can extract core and Sanic integration without depending on legacy middleware.

---

## v0.9.0 — Dependency-free core and Sanic extension

### Goal

Create the real framework kernel and remove Sanic from that kernel.

### Main work

- execute C2-R2 under the new target naming;
- create dependency-free core primitives for:
  - lifecycle;
  - execution context;
  - extension registration contracts;
  - time and deadline semantics;
  - IDs;
  - exception semantics;
  - serialization;
  - telemetry fields;
  - shared immutable types;
  - resource limits;
- move Sanic request lifecycle, middleware installation, resource registry, cleanup registry, finalization, and routing integration into the transitional target for `extensions/sanic/`;
- implement app-scoped cleanup registry with cancellation safety and per-hook idempotency;
- begin RoutePolicy unification at the public/core boundary;
- add machine tests proving `core` imports no Sanic or infrastructure drivers.

### Compatibility

- `lingshu.system.sanic_adapter` and other Internal paths may remain as compatibility re-exports during their documented lifecycle;
- Stable top-level facades remain unchanged.

### Exit gate

- `core` is independently testable;
- Sanic integration is outside `core`;
- cleanup and cancellation behavior is fully tested;
- no circular dependency is introduced;
- full suite passes.

---

## v0.10.0 — Official auth, tenant, and route-policy extensions

### Goal

Place request security and tenant capabilities behind explicit official extension boundaries.

### Main work

- map C2-R3 to `extensions/tenant/` rather than a permanent `contrib/tenant/` target;
- move authentication implementation into `extensions/auth/` while keeping `lingshu.auth` as the stable facade;
- move tenant implementation into `extensions/tenant/` while keeping `lingshu.tenant` as the stable facade;
- complete C2-R4 RoutePolicy unification;
- define public protocols shared by Sanic, auth, and tenant extensions;
- register auth/tenant cleanup through the Sanic extension lifecycle;
- prevent auth and tenant implementations from importing Sanic internals directly;
- preserve current auth/tenant result types and stable accessors.

### Exit gate

- auth, tenant, and Sanic extension boundaries are machine enforced;
- Stable facades pass existing compatibility tests;
- tenant remains optional;
- RoutePolicy has one authoritative definition;
- full suite passes.

---

## v0.11.0 — Infrastructure extensions and model decoupling

### Goal

Move configuration and infrastructure behavior out of global framework internals.

### Main work

- execute C2-R5 capability-scoped configuration modularization;
- execute C2-R6 dependency injection and model decoupling;
- introduce or converge official extension areas for:
  - database;
  - Redis;
  - cache;
  - logging;
- separate generic data access contracts from backend/project conventions;
- keep `data_state`, logical-delete, timestamp, and BusinessModel-style project conventions out of generic core;
- allow existing global facades to delegate to registered extension services;
- update scaffold templates to use Stable public imports;
- add generated-project smoke tests.

### Compatibility

- existing Stable `lingshu.db`, `lingshu.model`, and top-level facade behavior remains available;
- fallback to globals may remain temporarily with warnings where the approved deprecation policy requires it.

### Exit gate

- infrastructure drivers are not imported by core;
- model/data code can receive explicit services;
- generated projects import only approved public APIs;
- full suite, scaffold smoke test, and architecture gates pass.

---

## v0.12.0 — Unified official extension contract

### Goal

Make official extensions consistent instead of merely placing code in similarly named folders.

### Main work

- freeze the extension protocol and registry API;
- define extension identity, version, dependency, install, startup, readiness, shutdown, and uninstall behavior;
- define configuration validation and runtime-reload rules;
- define service registration and conflict behavior;
- define extension dependency ordering and cycle detection;
- define health/readiness degradation semantics;
- define optional dependency errors with actionable messages;
- organize optional dependency groups in `pyproject.toml` planning, without yet moving the package root;
- provide contract tests applied to every official extension.

### Expected usage direction

The exact public syntax is frozen in this release through its own ADR. It may resemble explicit installation such as:

```python
app.install(DatabaseExtension(...))
app.install(RedisExtension(...))
```

but this roadmap does not pre-approve exact class names or signatures.

### Exit gate

- all official extensions pass one shared contract test suite;
- dependency cycles fail fast;
- lifecycle failures have defined rollback/cleanup behavior;
- optional integrations do not become hidden mandatory dependencies.

---

## v0.13.0 — Physical no-`src` package migration

### Goal

Perform the approved repository simplification as a mechanical packaging change after internal architecture has converged.

### Main work

```text
src/lingshu/  →  lingshu/
```

Update:

- package discovery/build configuration;
- editable install behavior;
- CLI entry points;
- package data and resources;
- scaffold template paths;
- architecture-contract ownership roots and target paths;
- import scanners and architecture tests;
- development setup documentation;
- handoff/resume tooling paths;
- README directory guide;
- build, wheel, sdist, clean-environment install, and import smoke tests.

### Strict prohibition

This version must not contain large runtime behavior redesign. Internal moves required only to complete the package-root migration are allowed; unrelated refactoring is not.

### Exit gate

- repository root contains `lingshu/` and no permanent `src/lingshu/` package;
- `import lingshu` works only after correct installation in clean-environment tests;
- wheel and sdist contain the expected files;
- public import paths are unchanged;
- full suite passes on the new physical layout.

---

## v0.14.0 — CLI, scaffold, testing, documentation, and tools convergence

### Goal

Make all contributor and downstream workflows reflect the new architecture.

### Main work

- place CLI commands and scaffold templates under the target `lingshu/cli/` ownership model;
- provide `lingshu/testing/` helpers for downstream projects;
- reorganize repository tests by core, extensions, CLI, architecture, and integration domains where useful;
- consolidate runnable examples under `docs/examples/`;
- update README and guides for extension installation and project generation;
- audit top-level `scripts/`:
  - keep no generic dumping ground;
  - migrate real repository utilities into classified `tools/` areas;
  - keep compatibility wrappers only when required by active workflows;
- add end-to-end tests for init → configure extensions → run → shutdown.

### Exit gate

- generated projects match the new package/extension architecture;
- contributor commands work from a clean clone;
- documentation contains no contradictory permanent `src/` guidance;
- examples are executable in automated smoke tests where practical.

---

## v0.15.0 — Third-party extension SDK and ecosystem validation

### Goal

Prove that extensions outside the main repository can integrate without private imports.

### Main work

- publish the public extension authoring contract;
- define naming and compatibility policy for `lingshu-ext-*` distributions;
- define discovery/registration policy if entry points are adopted;
- create a minimal external example extension in a separate package or isolated fixture;
- verify install, configuration, lifecycle, telemetry, health, cleanup, and uninstall behavior;
- define framework/extension version compatibility metadata;
- ensure third-party extensions cannot silently override core services.

### Exit gate

- an external example extension works using only public APIs;
- no import from LingShu Internal modules is required;
- compatibility and conflict errors are deterministic and documented.

---

## v0.16.0 — Beta and release-candidate hardening

### Goal

Stop architectural expansion and validate production readiness.

### Main work

- performance and resource-budget benchmarks;
- concurrency, cancellation, timeout, and graceful-shutdown stress tests;
- security review of auth, configuration, secret redaction, and dependency surfaces;
- telemetry completeness and failure diagnostics;
- packaging and upgrade tests from supported v0.x baselines;
- Windows/Linux clean-environment verification;
- documentation review and API reference completion;
- resolve all release-blocking defects;
- classify every remaining Legacy/Deprecated path.

### Exit gate

- no open release-blocking issue;
- supported upgrade paths are documented and tested;
- public API inventory is complete;
- release candidate passes all quality gates repeatedly.

---

## v1.0.0 — Stable framework release

### Goal

Declare the core, official extension lifecycle, and documented Stable APIs production-ready.

### Required outcomes

- root `lingshu/` package layout is permanent;
- core/extension dependency direction is machine enforced;
- official extension lifecycle is Stable;
- third-party extension contract is documented and validated;
- Stable public API list is frozen and published;
- remaining compatibility paths have explicit status and removal policy;
- CLI/scaffold generates supported project structures;
- package build, install, upgrade, and runtime tests pass;
- architecture, user, extension-author, migration, and operations documentation is complete;
- changelog and v1.0 migration guide are published.

### v1.0 does not mean

- every possible extension exists;
- all Deprecated APIs are necessarily removed;
- no future additive feature work is allowed.

It means the published contracts can be relied upon under semantic versioning.

## 5. Mapping C2-R1–R6 into releases

| Existing phase | Release | Adjustment required by ADR-006 |
|---|---|---|
| C2-R1 Auth dedup + compat | v0.8.0 | retain intent; ensure extension target naming is reflected |
| C2-R2 Sanic adapter split | v0.9.0 | target `extensions/sanic/`; extract approved core primitives |
| C2-R3 Tenant relocation | v0.10.0 | target `extensions/tenant/` instead of permanent `contrib/tenant/` |
| C2-R4 RoutePolicy unification | v0.9.0–v0.10.0 | core contract first, full extension integration second |
| C2-R5 Config modularization | v0.11.0 | configurations are capability/extension scoped |
| C2-R6 Model decoupling + scaffold | v0.11.0 | generic data behavior moves toward official data extensions; scaffold uses facades |

## 6. Version change control

This roadmap is intentionally outcome-based. A version's scope may be split into smaller phases, but changing a version's architectural outcome requires:

1. a GitHub Issue explaining the change;
2. an ADR update or new ADR when architecture is affected;
3. Xiao Gu review;
4. project-lead approval and merge.

Release dates, developer assignment, and branch names are maintained in phase Issues, not frozen in this roadmap.