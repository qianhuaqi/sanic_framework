# LingShu Framework 总体架构设计总纲（P0-RC8）

- 设计负责人：小顾
- 产品决策人：多多
- 状态：P0 候选总纲，尚未最终冻结
- GitHub Issue：#25
- 规范仓库：`qianhuaqi/lingshu`
- 已接受决策：ADR-001、ADR-002、ADR-003、ADR-004、ADR-005、ADR-006
- 决策状态：`docs/architecture/P0_DECISION_STATUS.md`

> 本文件是 LingShu 唯一总体架构入口。详细合同位于已接受 ADR 和对应架构文档。P0 最终冻结前，不得创建生产源码、`pyproject.toml`、CI Workflow、运行依赖或发布配置。

## 1. 项目定位

LingShu 是从零开发、独立实现、自主控制的 Python Web/API Framework。

LingShu 不是 Sanic、FastAPI、Flask、Django、Starlette 或其他上层 Web Framework 的包装、适配层或迁移版本，也不承担旧实现兼容义务。

LingShu 自己定义和控制：

- Application Kernel；
- HTTP Runtime 与 Native Server；
- Request、Response、Router、Middleware 与 Streaming；
- 生命周期、并发、取消、清理、容量与背压；
- Extension Protocol；
- Request ID 与 Runtime Record；
- CLI、测试支持和后续生态。

旧实现只保留在：

```text
archive/legacy-sanic-20260628
```

封存提交：

```text
b869270e0ec7cbc324d17ef246e39d0873aab14f
```

旧源码、测试、依赖、Issue、PR 和 API 只作历史参考，不是新框架代码基线。

## 2. 最高原则

- **自主内核**：核心运行能力由 LingShu 自行实现；核心第三方依赖逐项评审。
- **机制与政策分离**：认证、租户、权限、数据库、缓存和业务模型不写进 Core。
- **单向无环依赖**：依赖可机器验证；下层不依赖业务集成、项目代码、测试工具或根 facade。
- **显式生命周期**：禁止 import 副作用启动任务、建连、打开文件或修改运行状态。
- **默认隔离与有界**：Scope 隔离；连接、请求、队列、任务、执行器、记录和磁盘必须有界。
- **Deadline、取消与清理**：绝对 monotonic Deadline；取消传播；所有退出路径有界清理。
- **安全优先**：协议歧义拒绝，敏感数据默认不记录，不自造密码学或证书验证。

## 3. ADR-001：单仓库与开发并发

规范仓库：

```text
qianhuaqi/lingshu
```

- 一个任务对应一个 Issue、writer-prefixed branch、主写入者和 PR；
- 并行开发使用独立 worktree/clone、虚拟环境、缓存和端口；
- Issue 声明写入范围、依赖和集成顺序；
- 重叠路径或同一公共契约禁止并行；
- 公共契约先合并；
- 开发可并行，进入 `main` 必须串行；
- 最终合并权属于项目负责人。

## 4. ADR-002：运行时并发

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

## 5. ADR-003：源码、包和组件边界

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

禁止依赖环、下层导入根 facade、生产代码依赖 testing、以及未经批准的跨组件私有导入。

`lingshu/__init__.py` 是受控 facade，使用显式 `__all__`。深层 import 默认私有。可选集成只在激活时加载。

详细文档：

- `docs/decisions/ADR-003-package-source-layout-and-component-boundaries.md`
- `docs/architecture/PACKAGE_AND_COMPONENT_LAYOUT.md`

## 6. ADR-004：Application Kernel 与请求管线

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
- freeze 原子发布完整不可变 Application Plan，失败不发布部分状态；
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

## 7. ADR-005：Hardening Foundations

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

```text
text/plain; charset=utf-8
application/octet-stream
application/json; charset=utf-8
application/problem+json; charset=utf-8
```

JSON 使用 UTF-8、有限、拒绝 duplicate key、NaN/Infinity 和未知对象；datetime/bytes/Decimal/domain type 使用显式 Serializer。415 表示不支持请求类型，406 表示没有可接受响应，禁止 Content Sniffing。

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

## 8. ADR-006：Executable、CLI 与 Build Baseline

P0-D6 已通过 PR #47 接受，生效提交：

```text
5f89572398cee509b9571ee1fe8c20bd2f71dfeb
```

### 所有权

```text
Application  → routes/middleware/extensions/config revision/lifecycle plan
Server       → one Worker loop/runtime/listener/protocol/readiness/drain
Supervisor   → spawn/listener transfer/readiness/restart/signals/exit
CLI          → arguments/target/config override/Supervisor/diagnostics
```

Application 不负责进程监督；Kernel 不依赖 Server。

### 公共单 Worker Server API

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

`Server`/`serve` 只支持单 Worker。多 Worker Supervisor 初期保持 CLI/internal。Root API 不增加 Server 名称。

### CLI 与 Target

```text
lingshu run TARGET
lingshu check TARGET
lingshu version
python -m lingshu ...
```

Target 只接受：

```text
module:attribute
```

Factory 通过显式 `--factory` 启用同步零参数 callable。禁止文件路径、表达式、调用语法、索引、dotted attribute traversal、隐式扫描和 app 猜测。

### Profile 与 Reload

```text
production
development
test
```

`run` 默认 production；`--reload` 显式选择 development。

Development Reload 使用 Watcher Parent + 单 Child Worker 的进程替换模型。禁止 in-process reload，禁止 multi-Worker reload，也不等同于 ADR-005 生产配置 Revision Reload。

### Multi-Worker、Listener 与 Readiness

- Linux、Windows、macOS 统一以 `spawn` 语义为基线；
- 每个 Worker 独立 import、build/freeze Application，启动一个 loop/runtime；
- required Workers 必须报告同一 RevisionId；
- deterministic import/config/freeze failure 不进入 restart loop；
- Supervisor 绑定一次 listener，并显式传递/复制到 Worker；
- 不依赖 fork 或 `SO_REUSEPORT`；
- Ready 必须满足 listener bound、required Workers ready、RevisionId 一致、required resources/extensions ready、Runtime Record required policy available。

第一终止信号进入 Graceful Drain；第二信号或 Graceful Timeout 进入 Hard Stop。

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

### Python 与平台

```text
Implementation:  CPython
Minimum:         3.12
Required:        3.12, 3.13, 3.14
Preview:         3.15 prerelease
requires-python: >=3.12
```

不设置人为上限。PyPy、free-threaded CPython、32-bit 和其他解释器延后。

Tier 1：维护中的 64-bit Linux、支持期内 64-bit Windows、支持期内 64-bit macOS。Required architecture：Linux x86_64、Windows x86_64、macOS arm64。Linux arm64 和 macOS x86_64 为 Tier 2 when available。

### Build、Version 与 Artifact

```toml
[build-system]
requires = ["hatchling>=1.26,<2"]
build-backend = "hatchling.build"
```

- 根级 PEP 621 `[project]`；
- 初始不创建 `setup.py`、`setup.cfg` 或 dynamic metadata；
- 唯一手工 Version Source 是 `[project].version`；
- Runtime/CLI 使用 `importlib.metadata.version("lingshu")`；
- 禁止重复手工 `__version__` 和组件独立版本。

Console：

```toml
[project.scripts]
lingshu = "lingshu.cli:main"
```

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

Preview：Linux CPython 3.15 prerelease，结果可见但非阻断。

详细文档：

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

## 10. 下一项：P0-D7 Public Governance、Release Policy 与 Final Freeze

P0-D7 应决定：

1. License 与 `LICENSE` 文件；
2. `CONTRIBUTING.md`、Code of Conduct、DCO/CLA 选择；
3. `SECURITY.md`、漏洞报告渠道、支持版本和响应流程；
4. `CHANGELOG.md` 与 Release Notes 规则；
5. SemVer、0.x 兼容性、Deprecation 和 Removal Policy；
6. Release Branch、Tag、Version Bump、Artifact Publication、Rollback、Signing/Attestation；
7. 第一个 Development Version 与 P1/v0.x Milestone；
8. P1 Issue Graph、Write Scope、Dependency 和 Acceptance Matrix；
9. Blueprint/ADR/状态文件一致性审计；
10. P0 Final Freeze 与是否明确授权启动 P1。

## 11. 仍待后续实现或决策

- actual numeric defaults 和 health endpoint path；
- SIGHUP/multi-Worker configuration rollout；
- advanced CLI/factory forms 与 public Supervisor API；
- advanced routing/body formats；
- sync Handler adaptation 与 dependency injection；
- official capabilities/extensions；
- HTTP/2、HTTP/3、accelerators、extra runtimes/platforms；
- native extensions/platform wheels。

## 12. 决策确认流程

提案只有满足 dedicated Issue、ADR/Blueprint amendment、多多确认、PR 审查合并、状态表同步，才成为 Confirmed。

## 13. P0 退出条件

1. 本总纲由多多确认；
2. Hardening 全部并入且 Verification 为 Verified；
3. 不存在第二份同级总体设计；
4. Distribution、源码、组件、Kernel、HTTP、Server、Record、CLI、Build 边界确认；
5. 启动、请求、响应、并发、关闭、崩溃恢复和 Packaging 语义确认；
6. Public Governance、Security、Compatibility 与 Release Policy 确认；
7. P1 范围、Issue 图和验收标准可直接执行；
8. 历史实施 Issue 已关闭或归档；
9. 多多明确冻结 P0 并授权启动 P1。

在此之前，所有开发模型只允许执行 P0 文档与治理工作。
