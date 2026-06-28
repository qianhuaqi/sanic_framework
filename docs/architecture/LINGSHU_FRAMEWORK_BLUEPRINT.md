# LingShu Framework 总体架构设计总纲（P0-RC6）

- 设计负责人：小顾
- 产品决策人：多多
- 状态：P0 候选总纲，尚未最终冻结
- GitHub Issue：#25
- 规范仓库：`qianhuaqi/lingshu`
- 已接受决策：ADR-001、ADR-002、ADR-003、ADR-004、ADR-005
- 决策状态：`docs/architecture/P0_DECISION_STATUS.md`

> 本文件是 LingShu 当前唯一总体架构入口。详细执行合同位于已接受 ADR 和对应架构文档。P0 完成前不得创建生产源码、包骨架、运行时依赖或发布配置。

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

历史提交：

```text
b869270e0ec7cbc324d17ef246e39d0873aab14f
```

旧源码、测试、依赖、Issue、PR 和 API 只作历史参考，不是新框架基线。

## 2. 最高架构原则

### 自主内核

核心运行能力由 LingShu 自行实现，不通过安装其他上层 Web 框架获得。核心第三方依赖必须逐项评审。

### 机制与政策分离

核心只提供通用机制，不把认证、租户、权限、数据库、缓存或业务模型写进核心。

### 单向无环依赖

依赖必须显式、无环并可机器验证。下层组件不得反向依赖业务集成、项目代码、测试工具或根级公共 facade。

### 显式生命周期

禁止通过 import 副作用注册、建连、启动任务、打开文件或修改进程级运行状态。启动、运行、排空和关闭必须有状态、有界预算、失败回滚、逆序清理、幂等关闭和可观测结果。

### 默认隔离与有界

Application、Worker、Connection、Request、Operation 和 Extension 状态按 Scope 隔离。连接、请求体、队列、任务、执行器、记录和磁盘使用必须有上限、背压或拒绝策略。

### Deadline、取消与清理

Deadline 是调用链共享的绝对 monotonic 预算，子调用只能继承或缩短。取消必须传播；任何退出路径都必须执行确定性、有界清理。

### 安全优先

协议歧义直接拒绝；敏感数据默认不记录；不自造密码学或证书验证；安全、正确性和可恢复性优先于未经验证的极限性能。

## 3. ADR-001：单仓库与开发并发

规范仓库：

```text
qianhuaqi/lingshu
```

开发治理：

- 一个任务对应一个 Issue、分支、主写入者和 PR；
- 并行开发使用独立 worktree/clone、虚拟环境、缓存和端口；
- Issue 必须声明写入范围、依赖和集成顺序；
- 重叠路径或同一公共契约禁止并行；
- 公共契约先合并，依赖任务再同步；
- 开发可并行，进入 `main` 必须串行；
- 最终合并权属于项目负责人。

## 4. ADR-002：运行时并发

正确性基线是 Python 标准库 `asyncio` 语义。

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

确认规则：

- Worker 不共享可变 Python 应用状态；
- 请求创建的任务默认归 Request 所有；
- 未登记 fire-and-forget 任务禁止；
- 一个 HTTP/1.1 连接同一时刻执行一个请求；
- 连接、请求、队列、执行器、依赖、Telemetry 和 Runtime Record 均有界；
- 网络、解析、请求体、业务、依赖和响应形成完整背压链；
- Deadline 使用绝对 monotonic time；
- Blocking I/O 与 CPU 密集工作不得阻塞 Worker event loop；
- Worker 重启有预算和退避；
- 关闭顺序为停止准入、排空、取消、逆序清理、刷新记录、关闭 Transport/执行器和 hard-stop。

详细文档：

- `docs/decisions/ADR-002-runtime-concurrency-model.md`
- `docs/architecture/RUNTIME_CONCURRENCY_MODEL.md`

## 5. ADR-003：打包、源码和组件边界

```text
Repository:          qianhuaqi/lingshu
Distribution:        lingshu
Import package:      lingshu
Packaging file:      pyproject.toml
Production source:   lingshu/
src layout:          prohibited
```

初始框架采用一个 distribution、一个 import package、一个根级 `pyproject.toml`、一个版本和一个发布节奏。

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

禁止依赖环、下层导入根 facade、生产代码依赖 testing、以及未经批准的跨组件私有导入。

`lingshu/__init__.py` 是受控公共 facade，采用显式 `__all__`。深层 import 默认私有。可选集成只在激活时加载。

不使用 `src/` 后，打包验收必须构建 wheel/sdist、在全新环境非 editable 安装、切换到仓库外执行测试，并禁止仓库 `PYTHONPATH` 注入。

详细文档：

- `docs/decisions/ADR-003-package-source-layout-and-component-boundaries.md`
- `docs/architecture/PACKAGE_AND_COMPONENT_LAYOUT.md`

## 6. ADR-004：Application Kernel 与请求管线

公开应用类型是：

```python
from lingshu import LingShu, Request, Response, HTTPException
```

内部 Kernel 负责生命周期、注册目录、Application Revision、freeze 校验、不可变 Application Plan 和资源生命周期契约。Kernel 不拥有 Listener、HTTP Parser 或业务政策，也不依赖 Server。

Application 生命周期：

```text
CREATED
→ CONFIGURING
→ FROZEN
→ STARTING
→ RUNNING
→ DRAINING
→ STOPPING
→ STOPPED
```

Route、Middleware、Exception Mapper、Extension、配置和 Hook 只在 freeze 前注册。Freeze 原子发布完整不可变 Plan；失败不得发布部分状态。

初始 Handler：

```python
async def handler(request: Request) -> Response | SupportedReturnValue:
    ...
```

初始只接受异步 Handler 和显式 Request，不自动依赖注入，也不把同步 Handler 直接放在 event loop 执行。

Middleware 使用 Application 与 Route 两层确定性洋葱模型，`call_next` 单次且受当前 Scope 约束。

固定请求管线：

```text
协议接入
→ Request Scope / Deadline
→ 身份与 Runtime Record
→ Request 与 Body Stream
→ Application 准入
→ Application Middleware
→ Route Match
→ Route 准入与 Capability
→ Route Middleware
→ Handler
→ Response Normalization
→ Middleware 逆序退出
→ Exception Fallback
→ Response Prepare
→ Response Commit
→ Body/Stream 发送
→ Record Finalize
→ Task Cleanup
→ Scope Resource Release
```

Request metadata 只读；Body 有界、背压、单消费者；Request state 属于 Scope。

初始 Handler 返回支持 Response、str 和 bytes-like。默认拒绝 None、tuple magic、任意 iterator/generator 和未知对象。

Response 状态：

```text
NEW → PREPARED → COMMITTED → COMPLETED
                  ↘          ↘
                   ABORTED ← ABORTED
```

Commit 后状态码和 Header 不可修改，也不能生成第二个 Response。

详细文档：

- `docs/decisions/ADR-004-application-kernel-request-pipeline-and-public-api.md`
- `docs/architecture/APPLICATION_KERNEL_AND_REQUEST_PIPELINE.md`

## 7. ADR-005：Hardening Foundations

### 时间与标识

- UTC wall time 用于可读时间、Retention 和跨进程关联；
- monotonic time 用于 Deadline、timeout、queue wait、scheduling 和 duration；
- 每个 Runtime Record 使用递增 event sequence；
- Request、Connection、Trace、Operation、Worker 和 Record ID 是 128-bit opaque typed value；
- RevisionId 是规范化 Application Revision 的 SHA-256；
- LingShu 永远生成内部 RequestId；入站 Request ID 只作为不可信外部关联；
- remote TraceId 只代表 correlation，不代表授权或信任。

### Exception 与 Error Code

Framework Error 具有稳定 code、safe message、client visibility、retryability、severity、fatal scope、safe details 和内部 cause。

Client-visible Framework Error 使用 `application/problem+json`。默认不暴露 Traceback、路径、配置、环境信息、凭据、请求正文、SQL 或内部拓扑。Cancellation 仍是控制流。

### Configuration

优先级：

```text
built-in defaults
< configuration file
< environment variables
< CLI overrides
< explicit programmatic overrides
```

配置必须经过 Schema normalize/validate，unknown key 默认失败，配置文件具有 schema version，迁移必须显式、确定和可测试。

运行时只接收不可变 typed Configuration Snapshot。受保护配置值通过专用类型或 Provider 处理，并在所有输出路径中隐藏。

Reload：

```text
load
→ normalize
→ validate
→ resolve protected values
→ prepare resources
→ compile/freeze Revision
→ atomic publish
→ drain old Revision
→ cleanup old resources
```

Publish 前失败保持旧 Revision 不变；无法安全回滚的 Publish 后失败进入明确 degraded/not-ready 状态。

### Serialization

Baseline：

```text
text/plain; charset=utf-8
application/octet-stream
application/json; charset=utf-8
application/problem+json; charset=utf-8
```

JSON 只使用 UTF-8，拒绝 duplicate key、NaN 和 Infinity，并限制 bytes、depth、items、strings 和 number tokens。未知对象不自动序列化；datetime、bytes、Decimal 和自定义值必须显式注册 Serializer。

不支持请求 Content-Type 返回 415；无可接受响应格式返回 406；禁止 Content Sniffing。

### Runtime Record

每个业务请求在 Handler 前预留 RecordId、Queue Capacity、Record/Event Budget、Durability 和 Storage Health。默认策略是 `required`：无法保证记录能力时在业务处理前拒绝请求。

Event Envelope 版本化且 append-only，包含时间、顺序、身份、组件、Outcome、HTTP 结果、Error Code、Cancellation 和有界 Attributes。

默认本地 Writer 使用 append-only UTF-8 JSON Lines rotated segments 和 atomic manifest/index。

Durability：

```text
buffered
flush
fsync
```

记录系统具有 Event、Record、Queue、Segment、Disk、Retention、Cleanup、Flush、Shutdown 和 Recovery 预算。

Disk 状态：

```text
normal
→ soft watermark
→ hard watermark
→ critical reserve
```

Hard Watermark 下服务 Not Ready 并拒绝新的 required 请求。Critical Reserve 只保留最小故障、健康、关闭和数据丢失诊断。Retention 不得删除 Active Segment。

Crash Recovery 校验路径、权限、Manifest 和 Tail，截断不完整末行，隔离无法恢复 Segment，重建索引并报告估算损失。只有记录策略可满足后才 Ready。

### Telemetry

Logs、Traces、Diagnostics 和 Runtime Records 共享统一字段和 `public/internal/sensitive/secret` 分类。

Request、Record、Trace、Operation、Connection ID、Raw Path、Raw Error Message 和 User/Tenant ID 默认禁止作为 Metric Label。Metric 使用 Component、Route Template/Name、Method、Status Class、Outcome、Stable Error Code 和 Cancellation Reason 等有界维度。

详细文档：

- `docs/decisions/ADR-005-hardening-foundations.md`
- `docs/architecture/HARDENING_FOUNDATIONS.md`
- `docs/architecture/P0_HARDENING_CHECKLIST.md`

`P0_HARDENING_CHECKLIST.md` 已标记为 Verified Integration Mapping，不再是第二架构来源。

## 8. 当前禁止事项

P0 最终冻结前禁止：

- 创建生产 `lingshu/` 目录、`tests/` 骨架或 `pyproject.toml`；
- 创建 `src/lingshu/` 或初始 `packages/` 结构；
- 引入运行时依赖；
- 实现 Kernel、Runtime、HTTP、Server、Record、Config、Serializer、CLI 或 Extension；
- 发布安装包；
- 建立旧框架适配、迁移层或兼容转发层；
- 多个开发者共享同一可写目录或分支；
- 并行任务修改重叠路径或同一公共契约；
- 启动 P1。

## 9. 下一项：P0-D6 Executable and Packaging Baseline

P0-D6 应确认：

1. Public Server Startup / Serve API；
2. Application、Server 与 CLI 的所有权边界；
3. CLI command grammar 和 `module:app` discovery；
4. Development 与 Production 执行和 Reload 边界；
5. Worker/process 参数、Signal、Readiness 和 Exit Code；
6. Python 最低版本和平台支持矩阵；
7. Build Backend 与权威 Version Source；
8. Package Metadata、Console Entry Point、Wheel/sdist 与 CI Matrix；
9. Startup、Discovery、Signal、Packaging 和 Clean-install Contract Tests。

## 10. 仍待后续决策

- exact numeric defaults 和 environment profiles；
- automatic HEAD/OPTIONS；
- host routing、reverse routing、mount 与 sub-application；
- form、multipart、upload、compression 和 streaming formats；
- sync Handler adaptation 与 dependency injection；
- official capabilities and integrations；
- HTTP/2、HTTP/3 和 optional accelerators；
- Release、Compatibility、License、Contribution、Security、Changelog 和 Code of Conduct；
- final P0 freeze 与 P1 implementation plan。

## 11. 决策确认流程

提案只有同时满足以下条件才成为 Confirmed：

1. 专用 GitHub Issue；
2. Blueprint amendment 或 ADR；
3. 多多明确确认；
4. PR 审查并合并；
5. `P0_DECISION_STATUS.md` 同步。

## 12. P0 退出条件

P0 只有满足以下条件才能结束：

1. 本总纲由多多确认；
2. 所有接受的 Hardening 已并入；
3. Hardening Integration Verification 为 Verified；
4. 不存在第二份同级总体设计；
5. Distribution、源码、组件和扩展边界已确认；
6. Kernel、HTTP、Server、Runtime Record 职责与合同已确认；
7. 启动、请求、响应、并发、关闭和崩溃恢复语义已确认；
8. P1 范围和验收标准可以直接写入 Issue；
9. 历史实施 Issue 已关闭或归档；
10. 多多明确授权启动 P1。

在此之前，所有开发模型只允许执行 P0 文档和治理工作。
