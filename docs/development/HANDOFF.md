# Development Handoff

Updated at: 2026-06-28
Project: LingShu Framework
Canonical repository: `qianhuaqi/lingshu`
Phase: P0 - Architecture Decision Review and Blueprint Consolidation
Parent Issue: #25
Active decision Issue: none
Active decision branch: none
Baseline: latest accepted `main`
Status: P0-D6 accepted; awaiting final governance/freeze decision

## Accepted decisions

- P0-D1: repository and concurrent-development governance — ADR-001 / PR #32.
- P0-D2: runtime concurrency — ADR-002 / PR #35.
- P0-D3: package and component layout — ADR-003 / PR #38.
- P0-D4: Application Kernel and request pipeline — ADR-004 / PR #41.
- P0-D5: Hardening Foundations — ADR-005 / PR #44.
- P0-D6: executable, CLI, support matrix, and build baseline — ADR-006 / PR #47.

P0-D6 merge commit:

```text
5f89572398cee509b9571ee1fe8c20bd2f71dfeb
```

## Confirmed execution ownership

```text
Application → routes/middleware/extensions/config revision/lifecycle plan
Server      → one Worker loop/runtime/listener/protocol/readiness/drain
Supervisor  → processes/listener transfer/readiness/restarts/signals/exit
CLI         → arguments/target/overrides/Supervisor/diagnostics
```

Application does not bind sockets or supervise processes. Kernel does not import Server.

## Confirmed public Server API

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

Server/serve are single-Worker. Multi-Worker Supervisor remains CLI/internal. Root exports stay limited to `LingShu`, `Request`, `Response`, and `HTTPException`.

## Confirmed CLI and discovery

```text
lingshu run myapp.main:app
lingshu run myapp:create_app --factory
lingshu check myapp.main:app
lingshu version
python -m lingshu ...
```

Target grammar is strict `module:attribute`. Factory is synchronous, zero-argument, and returns LingShu. Arbitrary expressions, calls, file paths, implicit scanning, and dotted attribute traversal are prohibited.

## Confirmed process model

```text
CLI
└─ Supervisor
   ├─ bind listener once
   ├─ spawn Worker → import/freeze/start
   ├─ transfer listener explicitly
   └─ ready only when required Workers share one RevisionId
```

Correctness does not depend on fork inheritance or `SO_REUSEPORT`. Development reload is single-Worker process replacement, not in-process reload or production configuration revision reload.

## Confirmed readiness, signals, and exit

Ready requires listener bind, required Worker count, identical RevisionId, ready required resources/extensions, available required Runtime Record policy, and no startup fatal condition.

First termination requests graceful drain. Second termination or graceful timeout requests hard stop.

```text
0  clean/success
1  generic failure
2  CLI usage
3  app import/discovery/type
4  config/validation/freeze/extension startup
5  listener/platform startup
6  Worker fatal/restart budget
7  graceful timeout/hard stop
8  required Runtime Record unavailable
70 internal CLI/Supervisor defect
```

## Confirmed support/build baseline

```text
CPython minimum: 3.12
Required:        3.12, 3.13, 3.14
Preview:         3.15 prerelease
Tier 1:          64-bit Linux, Windows, macOS
Build backend:   Hatchling
Metadata:        PEP 621
Version source:  static [project].version
Console script:  lingshu = "lingshu.cli:main"
Artifacts:       py3-none-any wheel + sdist
```

No initial `setup.py`, `setup.cfg`, dynamic metadata, duplicate `__version__`, PyPy/free-threaded/32-bit support claim, or native wheel.

## Confirmed packaging gate

```text
isolated build
→ metadata/inventory inspection
→ fresh venv
→ non-editable wheel install
→ run outside checkout
→ import/CLI/smoke
→ rebuild from sdist
→ compare metadata/inventory
→ separate editable test
→ uninstall verification
```

Required CI:

```text
Linux   3.12, 3.13, 3.14
Windows 3.12, 3.14
macOS   3.12, 3.14
Preview Linux 3.15 prerelease
```

## Deferred

- actual first development version;
- License and public governance;
- numeric defaults and health endpoint paths;
- SIGHUP/multi-Worker configuration rollout;
- advanced CLI/factory forms and public Supervisor API;
- extra runtimes/platforms and native extensions;
- PyPI publication, signing, and attestations.

## Next decision

P0-D7 should finalize:

- License and required governance files;
- contribution and code-of-conduct policy;
- security disclosure and supported-version policy;
- changelog/release-note/compatibility/deprecation rules;
- tags, branches, version bumps, publication and rollback;
- first development version and P1 milestone mapping;
- executable P1 Issue graph and acceptance matrix;
- final Blueprint audit, P0 freeze, and explicit P1 authorization.

## Verification

P0-D6 added architecture documentation only. No production source, `pyproject.toml`, workflow, dependency, implementation, or publishing configuration was created.

P1 remains blocked.
