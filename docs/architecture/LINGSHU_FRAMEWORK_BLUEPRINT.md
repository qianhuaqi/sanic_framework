# LingShu Framework 总体架构设计总纲（P0 Frozen）

- 设计负责人：小顾
- 产品决策人：多多
- 状态：Frozen；PR #51 合并即授权 P1
- Parent Issue：#25（由 PR #51 关闭）
- 最终决策 Issue：#49（由 PR #51 关闭）
- 规范仓库：`qianhuaqi/lingshu`
- 已接受决策：ADR-001、ADR-002、ADR-003、ADR-004、ADR-005、ADR-006、ADR-007
- Final Freeze：PR #51
- 权威 P0 Freeze Commit：PR #51 的 merge commit
- 决策状态：`docs/architecture/P0_DECISION_STATUS.md`
- Freeze Record：`docs/architecture/P0_FINAL_FREEZE.md`

> 本文件是 LingShu 唯一总体架构入口。详细合同位于已接受 ADR 和对应架构文档。PR #51 合并后，P0 正式结束，P1 按 `P1_IMPLEMENTATION_PLAN.md` 执行。任何实现不得静默重解释本总纲；修改冻结决策必须建立新 Issue 和新 ADR。

## 1. 项目定位

LingShu 是从零开发、独立实现、自主控制的 Python Web/API Framework。

LingShu 不是 Sanic、FastAPI、Flask、Django、Starlette 或其他上层 Web Framework 的包装、适配层或迁移版本，也不承担旧实现兼容义务。

LingShu 自己定义并控制：

- Application Kernel；
- HTTP Runtime 与 Native Server；
- Request、Response、Router、Middleware 与 Streaming 基础；
- 生命周期、并发、取消、清理、容量与背压；
- Extension Protocol；
- Request ID 与 Runtime Record；
- CLI、测试支持、打包和后续生态。

旧实现仅保留在：

```text
archive/legacy-sanic-20260628
```

封存提交：

```text
b869270e0ec7cbc324d17ef246e39d0873aab14f
```

旧源码、测试、依赖、Issue、PR 和 API 只作历史参考，不是新框架基线。

## 2. 最高架构原则

### 2.1 自主内核

核心运行能力由 LingShu 自行实现。Python 标准库是语言基础；任何 mandatory runtime dependency 必须单独评审。

### 2.2 机制与政策分离

Core 提供通用机制，不把认证、租户、权限、数据库、缓存、用户、订单等业务政策写入内核。

### 2.3 单向无环依赖

组件依赖必须显式、无环且可机器验证。下层不得依赖业务集成、项目代码、测试工具或根级 public facade。

### 2.4 显式生命周期

禁止通过 import 副作用注册、建连、启动任务、打开文件、绑定端口或修改进程级运行状态。

### 2.5 默认隔离与有界

Application、Worker、Connection、Request、Operation 和 Extension 按 Scope 隔离。连接、请求体、Header、队列、任务、执行器、记录和磁盘必须有上限、背压或拒绝策略。

### 2.6 Deadline、取消与清理

Deadline 是调用链共享的绝对 monotonic 预算，子调用只能继承或缩短。取消必须传播；所有退出路径必须执行确定性、有界清理。

### 2.7 安全优先

协议歧义直接拒绝；敏感数据默认不记录；不自造密码学、TLS 或证书验证；安全、正确性和可恢复性优先于未经验证的性能。

## 3. ADR-001：单仓库与并发开发

规范仓库：

```text
qianhuaqi/lingshu
```

- 一个任务对应一个 Issue、writer-prefixed branch、primary writer、独立 worktree/clone、独立环境和一个 PR；
- Issue 声明 `base_commit`、`write_scope`、依赖、冲突、集成顺序和 required checks；
- 重叠写入范围或同一公共契约不得并行；
- Provider contract 先合并，Consumer 后同步；
- 开发可并行，进入 `main` 必须串行；
- 禁止共享可写工作区、多写入者分支、直接提交 `main`、长期 `develop` 和 auto-merge；
- 最终合并权属于项目负责人。

## 4. ADR-002：运行时并发与关闭

```text
Supervisor
└─ Worker process
   └─ one event loop
      └─ Application Runtime
         ├─ infrastructure tasks
         ├─ application-owned tasks
         └─ Connection
            └─ Request
               └─ Operation / child tasks
```

- 标准库 `asyncio` 语义是正确性基线；
- 每个 Worker 一个 event loop 和 Application Runtime；
- Worker 不共享可变 Python 应用状态；
- Request 创建的任务默认归 Request Scope；
- 未登记 fire-and-forget 禁止；
- 一个 HTTP/1.1 Connection 同时执行一个 Request；
- Admission、Queue、Buffer、Executor、Dependency、Telemetry 和 Record 全部有界；
- 网络读取至 Response Write 形成完整背压链；
- Deadline 使用绝对 monotonic time；
- Blocking I/O 与 CPU 工作隔离；
- Worker restart 有预算、退避和崩溃循环保护；
- Shutdown 按停止准入、排空、取消、逆序清理、刷新记录、关闭资源和 hard stop 执行。

详细文档：

- `docs/decisions/ADR-002-runtime-concurrency-model.md`
- `docs/architecture/RUNTIME_CONCURRENCY_MODEL.md`

## 5. ADR-003：Package、源码和组件边界

```text
Repository:          qianhuaqi/lingshu
Distribution:        lingshu
Import package:      lingshu
Packaging file:      pyproject.toml
Production source:   lingshu/
src layout:          prohibited
```

初始采用一个 distribution、一个 import package、一个 version 和一个 release cadence。

目标组件：

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

依赖方向：

```text
runtime     → core
http        → runtime + core
server      → http + runtime + core
record      → core + stable runtime contracts
extensions  → core + runtime (+ documented HTTP contracts when required)
cli         → public composition surface
testing     → public/test-support surfaces
```

禁止依赖环、下层导入根 facade、生产代码依赖 `testing` 和未经批准的跨组件 private import。

`lingshu/__init__.py` 是受控 public facade，使用显式 `__all__`。Deep imports 默认 private。

详细文档：

- `docs/decisions/ADR-003-package-source-layout-and-component-boundaries.md`
- `docs/architecture/PACKAGE_AND_COMPONENT_LAYOUT.md`

## 6. ADR-004：Application Kernel 与请求管线

根级最小 public API：

```python
from lingshu import LingShu, Request, Response, HTTPException
```

Application 生命周期：

```text
CREATED → CONFIGURING → FROZEN → STARTING → RUNNING → DRAINING → STOPPING → STOPPED
```

- Route、Middleware、Exception Mapper、Extension、Config 和 Hook 只在 freeze 前注册；
- Freeze 校验完整 Revision 并原子发布 immutable Application Plan；
- Freeze 失败不发布部分状态；
- 运行中的 registries 不可变；
- 初始 Handler 是接收一个 Request 的 async callable；
- Application 与 Route Middleware 使用确定性洋葱模型；
- `call_next` 只能调用一次且受当前 Scope 约束；
- Request metadata 只读，Body 有界、背压、单消费者；
- Handler 返回值只 normalize 一次；初始支持 Response、str 和 bytes-like；
- 默认拒绝 None、tuple magic、任意 iterator/generator 和未知对象。

固定请求管线：

```text
Protocol Accept
→ Request Scope / Deadline
→ IDs / Runtime Record
→ Request / Body
→ Admission
→ Application Middleware
→ Route Match
→ Route Admission / Capability
→ Route Middleware
→ Handler
→ Response Normalization
→ Middleware Unwind
→ Exception Fallback
→ Response Prepare
→ Commit
→ Body Write
→ Record Finalize
→ Task Cleanup
→ Scope Release
```

Response：

```text
NEW → PREPARED → COMMITTED → COMPLETED/ABORTED
```

Commit 后 status/header 不可变，且不能创建第二个 Response。

详细文档：

- `docs/decisions/ADR-004-application-kernel-request-pipeline-and-public-api.md`
- `docs/architecture/APPLICATION_KERNEL_AND_REQUEST_PIPELINE.md`

## 7. ADR-005：Hardening Foundations

### 7.1 时间与标识

- RFC3339 UTC wall time 用于可读时间、Retention 和跨进程关联；
- monotonic time 用于 Deadline、Timeout、Queue Wait、Scheduling 和 Duration；
- Request/Connection/Trace/Operation/Worker/Record ID 是 typed opaque 128-bit values；
- RevisionId 是 canonical Revision 的 SHA-256；
- LingShu 永远生成 internal RequestId；inbound Request ID 仅作 untrusted correlation；
- remote TraceId 只用于 correlation，不产生授权。

### 7.2 Error 与 Configuration

Framework Error 具有 stable code、safe message、client visibility、retryability、severity、fatal scope、safe details 和 internal cause。Client 使用 `application/problem+json`，默认不暴露 traceback、路径、配置、环境、凭据、Body、SQL 或内部拓扑。Cancellation 是 control flow。

```text
built-in defaults
< configuration file
< environment variables
< CLI overrides
< explicit programmatic overrides
```

Config 经过 Schema/version 校验；Secret/Protected value 在所有输出路径隐藏；运行时只接收 immutable typed Snapshot。

### 7.3 Serialization

```text
text/plain; charset=utf-8
application/octet-stream
application/json; charset=utf-8
application/problem+json; charset=utf-8
```

JSON 使用 UTF-8、有限，拒绝 duplicate key、NaN/Infinity 和未知对象。Datetime、bytes、Decimal 和 domain types 使用显式 Serializer。415 与 406 语义明确，禁止 Content Sniffing。

### 7.4 Runtime Record 与 Telemetry

每个业务 Request 在 Handler 前预留 RecordId、Queue Capacity、Record/Event Budget、Durability 和 Storage Health。默认 `required`，无法保证记录时在业务执行前拒绝。

默认 local writer：versioned append-only Event Envelope → bounded queue → UTF-8 JSON Lines segments → atomic manifest → retention/recovery。

Durability：`buffered`、`flush`、`fsync`。Event、Record、Queue、Segment、Disk、Retention、Cleanup、Flush、Shutdown 和 Recovery 全部有预算。

Disk：normal → soft → hard → critical。Hard 状态 Not Ready 并拒绝 required Request；Critical 只保留最小故障、健康、关闭和数据丢失诊断。Active Segment 不被 Retention 删除。

Logs、Traces、Diagnostics 和 Records 共享字段与 `public/internal/sensitive/secret` 分类。高基数 IDs、Raw Path 和 Raw Error Message 默认不作 Metric Label。

详细文档：

- `docs/decisions/ADR-005-hardening-foundations.md`
- `docs/architecture/HARDENING_FOUNDATIONS.md`
- `docs/architecture/P0_HARDENING_CHECKLIST.md`

## 8. ADR-006：Executable、CLI 与 Build

所有权：

```text
Application → definitions/revision/lifecycle plan
Server      → one Worker loop/runtime/listener/protocol/readiness/drain
Supervisor  → spawn/listener transfer/readiness/restart/signals/exit
CLI         → arguments/target/overrides/Supervisor/diagnostics
```

Application 不负责进程监督；Kernel 不依赖 Server。

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

Target 只接受 `module:attribute`；禁止文件路径、表达式、调用、索引、dotted traversal、implicit scanning 和 app guessing。

Multi-Worker 设计使用 cross-platform `spawn`；每个 Worker 独立 import/freeze；Supervisor bind listener 一次并显式传递；不依赖 fork 或 `SO_REUSEPORT`。P1 不实现 multi-Worker。

Ready 要求 listener bound、required Workers ready、RevisionId 一致、required resources/extensions ready、Runtime Record required policy available。

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

Packaging Gate 必须在 checkout 外验证 non-editable install、inventory、sdist rebuild、editable experience 和 uninstall。

详细文档：

- `docs/decisions/ADR-006-executable-cli-support-and-build-baseline.md`
- `docs/architecture/EXECUTABLE_AND_BUILD_BASELINE.md`

## 9. ADR-007：Governance、Compatibility 与 Release

```text
License:       Apache-2.0
Contribution:  DCO 1.1 + Signed-off-by
CLA:           初期不使用
Conduct:       Contributor Covenant 2.1 adaptation
SemVer:        2.0.0
First P1:      0.1.0.dev0
Long-lived:    main only
```

Repository 提供：

```text
LICENSE
NOTICE
DCO
CONTRIBUTING.md
SECURITY.md
CODE_OF_CONDUCT.md
CHANGELOG.md
```

- first public release 前启用 private vulnerability reporting；
- 未修复漏洞不得公开；
- 0.x 默认只支持 latest minor；
- 1.x+ 支持 current major latest minor，新 major 后 previous major 通常保留 180 天 critical/high fixes；
- 0.x patch 在同 minor line 内保持 compatibility；breaking change 必须 minor bump、migration guidance、changelog 和 contract tests；
- 1.x+ breaking change 只在 Major；normal removal 需要 two released minors AND 180 days；
- Release 由 annotated tag 驱动 protected CI build；
- released tags/artifacts immutable；defective release 使用 yank/supersede；
- public publication 使用 short-lived trusted identity where available，并保留 artifact hashes 与 provenance/attestation。

详细文档：

- `docs/decisions/ADR-007-public-governance-release-and-p0-freeze.md`
- `docs/governance/RELEASE_AND_COMPATIBILITY_POLICY.md`

## 10. P1：Single-Worker Minimum Vertical Slice

Planned version：

```text
0.1.0.dev0
```

Issue graph：

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

详细依赖、write scopes、parallel waves 和 acceptance matrix：

- `docs/development/P1_IMPLEMENTATION_PLAN.md`

## 11. Freeze 与授权

PR #50 建立了 Freeze Candidate，但没有授权生产开发。

项目负责人合并 PR #51 后：

1. ADR-001 至 ADR-007 全部 Accepted；
2. 本 Blueprint 正式 Frozen；
3. PR #51 merge commit 成为权威 final P0 commit；
4. Issue #49 与 Parent Issue #25 由 close directives 完成；
5. P1 正式 Authorized；
6. 可以创建 P1-00 至 P1-10 Issues，但必须按 provider-first dependency 顺序；
7. P1-00 可以在其 write scope 内创建 `pyproject.toml`、初始 `lingshu/`、`tests/`、tooling 和 CI Workflow；
8. 其他 P1 Issue 不得在其 provider 合并前开始；
9. Final merge authority 与 no-auto-merge 继续生效。

Final Freeze 审计记录：

- `docs/architecture/P0_FINAL_FREEZE.md`

## 12. P1 仍未授权的能力

- public PyPI production publication；
- production-ready 声明；
- multi-Worker Supervisor implementation；
- development/production reload implementation；
- advanced routing、streaming、multipart、uploads 和 compression；
- sync Handler adaptation 与 dependency injection；
- official Auth/Tenant/RBAC/SQL/Redis/Cache/OpenAPI/Scheduler/Storage/Observability integrations；
- HTTP/2、HTTP/3、WebSocket、ASGI/WSGI；
- extra runtimes/platforms 与 native extensions；
- 修改冻结架构而没有新 Issue 和 ADR。
