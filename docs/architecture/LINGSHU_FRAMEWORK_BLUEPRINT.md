# LingShu Framework 总体架构设计总纲（P0-RC9 Freeze Candidate）

- 设计负责人：小顾
- 产品决策人：多多
- 状态：P0 Final Freeze Candidate，尚未授权 P1
- Parent Issue：#25
- 当前决策 Issue：#49
- 规范仓库：`qianhuaqi/lingshu`
- 已接受决策：ADR-001、ADR-002、ADR-003、ADR-004、ADR-005、ADR-006
- 当前提案：ADR-007
- 决策状态：`docs/architecture/P0_DECISION_STATUS.md`

> 本文件是 LingShu 唯一总体架构入口。详细合同位于已接受 ADR 和对应架构文档。P0-D7 决策 PR 合并后仍需独立 Final Freeze PR；此前不得创建生产源码、`pyproject.toml`、测试骨架、CI Workflow 或可执行 P1 Issue。

## 1. 定位与最高原则

LingShu 是从零开发、独立实现、自主控制的 Python Web/API Framework，不依赖 Sanic、FastAPI、Flask、Django、Starlette 或其他上层 Web Framework，也不承担旧实现兼容义务。

旧实现只保留在：

```text
archive/legacy-sanic-20260628
b869270e0ec7cbc324d17ef246e39d0873aab14f
```

最高原则：自主内核、机制与政策分离、单向无环依赖、显式生命周期、Scope 隔离、所有资源有界、绝对 monotonic Deadline、取消传播、确定性清理、安全优先。

## 2. ADR-001：仓库与并发开发

- 单一规范仓库 `qianhuaqi/lingshu`；
- 一个任务对应一个 Issue、writer branch、primary writer、独立 worktree/environment 和一个 PR；
- Issue 声明 base commit、write scope、依赖、冲突、集成顺序和检查；
- Provider 先合并，Consumer 后同步；
- 开发可并行，`main` 集成串行；
- 禁止共享 writable workspace、多写入者分支、直接提交 main、长期 develop 和 auto-merge；
- 最终合并权属于项目负责人。

## 3. ADR-002：运行时并发

```text
Supervisor
└─ Worker process
   └─ one event loop
      └─ Application Runtime
         └─ Connection → Request → Operation/tasks
```

- 标准库 `asyncio` 语义是正确性基线；
- Worker 不共享可变 Python 应用状态；
- Request 子任务默认归 Request Scope，未登记 fire-and-forget 禁止；
- 一个 HTTP/1.1 Connection 同时执行一个 Request；
- Admission、Queue、Buffer、Executor、Dependency、Telemetry、Record 全部有界；
- 网络至 Response Write 形成完整背压链；
- Deadline 使用绝对 monotonic time；
- Blocking I/O/CPU 工作隔离；
- Worker restart 有预算和退避；
- Shutdown 按停止准入、排空、取消、逆序清理、刷新记录、关闭资源和 hard stop 执行。

详细文档：`ADR-002` 与 `docs/architecture/RUNTIME_CONCURRENCY_MODEL.md`。

## 4. ADR-003：Package 与组件边界

```text
Distribution:        lingshu
Import package:      lingshu
Production source:   lingshu/
Packaging file:      pyproject.toml
src layout:          prohibited
```

初始一个 distribution、一个 version、一个 release cadence。

```text
lingshu.core
lingshu.runtime
lingshu.http
lingshu.server
lingshu.record
lingshu.extensions
lingshu.cli
lingshu.testing
```

依赖方向：runtime→core；http→runtime+core；server→http+runtime+core；record→core+stable runtime contracts；extensions→core+runtime；cli→public composition；testing→public/test-support。

Root `lingshu/__init__.py` 是显式 `__all__` public facade；deep imports 默认 private；生产代码不得依赖 testing。

详细文档：`ADR-003` 与 `docs/architecture/PACKAGE_AND_COMPONENT_LAYOUT.md`。

## 5. ADR-004：Application Kernel 与请求管线

Root public API：

```python
from lingshu import LingShu, Request, Response, HTTPException
```

Application 生命周期：

```text
CREATED → CONFIGURING → FROZEN → STARTING → RUNNING → DRAINING → STOPPING → STOPPED
```

- 注册只在 freeze 前；
- freeze 原子发布 immutable Application Plan，失败不发布部分状态；
- 初始 Handler 是接收一个 Request 的 async callable；
- Application/Route Middleware 使用确定性洋葱顺序；
- `call_next` 单次且 Scope-bound；
- Request metadata 只读，Body 有界、背压、单消费者；
- Handler 返回只 normalize 一次；初始支持 Response、str、bytes-like；
- 默认拒绝 None、tuple magic、任意 iterator/generator 和未知对象。

请求管线：Protocol Accept → Scope/Deadline → IDs/Record → Request/Body → Admission → Middleware → Route → Handler → Normalize → Exception Fallback → Prepare → Commit → Write → Record Finalize → Cleanup。

Response：

```text
NEW → PREPARED → COMMITTED → COMPLETED/ABORTED
```

Commit 后 status/header 不可变且不能创建第二响应。

详细文档：`ADR-004` 与 `docs/architecture/APPLICATION_KERNEL_AND_REQUEST_PIPELINE.md`。

## 6. ADR-005：Hardening Foundations

- RFC3339 UTC wall time 用于展示、Retention、跨进程关联；monotonic time 用于 Deadline、Timeout、Queue Wait 和 Duration；
- Request/Connection/Trace/Operation/Worker/Record ID 是 typed opaque 128-bit values；RevisionId 是 canonical Revision SHA-256；
- Framework Error 具有 stable code、safe message、retryability、severity、fatal scope 和 internal cause；client 使用 `application/problem+json`；
- Config precedence：defaults < file < environment < CLI < programmatic override；运行时使用 immutable typed Snapshot；
- JSON 仅 UTF-8、有限、拒绝 duplicate keys、NaN/Infinity 和未知对象；415/406 语义明确；
- 每个业务 Request 在 Handler 前预留 required Runtime Record；默认 local writer 为 bounded queue + append-only JSON Lines segments + atomic manifest + retention/recovery；
- Disk 状态 normal→soft→hard→critical；Hard 状态 Not Ready；
- Logs/Traces/Diagnostics/Records 共享字段和 `public/internal/sensitive/secret` 分类；高基数 ID 不作 Metric Label。

详细文档：`ADR-005`、`HARDENING_FOUNDATIONS.md`、`P0_HARDENING_CHECKLIST.md`。

## 7. ADR-006：Executable、CLI 与 Build

所有权：

```text
Application → definitions/revision/lifecycle plan
Server      → one Worker loop/runtime/listener/protocol/readiness/drain
Supervisor  → spawn/listener transfer/readiness/restart/signals/exit
CLI         → arguments/target/overrides/Supervisor/diagnostics
```

Public single-Worker API：

```python
from lingshu.server import Server, ServerConfig, serve
```

CLI：

```text
lingshu run module:app
lingshu run module:create_app --factory
lingshu check module:app
lingshu version
python -m lingshu ...
```

Target 只接受 `module:attribute`；禁止文件路径、表达式、调用、索引、dotted traversal、implicit scanning。

Multi-Worker 语义使用 cross-platform `spawn`；每个 Worker 独立 import/freeze；Supervisor bind listener 一次并显式传递；不依赖 fork 或 `SO_REUSEPORT`；Ready 要求 RevisionId 一致和 required resources/Record policy ready。

第一终止信号 Graceful Drain，第二信号或 timeout Hard Stop。Exit codes：0、1、2、3、4、5、6、7、8、70。

```text
CPython minimum: 3.12
Required:        3.12, 3.13, 3.14
Preview:         3.15 prerelease
Tier 1:          64-bit Linux, Windows, macOS
Build backend:   Hatchling
Version source:  static [project].version
Console script:  lingshu = "lingshu.cli:main"
Artifacts:       py3-none-any wheel + sdist
```

详细文档：`ADR-006` 与 `docs/architecture/EXECUTABLE_AND_BUILD_BASELINE.md`。

## 8. ADR-007：治理、Release 与 Final Freeze（Proposed）

本节在 P0-D7 决策 PR 和后续 Final Freeze PR 均合并后才成为 Confirmed。

### 8.1 Governance

```text
License:      Apache-2.0
Contribution: DCO 1.1 + Signed-off-by
CLA:          初期不使用
Conduct:      Contributor Covenant 2.1 adaptation
```

Repository 提供 `LICENSE`、`NOTICE`、`DCO`、`CONTRIBUTING.md`、`SECURITY.md`、`CODE_OF_CONDUCT.md` 和 `CHANGELOG.md`。

Security：first public release 前启用 private vulnerability reporting；未修复漏洞不得公开；0.x 默认只支持 latest minor；1.x+ current major latest minor，new major 后 previous major 通常 180 天 critical/high fixes。

### 8.2 SemVer 与兼容

```text
SemVer:           2.0.0
First P1 version: 0.1.0.dev0
Tag:              vX.Y.Z / prerelease
Long-lived branch: main only
```

0.x patch 在同 minor line 内保持 compatibility；breaking change 必须 minor bump、migration guidance、changelog 和 contract tests，where practical 至少提前一个 minor deprecate。

1.x+ breaking change 只在 Major；normal removal 需要 two released minors AND 180 days deprecation。Security/Corruption/Protocol Emergency 可用 narrow documented exception。

Released versions/tags/artifacts immutable。Release 由 annotated tag 驱动 protected CI build；defective release 使用 yank/supersede，不覆盖。Public publication 使用 short-lived trusted identity where available，并保留 artifact hashes 与 provenance/attestation。

详细政策：`docs/governance/RELEASE_AND_COMPATIBILITY_POLICY.md`。

### 8.3 P1：Single-Worker Minimum Vertical Slice

```text
P1-00 package/tooling/CI
P1-01 core primitives
P1-02 static configuration
P1-03 runtime Scope/Deadline/cancellation/admission
P1-04 HTTP model/body/response
P1-05 Router/Middleware
P1-06 Application Kernel/freeze/lifecycle
P1-07 minimum Runtime Record
P1-08 native single-Worker HTTP/1.1 Server
P1-09 CLI version/check/run --workers 1
P1-10 integration/security/packaging/docs
```

P1 不包含 multi-Worker Supervisor、reload、advanced streaming/body formats、official extensions、HTTP/2/3、WebSocket、ASGI/WSGI 或 public PyPI release。

详细 graph/write scopes/acceptance：`docs/development/P1_IMPLEMENTATION_PLAN.md`。

### 8.4 Final Freeze Gate

P0-D7 decision PR merge 只形成 Freeze Candidate，不授权生产代码。

随后 Final Freeze PR 必须：

1. ADR-007 标记 Accepted；
2. 本 Blueprint 标记 Frozen；
3. 核验 ADR-001 至 ADR-007 和治理/状态/P1 Plan 一致；
4. 关闭 Issue #49 与 Parent Issue #25；
5. 记录 final P0 commit；
6. CURRENT_PHASE 切换为 P1 Authorized；
7. 明确允许创建 `pyproject.toml`、`lingshu/`、`tests/`、CI Workflow 与 P1 Issues；
8. 由项目负责人 merge，作为 explicit P1 authorization。

## 9. Final Freeze 前禁止

- 创建生产 package、tests、examples、`pyproject.toml` 或 CI Workflow；
- 引入实际 runtime/build dependency；
- 实现 Framework components；
- 打开 executable P1 implementation Issues；
- 发布 artifacts；
- 共享 writable workspace/branch；
- auto-merge。

## 10. P1 后继续延后的能力

Multi-Worker Supervisor implementation、development reload、production config rollout、advanced routing/streaming/multipart/uploads/compression、sync Handler adaptation、dependency injection、official extensions、HTTP/2/3、WebSocket、ASGI/WSGI、extra runtimes/platforms、native extensions、public release date、manual signing、trademark 与 LTS governance。

## 11. P0 退出条件

1. ADR-001 至 ADR-007 全部 Accepted；
2. 本 Blueprint 标记 Frozen；
3. Hardening Verification 为 Verified；
4. 不存在冲突总体设计；
5. Package、Kernel、Runtime、HTTP、Server、Record、CLI、Build、Security、Release boundaries 全部确认；
6. Governance files 一致；
7. P1 scope、Issue graph、write scopes、acceptance matrix 可执行；
8. Parent Issue #25 完成；
9. 多多 merge Final Freeze PR 并明确授权 P1。

在 Final Freeze 之前，P1 保持 blocked。
