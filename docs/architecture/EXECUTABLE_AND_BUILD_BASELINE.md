# LingShu Executable and Build Baseline

- Status: Accepted through P0-D6
- Decision Issue: #46 (completed)
- Pull Request: #47
- Effective merge commit: `5f89572398cee509b9571ee1fe8c20bd2f71dfeb`
- Parent Issue: #25
- Related ADR: `docs/decisions/ADR-006-executable-cli-support-and-build-baseline.md`

## 1. Ownership map

```text
Application
  routes, middleware, extensions, configuration revision, lifecycle plan

Server
  one Worker runtime, one event loop, listener/transport, protocol execution, readiness, drain

Supervisor
  process spawn, one-time listener binding/transfer, Worker readiness, restart budget, signals, exit

CLI
  arguments, target specification, configuration overrides, Supervisor setup, diagnostics, terminal exit
```

Application does not supervise processes. Kernel does not import Server.

## 2. Public single-Worker Server surface

```python
from lingshu.server import Server, ServerConfig, serve
```

```python
server = Server(app, ServerConfig(host="127.0.0.1", port=8000))
await server.start()
await server.wait_closed()
```

```python
serve(app, host="127.0.0.1", port=8000)
```

Rules:

- Server/serve are single-Worker;
- ServerConfig is immutable and validated before binding;
- Application freeze precedes listener creation;
- failed startup performs reverse cleanup and leaves no partial listener state;
- programmatic Server installs no global signals by default;
- serve owns an event loop and supported main-thread signals and rejects use from a running loop;
- drain/close is idempotent;
- multi-Worker Supervisor remains CLI/internal initially;
- root exports remain `LingShu`, `Request`, `Response`, and `HTTPException`.

## 3. CLI

Equivalent entry points:

```text
lingshu ...
python -m lingshu ...
```

Initial commands:

```text
lingshu run TARGET
lingshu check TARGET
lingshu version
```

`check` validates/imports/freezes without binding or accepting traffic. `version` does not import user application code.

## 4. Target grammar

```text
module:attribute
```

Accepted:

```text
project.api:app
project.api:create_app --factory
```

Rejected:

```text
app.py:app
project.api:create_app()
project.api:container.app
project.api:apps[0]
arbitrary expressions
implicit module scanning
```

Without `--factory`, target is a LingShu instance. With `--factory`, target is a synchronous zero-argument callable returning LingShu. Each Worker imports its own target.

## 5. Run options and profiles

Initial options:

```text
--factory
--host
--port
--workers
--config
--profile
--reload
--graceful-timeout
--hard-stop-timeout
--log-level
```

Profiles:

```text
production
development
test
```

`run` defaults to production. `--reload` explicitly selects development. All values use ADR-005 schema/precedence rules.

## 6. Development reload

```text
watcher parent
└─ one child Worker
```

Reload is process replacement, not in-process module reload and not production configuration-revision reload.

- one Worker only;
- multi-Worker reload fails before startup;
- changes are debounced/coalesced;
- old child receives bounded stop;
- VCS, environments, caches, build output, records, and configured exclusions are ignored;
- no production zero-downtime guarantee.

## 7. Multi-Worker process model

Cross-platform semantic baseline:

```text
spawn
```

- Supervisor does not pass inherited mutable Application state;
- each Worker imports, validates/freezes, starts one loop/runtime, and reports RevisionId/readiness;
- all required Workers must report one RevisionId;
- deterministic import/configuration/freeze failures are startup failures, not restart loops;
- unexpected exits use ADR-002 restart budgets.

## 8. Listener ownership

```text
Supervisor binds once
→ explicit descriptor/handle transfer
→ Workers accept from transferred listener
```

No Worker bind race and no correctness dependency on `SO_REUSEPORT`. Ephemeral port selection occurs once. Single-Worker Server binds directly.

## 9. Readiness

Ready requires:

```text
listener bound
AND required Workers alive
AND identical RevisionId
AND required Application/extensions/resources ready
AND required Runtime Record policy available
AND no fatal startup error
```

Startup, partial rollout, development replacement, hard disk watermark, degraded configuration, and insufficient Workers are not-ready. Liveness is separate.

## 10. Signals and exit codes

```text
first termination → graceful drain
second termination → hard stop
graceful timeout → hard stop
```

CLI/Supervisor owns process signals. Unix SIGINT/SIGTERM and interactive Windows Ctrl+C are supported according to platform capability. SIGHUP reload remains deferred.

| Code | Meaning |
|---:|---|
| 0 | clean shutdown or successful check/version |
| 1 | uncategorized command failure |
| 2 | CLI usage/argument error |
| 3 | application import/discovery/type error |
| 4 | configuration/validation/freeze/extension startup error |
| 5 | listener/platform startup error |
| 6 | Worker fatal failure/restart budget exhausted |
| 7 | graceful timeout/forced hard stop |
| 8 | required Runtime Record policy unavailable |
| 70 | unexpected CLI/Supervisor defect |

## 11. Python support

```text
Implementation:  CPython
Minimum:         3.12
Required:        3.12, 3.13, 3.14
Preview:         3.15 prerelease
requires-python: >=3.12
```

No artificial upper bound. PyPy, free-threaded CPython, 32-bit Python, and other implementations are deferred.

## 12. Platform tiers

Tier 1, release blocking:

```text
64-bit maintained Linux
64-bit supported Windows
64-bit supported macOS
```

Required architecture coverage:

```text
Linux x86_64
Windows x86_64
macOS arm64
```

Linux arm64 and macOS x86_64 are Tier 2 when CI capacity exists.

## 13. Build backend and metadata

```toml
[build-system]
requires = ["hatchling>=1.26,<2"]
build-backend = "hatchling.build"
```

- one root `pyproject.toml`;
- PEP 621 `[project]` metadata;
- no initial `setup.py`, `setup.cfg`, or dynamic metadata;
- `name = "lingshu"`;
- `requires-python = ">=3.12"`;
- README metadata;
- License metadata waits for governance decision;
- runtime dependencies start empty unless separately approved.

## 14. Version and console entry point

The only manually edited version source is:

```text
[project].version
```

Runtime/CLI read installed metadata through:

```python
importlib.metadata.version("lingshu")
```

No duplicate manual `__version__`, component versions, or unapproved SCM dynamic versioning.

Console entry point:

```toml
[project.scripts]
lingshu = "lingshu.cli:main"
```

`python -m lingshu` delegates to the same integer-returning `main()`.

## 15. Artifacts

Initial artifacts:

```text
one py3-none-any wheel
one source distribution
```

Wheel excludes tests, tools, benchmarks, fuzz data, caches, local configuration, Runtime Records, credentials, secrets, and development output. Sdist includes source/metadata needed to rebuild the wheel and accepted public governance material.

## 16. Packaging verification

```text
isolated wheel + sdist build
→ metadata/inventory inspection
→ fresh virtual environment
→ non-editable wheel install
→ run outside checkout
→ import/CLI/smoke tests
→ rebuild wheel from sdist
→ compare metadata/inventory
→ separate editable developer test
→ uninstall verification
```

Repository `PYTHONPATH` injection is prohibited. CI records artifact hashes.

## 17. CI matrix

Required PR matrix:

```text
Linux   3.12, 3.13, 3.14
Windows 3.12, 3.14
macOS   3.12, 3.14
```

Preview:

```text
Linux 3.15 prerelease — visible and non-blocking until promoted
```

Release candidates include expanded artifact, listener-transfer, signal, and shutdown tests.

## 18. Required implementation tests

- Server lifecycle, freeze-before-bind, failed-start cleanup, event-loop/signal restrictions, idempotent close;
- script and `python -m` parity;
- strict target grammar and instance/factory validation;
- no parent mutable Application inheritance;
- spawn on Tier 1 systems;
- one Supervisor bind and listener transfer;
- identical RevisionId readiness;
- startup failure, restart budget, signal escalation, and exit codes;
- single-Worker reload and process replacement;
- Python implementation/version diagnostics;
- Hatchling metadata and file inventory;
- version/tag consistency;
- clean non-editable install outside checkout;
- forbidden-file exclusion;
- required matrix and visible preview.

## 19. Deferred decisions

- actual first development version and numeric defaults;
- health endpoint paths;
- SIGHUP/multi-Worker configuration rollout;
- advanced CLI and async/parameterized factories;
- public multi-Worker Supervisor API;
- PyPy, free-threaded, 32-bit, extra architectures;
- native extensions/platform wheels;
- exact OS floors;
- License/public governance;
- PyPI publication, signing, and attestation.
