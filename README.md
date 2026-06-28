# LingShu Framework / 灵枢框架

Canonical repository: `qianhuaqi/lingshu`

LingShu is a greenfield, independently implemented Python Web/API framework.

LingShu does not depend on Sanic, FastAPI, Flask, Django, Starlette, or any other upper-level Web framework. The archived legacy repository creates no compatibility obligation for the new framework.

## Current status

The repository is in **P0 architecture and governance consolidation**.

There is currently no production framework package, runnable server, published wheel, or supported installation command on the greenfield `main` branch. Do not attempt to install or run LingShu yet.

Production implementation is blocked until the project lead confirms the complete Blueprint and a P1 Issue is created.

## Authoritative entrypoints

Read these before contributing:

1. [Development Constitution](docs/development/DEVELOPMENT_CONSTITUTION.md)
2. [Current Phase](docs/development/CURRENT_PHASE.md)
3. [P0 Decision Status](docs/architecture/P0_DECISION_STATUS.md)
4. [Framework Blueprint](docs/architecture/LINGSHU_FRAMEWORK_BLUEPRINT.md)
5. [Development Handoff](docs/development/HANDOFF.md)
6. Active architecture Issue: #25

## Important P0 warning

The Blueprint contains detailed candidate designs for package boundaries, repository layout, multiple distributions, `src/` directories, runtime components, extensions, and release stages.

Those sections are not automatically approved. The project lead has not yet frozen the final directory and packaging plan. No developer or AI tool may create production directories from an unresolved candidate section.

Use `docs/architecture/P0_DECISION_STATUS.md` to determine what is confirmed and what remains open.

## Greenfield rules

- New framework code will be written from scratch.
- Legacy Sanic code is not migrated, adapted, or preserved for compatibility.
- No old API compatibility layer is required before v1.0.
- LingShu will define and control its own framework kernel, HTTP runtime, server behavior, request/response model, routing, middleware, lifecycle, extension protocol, CLI, and ecosystem.
- Third-party dependencies require explicit architectural review; upper-level Web frameworks are prohibited.
- P0 allows documentation and governance work only.

## Legacy archive

The complete previous repository state is preserved at:

```text
archive/legacy-sanic-20260628
```

Archived commit:

```text
b869270e0ec7cbc324d17ef246e39d0873aab14f
```

The archive remains available for historical inspection only. It is not an implementation baseline or source of active requirements.

## Open repository decisions

Before P1, the project lead still needs to confirm:

- single package versus monorepo with multiple distributions;
- direct `lingshu/` package versus a `src/` layout;
- exact Core, HTTP, Server, Record, CLI, and extension boundaries;
- which capabilities are built in and which are separately installable;
- release stages and the first public compatibility promise;
- open-source license, contribution rules, and vulnerability-reporting policy.
