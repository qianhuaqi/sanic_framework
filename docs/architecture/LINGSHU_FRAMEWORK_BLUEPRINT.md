# LingShu Framework 总体架构设计总纲（P0-RC7）

- 设计负责人：小顾
- 产品决策人：多多
- 状态：P0 候选总纲，尚未最终冻结
- GitHub Issue：#25
- 当前决策 Issue：#46
- 规范仓库：`qianhuaqi/lingshu`
- 已接受决策：ADR-001、ADR-002、ADR-003、ADR-004、ADR-005
- 当前提案：ADR-006
- 决策状态：`docs/architecture/P0_DECISION_STATUS.md`

> 本文件是 LingShu 唯一总体架构入口。只有 Confirmed 内容可以成为实施依据。P0-D6 当前仍是 Proposed；在决策 PR 合并前不得创建生产源码、`pyproject.toml`、CI Workflow 或运行依赖。

## 1. 项目定位

LingShu 是从零开发、独立实现、自主控制的 Python Web/API Framework。

LingShu 不是 Sanic、FastAPI、Flask、Django、Starlette 或其他上层 Web Framework 的包装、适配层或迁移版本，也不承担旧实现兼容义务。

LingShu 自己定义和控制 Application Kernel、HTTP Runtime、Native Server、Request/Response/Router/Middleware/Streaming、并发/取消/背压/清理、Extension Protocol、Runtime Record、CLI 和测试支持。

旧实现只保留在：

```text
archive/legacy-sanic-20260628
```

封存提交：

```text
b869270e0ec7cbc324d17ef246e39d0873aab14f
```

旧源码、测试、依赖、Issue、PR 和 API 只作历史参考，不是新框架基线。

## 2. 最高原则

- **自主内核**：核心运行能力由 LingShu 自行实现；核心第三方依赖逐项评审。
- **机制与政策分离**：认证、租户、权限、数据库、缓存和业务模型不写进 Core。
- **单向无环依赖**：依赖可机器验证；下层不依赖业务集成、项目代码、测试工具或根 facade。
- **显式生命周期**：禁止 import 副作用启动任务、建连、打开文件或修改运行状态。
- **默认隔离与有界**：Scope 隔离；连接、请求、队列、任务、记录和磁盘必须有界。
- **Deadline、取消与清理**：绝对 monotonic Deadline；取消传播；所有退出路径有界清理。
- **安全优先**：协议歧义拒绝，敏感数据默认不记录，不自造密码学或证书验证。

## 3. ADR-001：单仓库与开发并发（Confirmed）

规范仓库：

```text
qianhuaqi/lingshu
```

- 一个任务对应一个 Issue、一个 writer-prefixed branch、一个主写入者和一个 PR；
- 并行开发使用独立 worktree/clone、环境、缓存和端口；
- Issue 声明 write scope、依赖和集成顺序；
- 重叠路径或同一公共契约禁止并行；
- 公共契约先合并；
- 开发可并行，进入 `main` 串行；
- 最终合并权属于项目负责人。

## 4. ADR-002：运行时并发（Confirmed）

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

确认：

- 标准库 `asyncio` 语义是正确性基线；
- Worker 不共享可变 Python 应用状态；
- 请求子任务默认归 Request Scope；
- 未登记 fire-and-forget 禁止；
- 一个 HTTP/1.1 连接同一时刻执行一个请求；
- Admission、Queue、Buffer、Executor、Dependency、Telemetry、Record 全部有界；
- 网络到响应形成完整背压链；
- Deadline 是绝对 monotonic time；
- Blocking I/O 和 CPU 工作隔离；
- Worker 重启有预算和退避；
- Shutdown 按停止准入、排空、取消、逆序清理、刷新记录、关闭资源、hard stop 执行。

详细文档：

- `docs/decisions/ADR-002-runtime-concurrency-model.md`
- `docs/architecture/RUNTIME_CONCURRENCY_MODEL.md`

## 5. ADR-003：源码、包和组件边界（Confirmed）

```text
Repository:          qianhuaqi/lingshu
Distribution:        lingshu
Import package:      lingshu
Packaging file:      pyproject.toml
Production source:   lingshu/
src layout:          prohibited
```

初始采用一个 distribution、一个 import package、一个根级 `pyproject.toml`、一个版本和一个发布节奏。

组件：

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

依赖：

```text
runtime     → core
http        → runtime + core
server      → http + runtime + core
record      → core + stable runtime contracts
extensions  → core + runtime (+ documented HTTP contracts when required)
cli         → public composition surface
testing     → public/test-support surfaces
```

`lingshu/__init__.py` 是受控 facade，显式 `__all__`；深层 import 默认私有。生产代码不得依赖 testing。打包验收必须在仓库外对非 editable wheel 执行。

详细文档：

- `docs/decisions/ADR-003-package-source-layout-and-component-boundaries.md`
- `docs/architecture/PACKAGE_AND_COMPONENT_LAYOUT.md`

## 6. ADR-004：Application Kernel 与请求管线（Confirmed）

根级最小公开 API：

```python
from lingshu import LingShu, Request, Response, HTTPException
```

Application 生命周期：

```text
CREATED → CONFIGURING → FROZEN → STARTING → RUNNING
                                      ↓          ↓
                                   STOPPING ← DRAINING
                                      ↓
                                   STOPPED
```

- Route、Middleware、Exception Mapper、Extension、配置和 Hook 只在 freeze 前注册；
- freeze 原子发布完整不可变 Application Plan；失败无部分状态；
- 初始 Handler 是接收一个 Request 的 async callable；
- Middleware 是 Application/Route 两层确定性洋葱模型；
- `call_next` 单次且 Scope-bound；
- Request metadata 只读，Body 有界、背压、单消费者；
- Handler 返回只规范化一次；初始支持 Response、str、bytes-like；
- 默认拒绝 None、tuple magic、任意 iterator/generator 和未知对象。

请求管线：

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
→ Body/Stream Write
→ Record Finalize
→ Task Cleanup
→ Scope Release
```

Response：

```text
NEW → PREPARED → COMMITTED → COMPLETED
                  ↘          ↘
                   ABORTED ← ABORTED
```

Commit 后 status/header 不可变且不能创建第二响应。

详细文档：

- `docs/decisions/ADR-004-application-kernel-request-pipeline-and-public-api.md`
- `docs/architecture/APPLICATION_KERNEL_AND_REQUEST_PIPELINE.md`

## 7. ADR-005：Hardening Foundations（Confirmed）

### 时间与 ID

- RFC3339 UTC wall time 用于展示、Retention 和跨进程关联；
- monotonic time 用于 Deadline、Timeout、Queue Wait、Scheduling、Duration；
- Request/Connection/Trace/Operation/Worker/Record ID 是 typed opaque 128-bit value；
- RevisionId 是规范 Revision 的 SHA-256；
- LingShu 总是生成内部 RequestId；外部 Request ID 只是不可信关联；
- remote TraceId 只用于 correlation。

### Error

Framework Error 具有 stable code、safe message、client visibility、retryability、severity、fatal scope、safe details 和内部 cause。Client 使用 `application/problem+json`。默认不暴露 Traceback、路径、配置、环境信息、凭据、Body、SQL 或内部拓扑。Cancellation 是控制流。

### Configuration

```text
built-in defaults
< configuration file
< environment variables
< CLI overrides
< explicit programmatic overrides
```

配置 Schema/version 严格校验；Protected value 统一隐藏；运行时只接收 immutable typed Snapshot。

Reload：

```text
load → normalize → validate → resolve protected values → prepare
→ compile/freeze Revision → atomic publish → drain old → cleanup old
```

Publish 前失败保持旧 Revision；无法安全回滚则进入明确 degraded/not-ready。

### Serialization

Baseline：

```text
text/plain; charset=utf-8
application/octet-stream
application/json; charset=utf-8
application/problem+json; charset=utf-8
```

JSON UTF-8、有限、拒绝 duplicate key、NaN/Infinity 和未知对象；datetime/bytes/Decimal/domain type 使用显式 Serializer。415 表示不支持请求类型，406 表示没有可接受响应，禁止 Content Sniffing。

### Runtime Record

每个业务请求在 Handler 前预留 RecordId、Queue Capacity、Record/Event Budget、Durability 和 Storage Health。默认 `required`，无法保证记录时在业务执行前拒绝。

默认本地 Writer：versioned append-only Event Envelope → bounded queue → UTF-8 JSON Lines segments → atomic manifest → retention/recovery。

Durability：`buffered`、`flush`、`fsync`。Event、Record、Queue、Segment、Disk、Retention、Cleanup、Flush、Shutdown 和 Recovery 全部有预算。

Disk：normal → soft → hard → critical。Hard 状态 Not Ready 并拒绝 required 请求；Critical 仅保留最小故障/健康/关闭诊断。Active Segment 不被 Retention 删除。

### Telemetry

Logs、Traces、Diagnostics 和 Records 共享字段与 `public/internal/sensitive/secret` 分类。Request/Record/Trace/Operation/Connection ID、Raw Path、Raw Error Message、User/Tenant ID 默认禁止作为 Metric Label。

详细文档：

- `docs/decisions/ADR-005-hardening-foundations.md`
- `docs/architecture/HARDENING_FOUNDATIONS.md`
- `docs/architecture/P0_HARDENING_CHECKLIST.md`

## 8. ADR-006：Executable、CLI 与 Build Baseline（Proposed）

本节只有在 P0-D6 PR 合并后才成为 Confirmed。

### 8.1 所有权

```text
Application  → routes/middleware/extensions/config revision/lifecycle plan
Server       → one Worker loop/runtime/listener/protocol/drain
Supervisor   → spawn/listener transfer/readiness/restart/signals/exit
CLI          → arguments/target/config override/Supervisor/diagnostics
```

Application 不负责进程监督；Kernel 不依赖 Server。

### 8.2 公共单 Worker Server API

文档化公共子包：

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

`Server`/`serve` 只支持单 Worker；多 Worker Supervisor 初期保持 CLI/internal。Root API 不增加 Server 名称。`serve()` 拥有 event loop 和主线程信号，不能在已运行 loop 中调用。

### 8.3 CLI 与 Target

```text
lingshu run TARGET
lingshu check TARGET
lingshu version
python -m lingshu ...
```

Target：

```text
module:attribute
```

```text
myapp.main:app
myapp:create_app --factory
```

禁止文件路径、表达式、调用语法、索引、隐式扫描和 dotted attribute traversal。普通模式必须得到 LingShu 实例；Factory 是同步零参数 callable 并返回 LingShu。

### 8.4 Profile 与 Development Reload

```text
production
development
test
```

`run` 默认 production；`--reload` 显式选择 development。

Development Reload 使用一个 Watcher Parent + 一个 Child Worker 的进程替换模型；禁止 in-process module reload，禁止与多 Worker 同时使用，也不等同于 ADR-005 生产配置 Revision Reload。

### 8.5 Multi-Worker

- Linux、Windows、macOS 统一以 `spawn` 语义为基线；
- Supervisor 不依赖 parent-imported mutable Application；
- 每个 Worker 独立 import、build/freeze Application，启动一个 loop/runtime；
- required Workers 必须报告相同 RevisionId；
- deterministic import/config/freeze failure 不进入 restart loop；
- unexpected runtime exit 使用 ADR-002 restart budget。

### 8.6 Listener、Readiness 与 Signal

Supervisor 只绑定一次 listener，并通过平台安全机制显式传递/复制到 Worker；不依赖 `SO_REUSEPORT`，Worker 不竞争 bind。

Ready 必须满足 listener bound、required Workers ready、RevisionId 一致、required extension/resources ready、Runtime Record required policy available。

第一终止信号进入 Graceful Drain；第二信号或 Graceful Timeout 进入 Hard Stop。CLI/Supervisor 拥有进程信号。SIGHUP Reload 延后。

Exit Codes：

```text
0 clean/success
1 generic failure
2 CLI usage
3 app import/discovery/type
4 config/freeze/extension startup
5 listener/platform startup
6 Worker fatal/restart budget
7 graceful timeout/hard stop
8 required Runtime Record unavailable
70 internal CLI/Supervisor defect
```

### 8.7 Python 与平台

```text
Implementation: CPython
Minimum:        3.12
Required:       3.12, 3.13, 3.14
Preview:        3.15 prerelease
requires-python: >=3.12
```

不设置人为上限。PyPy、free-threaded CPython、32-bit 和其他解释器延后。

Tier 1：维护中的 64-bit Linux、支持期内 64-bit Windows、支持期内 64-bit macOS。Required architecture：Linux x86_64、Windows x86_64、macOS arm64。Linux arm64 和 macOS x86_64 在 CI 容量可用时作为 Tier 2。

### 8.8 Build 与 Version

Build Backend：

```toml
[build-system]
requires = ["hatchling>=1.26,<2"]
build-backend = "hatchling.build"
```

使用根级 PEP 621 `[project]`；初始不创建 `setup.py`/`setup.cfg`；初始不使用 dynamic metadata。

唯一手工 Version Source：

```text
[project].version
```

运行时和 CLI 使用：

```python
importlib.metadata.version("lingshu")
```

禁止重复手工 `__version__`、组件独立版本和未决策的 SCM dynamic version。

Console：

```toml
[project.scripts]
lingshu = "lingshu.cli:main"
```

### 8.9 Artifact 与 CI

初始产物：

```text
lingshu-<version>-py3-none-any.whl
lingshu-<version>.tar.gz
```

Wheel 不包含 tests、tools、benchmarks、fuzz、cache、local config、Runtime Record、credential 或 secret。

Packaging Gate：isolated build → inventory/metadata → clean venv → non-editable install → checkout 外 import/CLI/smoke → sdist rebuild → metadata/inventory compare → editable developer test → uninstall verification。

Required PR Matrix：

```text
Linux   3.12, 3.13, 3.14
Windows 3.12, 3.14
macOS   3.12, 3.14
```

Preview：Linux CPython 3.15 prerelease，结果可见但非阻断，直到通过完整 Gate 后提升为 Required。

详细提案：

- `docs/decisions/ADR-006-executable-cli-support-and-build-baseline.md`
- `docs/architecture/EXECUTABLE_AND_BUILD_BASELINE.md`

## 9. 当前禁止事项

P0 最终冻结前禁止：

- 创建生产 `lingshu/`、`tests/`、`pyproject.toml` 或 CI Workflow；
- 创建 `src/lingshu/` 或初始 `packages/`；
- 引入运行时或构建依赖到实际项目；
- 实现 Kernel、Runtime、HTTP、Server、Supervisor、CLI、Record、Config、Serializer 或 Extension；
- 发布安装包；
- 多个开发者共享同一可写目录/分支；
- 并行修改重叠路径或同一公共契约；
- 启动 P1。

## 10. P0-D6 延后

- 实际第一开发版本；
- numeric defaults 和 health endpoint path；
- SIGHUP 与 multi-Worker config rollout transport；
- advanced CLI、async/parameterized factory；
- public multi-Worker Supervisor API；
- PyPy、free-threaded、32-bit、extra architectures；
- native extension/platform wheel；
- exact OS floors；
- License、PyPI、签名和 Attestation。

## 11. P0 后续主要事项

- License、Contribution、Security、Supported Versions、Changelog、Code of Conduct；
- Release/Compatibility Policy 与 v0.x/v1.0 规则；
- P1 implementation scope、Issue 分解和验收矩阵；
- 最终 P0 Freeze 与多多明确授权启动 P1。

## 12. 决策确认流程

提案只有满足 dedicated Issue、ADR/Blueprint amendment、多多确认、PR 审查合并、状态表同步，才成为 Confirmed。

## 13. P0 退出条件

1. 本总纲由多多确认；
2. Hardening 全部并入且 Verification 为 Verified；
3. 不存在第二份同级总体设计；
4. Distribution、源码、组件、Kernel、HTTP、Server、Record、CLI、Build 边界确认；
5. 启动、请求、响应、并发、关闭、崩溃恢复和 Packaging 语义确认；
6. Public Governance 和 Release Policy 确认；
7. P1 范围、Issue 分解和验收标准可直接执行；
8. 历史实施 Issue 已关闭或归档；
9. 多多明确授权启动 P1。

在此之前，所有开发模型只允许执行 P0 文档与治理工作。
