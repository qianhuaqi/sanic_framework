# LingShu Framework 总体架构设计总纲（Blueprint v0.6）

- 设计负责人：小顾
- 产品决策人：多多
- 状态：总体设计候选版，待多多确认并冻结
- GitHub Issue：#25
- 设计分支：`research/lingshu-framework-blueprint`
- 唯一权威文件：`docs/architecture/LINGSHU_FRAMEWORK_BLUEPRINT.md`
- 变更规则：任何架构变化必须经过 Issue、ADR、Git 提交和多多确认；聊天记录不得覆盖本文件

---

## 1. 根本定位

LingShu 是一个完全独立、自主可控的 Python Web/API Framework，不是 Sanic、FastAPI、Flask、Django、Starlette 或其他 Web Framework 的二次封装，也不承担当前旧实现的兼容义务。

LingShu 自己定义并控制：

- Application Kernel；
- Application Plan；
- HTTP Runtime；
- Request、Response、Router、Middleware；
- Native HTTP Server；
- Service / Layer / Permit；
- Typed Extractor 与 Schema；
- Extension Protocol；
- 生命周期、依赖作用域、取消和清理；
- Supervision、Health、Telemetry；
- Request ID 与每请求 Runtime Record；
- CLI、Scaffold 和官方扩展生态。

当前仓库中的旧代码只作为需求、测试和实现素材。凡是与本 Blueprint 冲突的代码，在 1.0 前可以重写或删除，不建立永久兼容层。

### 1.1 核心目标

1. 稳定：生命周期明确、资源可回滚、取消不泄漏；
2. 安全：从 HTTP 解析层拒绝歧义和恶意输入；
3. 强大：具备完整应用内核、HTTP Runtime、原生服务器和扩展生态；
4. 可调试：每次请求可凭 Request ID 还原完整执行过程；
5. 可扩展：Auth、Tenant、RBAC、Data、Cache、i18n 等独立安装；
6. 可验证：关键行为具备合同、协议、压力和安全测试；
7. 可解释：路由、依赖、配置、Layer、Schema 和错误来源均可解释；
8. 可维护：Python 版本和平台差异集中处理，不污染业务代码。

### 1.2 明确不做

- 不依赖其他上层 Python Web Framework；
- 不为旧 API 保留双轨实现；
- 不把用户、订单、租户表、角色表等业务模型塞入 Core；
- 不自造密码学算法、TLS 算法和证书验证；
- 不为追求零依赖牺牲安全和正确性；
- 1.0 首阶段不承诺完整 HTTP/2、HTTP/3；
- 不以未经测试的极限性能代替稳定性和安全性；
- 不允许运行时全量反射扫描和隐式自动装配；
- 不允许无限自动重试、无限队列和进程级可变全局状态。

---

## 2. 最高架构原则

### 2.1 机制与政策分离

Core 只提供稳定机制，不提供 JWT、Tenant、RBAC、数据库、ORM、Redis 等具体政策。

### 2.2 依赖单向

```text
Project Application
        ↓
Official / Third-party Extensions
        ↓
LingShu HTTP Runtime
        ↓
LingShu Application Kernel
        ↕ Transport Contract
LingShu Native Server
```

Core 不得反向依赖 HTTP、Server、Record 或任何扩展。

### 2.3 显式安装

禁止 import-time 注册、建连、启动任务、修改全局 Registry 和读取项目环境变量。

### 2.4 启动前编译

路由、扩展 DAG、Provider Scope、Layer、Extractor、Schema、配置和安全策略必须编译为确定性的 Application Plan。请求热路径禁止重新扫描模块和类型签名。

### 2.5 默认隔离

App、Worker、ModuleContext、Request、Operation 和 Extension 状态必须隔离。能力只有显式导出才可跨边界共享。

### 2.6 默认有界

队列、连接、请求体、Header、任务、重试、缓存、调试记录、日志和磁盘均必须有限额。

### 2.7 默认可追踪

每一个业务请求必须拥有内部 Request ID 和独立 Runtime Record 目录。

---

## 3. 仓库整体目录结构

采用单仓多包结构：

```text
repo/
├── pyproject.toml                 # 仓库级工具、测试和质量配置
├── README.md
├── CHANGELOG.md
├── SECURITY.md
├── CONTRIBUTING.md
├── LICENSE
├── packages/
│   ├── lingshu-core/
│   ├── lingshu-http/
│   ├── lingshu-record/
│   ├── lingshu-server/
│   ├── lingshu-cli/
│   ├── lingshu-framework/
│   ├── lingshu-auth/
│   ├── lingshu-tenant/
│   ├── lingshu-tenant-auth/
│   ├── lingshu-rbac/
│   ├── lingshu-data/
│   ├── lingshu-sql/
│   ├── lingshu-mysql/
│   ├── lingshu-postgresql/
│   ├── lingshu-mongo/
│   ├── lingshu-cache/
│   ├── lingshu-redis/
│   ├── lingshu-i18n/
│   ├── lingshu-openapi/
│   ├── lingshu-observability/
│   └── lingshu-resilience/
├── templates/                     # CLI 项目与扩展模板
├── examples/                      # 最小、完整、安全部署示例
├── contract-tests/                # 官方/第三方扩展合同测试套件
├── integration-tests/             # 跨包真实集成测试
├── protocol-tests/                # HTTP 协议与恶意报文测试
├── fuzz/                          # Parser、Header、URL、Multipart 等模糊测试
├── benchmarks/                    # 路由、Parser、Pipeline、Record Writer 基准
├── docs/
│   ├── architecture/
│   ├── decisions/
│   ├── development/
│   ├── guides/
│   └── reference/
├── scripts/
└── runtime/                       # 本地运行数据，必须 Git ignore
```

每个 Package 自己拥有：

```text
pyproject.toml
README.md
CHANGELOG.md
src/<import_package>/
tests/
```

多个 distribution 不得共同写同一个普通 Python package。只有 `lingshu-framework` 使用 `lingshu` 作为薄总入口；其他包使用独立 import package。

默认安装：

```bash
pip install lingshu-framework
```

默认包含：

```text
lingshu-core
lingshu-http
lingshu-record
lingshu-server
lingshu-cli
```

---

## 4. 包依赖结构

```text
lingshu_core

lingshu_http       → lingshu_core
lingshu_record     → lingshu_core + lingshu_http
lingshu_server     → lingshu_core + lingshu_http
lingshu_cli        → lingshu_core
lingshu            → core + http + record + server + cli

lingshu_auth       → core + http
lingshu_tenant     → core + http
lingshu_tenant_auth→ auth + tenant
lingshu_rbac       → core + http
lingshu_data       → core
lingshu_sql        → data
lingshu_mysql      → sql
lingshu_postgresql → sql
lingshu_mongo      → data
lingshu_cache      → core
lingshu_redis      → core + cache
lingshu_i18n       → core
lingshu_openapi    → core + http
lingshu_observability → core + http
lingshu_resilience → core
```

禁止：

```text
core → http/server/record/extensions
http → server/database/auth/tenant
server → extensions/project
record → server/database drivers
extension A → extension B（除非 Manifest 显式声明）
```

---

## 5. 源码注释、Docstring 与可读性标准

代码注释不是装饰，而是公共合同和维护工具。

### 5.1 语言规范

- 源码标识符、公共 Docstring、异常消息键和代码注释统一使用英文；
- 架构、开发流程和用户指南可以中文为主；
- 不在同一源码注释中维护中英双份内容，避免长期漂移；
- 对外文档可由公共 Docstring 生成并进行本地化。

### 5.2 强制注释范围

以下内容必须有完整 Docstring 或设计注释：

1. 所有公共 Module、Class、Protocol、Enum、Function、Method；
2. 所有 Extension Manifest 字段；
3. 所有状态机及合法/非法状态转换；
4. 所有并发、锁、队列、背压和任务所有权；
5. 所有安全校验、脱敏和拒绝规则；
6. 所有资源生命周期、回滚、关闭和幂等语义；
7. 所有复杂算法、性能权衡和非显然实现；
8. 所有公共错误码及客户端可见行为；
9. 所有兼容层和版本判断；
10. 所有临时 TODO、FIXME 和安全例外。

### 5.3 公共 API Docstring 内容

至少说明：

```text
Purpose
Parameters
Returns
Raises
Lifecycle / Ownership
Concurrency
Cancellation
Security
Examples（适用时）
```

### 5.4 注释质量要求

注释必须解释：

- 为什么这样设计；
- 必须保持的 Invariant；
- 不能采用直觉写法的原因；
- 修改后可能破坏的安全、并发和生命周期合同。

禁止：

- 重复代码表面含义；
- 失效注释；
- 注释掉的大段旧代码；
- 无 Issue 编号的 TODO；
- 用注释掩盖复杂度而不拆分代码。

TODO 格式：

```text
TODO(#123): reason, owner, removal condition
```

### 5.5 质量门

- 公共 API Docstring 覆盖率 100%；
- 公共函数类型标注覆盖率 100%；
- Core/HTTP/Server/Record 使用严格静态类型检查；
- CI 检查 Docstring、失效 TODO、复杂度和循环依赖；
- 行为变更必须同步修改注释、文档和测试；
- 生成文件必须带 `Generated file; do not edit` 标记和生成源。

---

## 6. `lingshu-core` 目录结构

```text
packages/lingshu-core/
├── pyproject.toml
├── README.md
├── src/lingshu_core/
│   ├── __init__.py
│   ├── application/
│   │   ├── kernel.py              # ApplicationKernel
│   │   ├── builder.py             # KernelBuilder
│   │   ├── state.py               # KernelState
│   │   └── identity.py            # app/instance identity
│   ├── plan/
│   │   ├── model.py               # immutable ApplicationPlan
│   │   ├── compiler.py
│   │   ├── validator.py
│   │   ├── fingerprint.py
│   │   ├── serializer.py
│   │   └── loader.py
│   ├── config/
│   │   ├── field.py
│   │   ├── schema.py
│   │   ├── source.py
│   │   ├── loader.py
│   │   ├── snapshot.py
│   │   ├── secret.py
│   │   └── reload.py
│   ├── context/
│   │   ├── execution.py
│   │   ├── cancellation.py
│   │   ├── deadline.py
│   │   ├── binding.py
│   │   └── operation.py
│   ├── lifecycle/
│   │   ├── state_machine.py
│   │   ├── coordinator.py
│   │   ├── rollback.py
│   │   ├── shutdown.py
│   │   └── errors.py
│   ├── extension/
│   │   ├── manifest.py
│   │   ├── registry.py
│   │   ├── graph.py
│   │   ├── installer.py
│   │   └── contract.py
│   ├── capability/
│   │   ├── token.py
│   │   ├── registry.py
│   │   ├── provider.py
│   │   ├── scope.py
│   │   └── container.py
│   ├── service/
│   │   ├── protocol.py
│   │   ├── permit.py
│   │   ├── layer.py
│   │   ├── stack.py
│   │   └── capacity.py
│   ├── supervision/
│   │   ├── child.py
│   │   ├── supervisor.py
│   │   ├── strategy.py
│   │   ├── restart.py
│   │   └── tree.py
│   ├── telemetry/
│   │   ├── event.py
│   │   ├── schema.py
│   │   ├── bus.py
│   │   └── subscriber.py
│   ├── health/
│   │   ├── status.py
│   │   ├── check.py
│   │   ├── registry.py
│   │   └── aggregator.py
│   ├── errors/
│   │   ├── base.py
│   │   ├── spec.py
│   │   ├── registry.py
│   │   └── redaction.py
│   ├── tasks/
│   │   ├── managed.py
│   │   ├── registry.py
│   │   └── result.py
│   ├── checks/
│   │   ├── model.py
│   │   ├── registry.py
│   │   ├── runner.py
│   │   └── codes.py
│   ├── logging/
│   │   ├── context.py
│   │   ├── adapter.py
│   │   └── redaction.py
│   ├── typing.py
│   └── version.py
└── tests/
```

Core 原则上只依赖 Python 标准库。引入第三方依赖必须另立 ADR。

---

## 7. `lingshu-http` 目录结构

```text
packages/lingshu-http/
├── src/lingshu_http/
│   ├── __init__.py
│   ├── protocol/
│   │   ├── method.py
│   │   ├── version.py
│   │   ├── status.py
│   │   └── media_type.py
│   ├── message/
│   │   ├── headers.py
│   │   ├── cookies.py
│   │   ├── query.py
│   │   ├── url.py
│   │   └── body.py
│   ├── request.py
│   ├── response.py
│   ├── streaming.py
│   ├── routing/
│   │   ├── route.py
│   │   ├── tree.py
│   │   ├── compiler.py
│   │   ├── matcher.py
│   │   ├── params.py
│   │   └── reverse.py
│   ├── middleware/
│   │   ├── stage.py
│   │   ├── definition.py
│   │   ├── compiler.py
│   │   └── pipeline.py
│   ├── extractors/
│   │   ├── base.py
│   │   ├── compiler.py
│   │   ├── path.py
│   │   ├── query.py
│   │   ├── header.py
│   │   ├── cookie.py
│   │   ├── body.py
│   │   └── inject.py
│   ├── schema/
│   │   ├── contract.py
│   │   ├── registry.py
│   │   ├── validator.py
│   │   ├── serializer.py
│   │   └── errors.py
│   ├── modules/
│   │   ├── context.py
│   │   ├── export.py
│   │   └── compiler.py
│   ├── runtime/
│   │   ├── engine.py
│   │   ├── dispatcher.py
│   │   ├── commit.py
│   │   ├── cleanup.py
│   │   └── state.py
│   ├── exceptions/
│   │   ├── mapper.py
│   │   └── response.py
│   └── checks/
└── tests/
```

HTTP Runtime 不认识 Socket、Worker、数据库驱动或具体 Auth 实现。

---

## 8. `lingshu-record` 目录结构

每请求独立目录是强制能力，因此独立为默认安装包：

```text
packages/lingshu-record/
├── src/lingshu_record/
│   ├── __init__.py
│   ├── contract.py                # RequestRecorder capability
│   ├── policy.py                  # capture/redaction/retention policy
│   ├── model.py                   # manifest/event/final record schemas
│   ├── manager.py                 # request record lifecycle
│   ├── writer/
│   │   ├── queue.py
│   │   ├── worker.py
│   │   ├── batch.py
│   │   └── flush.py
│   ├── storage/
│   │   ├── base.py
│   │   ├── filesystem.py
│   │   ├── atomic.py
│   │   └── permissions.py
│   ├── sinks/
│   │   ├── telemetry.py
│   │   ├── logs.py
│   │   └── calls.py
│   ├── recovery/
│   │   ├── scanner.py
│   │   └── finalize.py
│   ├── retention/
│   │   ├── cleanup.py
│   │   └── capacity.py
│   ├── inspector/
│   │   ├── reader.py
│   │   └── explain.py
│   └── checks/
└── tests/
```

`lingshu-record` 通过 Telemetry Event Bus 接收事件，Router、Database、Cache 等组件不得直接操作请求目录。

---

## 9. `lingshu-server` 目录结构

```text
packages/lingshu-server/
├── src/lingshu_server/
│   ├── __init__.py
│   ├── manager/
│   │   ├── process.py
│   │   ├── worker_pool.py
│   │   ├── signals.py
│   │   └── state.py
│   ├── worker/
│   │   ├── runtime.py
│   │   ├── bootstrap.py
│   │   └── shutdown.py
│   ├── listener/
│   │   ├── tcp.py
│   │   ├── tls.py
│   │   └── socket_options.py
│   ├── connection/
│   │   ├── model.py
│   │   ├── state.py
│   │   ├── supervisor.py
│   │   ├── limits.py
│   │   └── timeout.py
│   ├── http1/
│   │   ├── parser.py
│   │   ├── strict_parser.py
│   │   ├── request_decoder.py
│   │   ├── response_encoder.py
│   │   ├── chunked.py
│   │   └── keepalive.py
│   ├── admission/
│   │   ├── limiter.py
│   │   ├── shedding.py
│   │   └── permit.py
│   ├── proxy/
│   │   ├── trust.py
│   │   └── headers.py
│   ├── transport/
│   │   ├── contract.py
│   │   ├── inbound.py
│   │   └── outbound.py
│   ├── platform/
│   │   ├── base.py
│   │   ├── posix.py
│   │   └── windows.py
│   ├── compat/
│   │   ├── python.py
│   │   └── asyncio.py
│   └── checks/
└── tests/
```

第一阶段支持 HTTP/1.1。HTTP/2、HTTP/3 和 WebSocket 以后独立阶段实现。

---

## 10. CLI、总入口与扩展目录结构

### 10.1 `lingshu-cli`

```text
lingshu_cli/
├── main.py
├── commands/
│   ├── new.py
│   ├── run.py
│   ├── check.py
│   ├── doctor.py
│   ├── build_plan.py
│   ├── inspect.py
│   └── explain.py
├── output/
└── templates/
```

### 10.2 `lingshu-framework`

`lingshu` 只提供稳定薄入口：

```python
from lingshu import LingShu, Request, Response, current_request, abort
```

不得重新实现 Core/HTTP/Server 逻辑。

### 10.3 官方扩展

统一结构：

```text
src/lingshu_<name>/
├── __init__.py
├── extension.py
├── manifest.py
├── config.py
├── capabilities.py
├── errors.py
├── language/
├── checks/
└── tests_support/
```

---

## 11. Application Plan

启动或构建阶段执行：

```text
discover
→ validate
→ compile
→ fingerprint
→ freeze
```

Plan 包含：

```text
extension dependency DAG
provider/scope graph
route tree
module context tree
service/layer graph
handler extraction plans
input validators
output serializers
error/catalog registry
configuration schema
telemetry event registry
health check registry
runtime record policy
security policy summary
```

硬性规则：

- 同一输入得到同一 fingerprint；
- Production 可使用 `lingshu build-plan`；
- 启动时验证源码、配置、扩展、Python 和 Plan fingerprint；
- fingerprint 不一致时拒绝旧 Plan；
- 不使用 pickle；
- 第一阶段 Plan 使用可读、可审计格式；
- 不透明代码生成或原生加速必须另立 ADR。

---

## 12. Service / Layer / Permit

```python
class Service(Protocol[RequestT, ResponseT]):
    async def acquire(self, context: ExecutionContext) -> ServicePermit:
        ...

class ServicePermit(Protocol[RequestT, ResponseT]):
    async def call(self, request: RequestT) -> ResponseT:
        ...

class Layer(Protocol):
    def wrap(self, inner: Service) -> Service:
        ...
```

先获得 Permit，再调用 Service，确保容量已经预留。

统一承载：

```text
Handler
Middleware
Timeout
Concurrency Limit
Rate Limit
Load Shedding
Retry
Circuit Breaker
Outbound HTTP
Message Producer
Extension Capability
Runtime Record Writer
```

具体重试、熔断和限流策略属于 `lingshu-resilience`，不进入 Core。

---

## 13. ModuleContext

ModuleContext 形成父子树。子 Context 默认继承父 Context 的 Provider、Layer、Hook、Schema、配置视图和错误处理，但父级和兄弟级不能看到子级私有能力。

能力只有显式 `export` 才可跨边界共享。

示例：

```text
Root
├── PublicContext  → /public
├── AdminContext   → Auth + RBAC + /admin
└── ApiV2Context   → V2 Schema + /v2
```

Context 泄漏、循环依赖、重复导出和非法覆盖必须在 Plan 编译阶段失败。

---

## 14. Typed Extractor 与 Schema

目标 API：

```python
@app.get("/users/{user_id}")
async def get_user(
    user_id: Path[int],
    page: Query[int] = 1,
    principal: Principal = Inject(),
) -> UserOutput:
    ...
```

启动时编译 ExtractionPlan：

```text
path/query/header/cookie extraction
→ type conversion
→ structural validation
→ capability injection
→ body decode
→ handler
→ output serialization
```

规则：

- Body 只能被一个消费型 Extractor 消耗；
- Body Extractor 必须位于计划末端；
- 基础 Schema 校验禁止访问数据库或外部服务；
- 业务校验进入显式 Service；
- Response Schema 是输出字段白名单；
- Unknown Field 策略必须显式；
- Schema Engine 不强制绑定 Pydantic。

---

## 15. Extension Protocol

生命周期：

```text
configure → register → start → ready → drain → stop → close
```

Manifest 至少声明：

```text
name
version
requires_core
requires_python
requires_packages
provides
requires
optional_requires
conflicts
config schema
error/catalog resources
telemetry events
health checks
```

规则：

- 禁止 import-time 副作用；
- Register 必须可撤销；
- Start 失败必须逆序回滚；
- Close 必须幂等；
- 后台任务进入 Task Registry 和 Supervision Tree；
- 多 App 完全隔离；
- 扩展不得修改 Core 文件；
- 扩展必须通过统一 Contract Test。

---

## 16. Telemetry 与 Runtime Record

### 16.1 统一事件总线

组件发出版本化事件：

```text
name
schema_version
phase
monotonic_ns
system_time
measurements
safe_metadata
request_id
connection_id
trace_id
span_id
operation_id
```

统一流向：

```text
Component
→ Telemetry Event Bus
→ Request Record Sink
→ Structured Log Sink
→ Metrics Sink
→ Trace Sink
```

### 16.2 Request ID 创建时机

连接接入后先执行 Connection Admission 和请求行长度/超时校验。只要安全识别出一个 HTTP 请求行，就立即：

1. 生成内部 Request ID；
2. 同步创建独立目录和 manifest；
3. 再继续完整 Header 和 Body 解析。

在尚未形成合法请求行前发生的恶意字节或连接错误记录到：

```text
runtime/connections/<date>/<connection_id>/
```

Keep-Alive 连接中的每个请求拥有不同 Request ID，但共享 Connection ID。

### 16.3 目录结构

```text
runtime/
├── connections/<date>/<connection_id>/
├── requests/<date>/<request_id>/
│   ├── manifest.json
│   ├── request.json
│   ├── events.jsonl
│   ├── routing.json
│   ├── middleware.jsonl
│   ├── logs.jsonl
│   ├── calls/
│   │   ├── database.jsonl
│   │   ├── cache.jsonl
│   │   ├── external_http.jsonl
│   │   ├── message.jsonl
│   │   └── extension.jsonl
│   ├── response.json
│   ├── error.json
│   ├── cleanup.json
│   ├── final.json
│   ├── payload/
│   └── attachments/
└── operations/<date>/<operation_id>/
```

### 16.4 强制语义

- 目录创建失败时不得进入业务处理；
- 请求目录只能由内部 Request ID 构造；
- manifest 和 accepted 事件必须在业务执行前持久化；
- 运行中事件可通过有界 Writer Queue 批量写入；
- 队列满时施加背压，不静默丢事件；
- 正常结束必须写 `final.json`；
- Response 已提交后写盘失败不能修改已发送响应，但必须使 Readiness 失败并写应急日志；
- 启动时恢复没有 `final.json` 的目录为 `crashed` 或 `incomplete`；
- Runtime 目录权限、配额、TTL、磁盘安全线和符号链接防御是强制要求；
- 敏感 Header、Token、Cookie、密码和未脱敏 Body 默认禁止落盘。

---

## 17. 底层运行结构

### 17.1 进程结构

```text
ProcessManager
├── Config Snapshot
├── Frozen ApplicationPlan
├── Listener Ownership
├── WorkerSupervisor
├── Signal / Shutdown Coordinator
└── Process Health Aggregator

Worker Process × N
├── one Event Loop
├── WorkerKernel
├── Worker Container Scope
├── Supervision Tree
├── Telemetry Bus
├── Request Record Writer
├── HTTP Runtime
├── Listener / Connection Supervisor
└── Extension Worker Resources
```

规则：

- Worker 之间不共享可变业务状态；
- ApplicationPlan 是不可变快照；
- POSIX 可通过 fork 复用只读 Plan；Windows 使用 spawn 后重新加载 Plan；
- Worker 连接池、Record Writer、Task Registry 和 Extension Resource 独立；
- Manager 不参与请求业务逻辑；
- 单 Worker 模式仍保持相同生命周期语义。

### 17.2 启动流程

```text
CLI parse minimal args
→ load config sources
→ resolve enabled packages
→ run static system checks
→ compile ApplicationPlan
→ validate + fingerprint + freeze
→ verify runtime directory and permissions
→ create ProcessManager
→ bind listener(s)
→ spawn worker(s)
→ each worker builds WorkerKernel
→ start Telemetry and Record Writer
→ configure/register/start extensions
→ start HTTP Runtime and Connection Supervisor
→ run startup checks
→ mark worker ready
→ manager marks application ready
```

任何 required 组件失败都触发逆序回滚，禁止半启动继续接流量。

### 17.3 关闭流程

```text
signal received
→ manager readiness=false
→ stop accepting new connections
→ workers enter draining
→ wait bounded in-flight requests
→ cancel remaining requests
→ flush Request Records
→ stop supervised tasks
→ close extensions in reverse order
→ close listener and event loop resources
→ write shutdown summary
→ process exit
```

---

## 18. 单请求完整运行链

```text
1. TCP accept
2. connection admission / limits
3. assign connection_id
4. strict request-line parse
5. request-line security validation
6. generate request_id
7. create request directory + manifest
8. create ExecutionContext / Request Scope / deadline
9. parse and validate headers
10. proxy trust and client identity resolution
11. acquire global/worker admission permit
12. route pre-match and ModuleContext selection
13. acquire Service Permit
14. stream body under limits
15. run before-routing layers
16. final route match
17. compile-time ExtractionPlan execution
18. input Schema validation
19. capability injection
20. handler/service execution
21. response Schema serialization
22. response commit
23. stream response with backpressure
24. run after-response hooks
25. cleanup Request Scope and ContextVar bindings
26. flush final Runtime Record
27. release permits and resources
28. keep-alive next request or close connection
```

### 18.1 Response 状态机

```text
new
→ headers_committed
→ streaming
→ completed
```

异常状态：

```text
aborted
client_disconnected
failed
```

Headers 一旦提交，状态码和普通 Header 不得修改。之后发生错误只能中止流或使用协议允许的 Trailer。

### 18.2 Request 状态机

```text
identified
→ recorded
→ parsing
→ routed
→ executing
→ responding
→ cleaning
→ closed
```

异常终态：

```text
rejected
cancelled
timed_out
client_disconnected
failed
crashed
incomplete
```

---

## 19. 并发、容量与背压

每个边界必须有容量合同：

```text
listener connections
worker active requests
per-route concurrency
body bytes in-flight
response bytes queued
record writer queue
extension tasks
outbound calls
```

规则：

- 无容量时拒绝、等待有界时间或 Load Shed；
- 不允许无限排队；
- Deadline 是整个调用链总预算；
- 子调用不得重新获得完整超时；
- 客户端断开触发请求取消；
- `CancelledError` 必须传播；
- 后台任务必须转换为独立 Operation Context；
- HTTP/1.1 第一阶段不并行执行同一连接中的 Pipelined Request；按顺序处理并限制 Read-ahead Buffer；
- Streaming 必须服从写缓冲高水位和低水位。

---

## 20. Supervision 与健康状态

### 20.1 Supervision Tree

后台组件通过 ChildSpec 声明：

```text
name
factory
dependencies
scope
restart_policy
restart_strategy
shutdown_timeout
health_check
significant
```

重启策略：

```text
never
on_failure
always
```

监督策略：

```text
one_for_one
rest_for_one
one_for_all
```

必须有 max_restarts、restart_window、backoff、jitter 和 escalation。

HTTP Handler 失败只结束当前请求，绝不自动重放业务请求。

### 20.2 健康状态

```text
startup
liveness
readiness
degraded
```

- Liveness 不依赖数据库和外部 API，避免重启风暴；
- Readiness 聚合 required 扩展、磁盘、Record Writer、连接池等；
- Draining 时 Liveness 可正常，但 Readiness 必须失败；
- 健康变化进入 Telemetry 和审计记录。

---

## 21. System Check 与可解释工具

命令：

```bash
lingshu check
lingshu check --tag security
lingshu check --deploy
lingshu doctor
lingshu build-plan
lingshu inspect routes
lingshu inspect route <name>
lingshu inspect extensions
lingshu inspect providers
lingshu inspect layers
lingshu inspect config <key>
lingshu inspect health
lingshu explain request <request_id>
```

检查类别：

```text
architecture
configuration
extensions
providers
routes
schemas
security
runtime
storage
server
packaging
deployment
```

ERROR/CRITICAL 默认阻止启动。Production 安全检查不得静默忽略。

---

## 22. 错误与语言资源

归属：

```text
Core      → Core 错误
HTTP      → HTTP/Runtime 错误
Server    → Transport/Protocol 错误
Record    → Runtime Storage 错误
Extension → 扩展错误
Project   → 业务错误
```

每个包携带自己的 Error Registry 和 Catalog。启动时检查 Namespace、号段、Code、Key 和覆盖冲突。

生产环境内部错误响应必须包含 Request ID，但不得包含完整堆栈和敏感详情。

---

## 23. 配置系统

来源优先级：

```text
package defaults
→ project config
→ environment
→ explicit runtime override
```

字段声明：

```text
build_time
startup_fixed
runtime_reloadable
secret
```

热更新采用：

```text
validate → prepare → swap → rollback
```

未知配置默认报错。所有配置模型生成统一 JSON Schema，并进入 Application Plan fingerprint。

---

## 24. 官方扩展边界

### Auth

Principal、Authenticator、JWT Bearer、API Key、Session 和认证 Layer。不包含用户表、注册登录业务、Tenant 和 RBAC。

### Tenant

TenantContext、Host/Header/Path Resolver 和 Tenant Layer。不强制依赖 Auth。

### Tenant-Auth Bridge

从 Principal 或认证 Claims 解析 Tenant，避免 Auth 与 Tenant 相互硬绑定。

### RBAC

Permission、Policy、Gate 和 Authorization Layer。不包含项目角色表和权限表。

### Data

Resource、Transaction、Repository 和 Driver Contract。MySQL、PostgreSQL、Mongo、Redis 为独立包。

### Cache

Cache Protocol、Memory Cache、TTL、Key 规范和 Stampede Protection。

### i18n

Locale Resolver、Catalog、Message Formatter 和资源注册。

### Resilience

Timeout、Concurrency Limit、Queue Limit、Rate Limit、Load Shedding、Retry、Circuit Breaker、Bulkhead 和 Fallback。

Retry 只允许用于幂等操作；已提交响应后禁止重试。

---

## 25. 安全体系

默认：

- Debug 关闭；
- Header、Body、连接、时间和队列均有限额；
- Proxy Header 默认不信任；
- CORS 默认关闭；
- Server Banner 最小化；
- Cookie 安全属性明确；
- 日志与 Record 自动脱敏；
- Runtime 目录不公开；
- TLS 使用安全默认值；
- Parser 对歧义报文直接拒绝。

必须防御：

```text
Slowloris
Request Smuggling
重复 Content-Length
Content-Length / Transfer-Encoding 冲突
非法 Chunk
CRLF Injection
Host Header 异常
路径穿越
编码歧义
Multipart Bomb
无界上传
客户端断开资源泄漏
符号链接替换
Runtime 文件任意读取
```

---

## 26. Python 与平台支持

正式支持：

```text
Python 3.10
Python 3.11
Python 3.12
Python 3.13
Python 3.14
```

Linux 全矩阵，Windows 最低和最高版本重点测试。

能力检测优先，版本判断集中在 Server/Extension Compat 层；不全局屏蔽弃用警告；新 Python 版本先进入预览 CI。

---

## 27. 测试与发布门

测试层级：

```text
Unit
Contract
Integration
Protocol
Fuzz
Stress
Soak
Security
Packaging
Multi-platform
```

核心必测：

- ApplicationPlan 确定性；
- Scope 捕获和依赖循环；
- 生命周期回滚；
- Cancellation 和 Deadline；
- 多 App、多 Worker 隔离；
- Router、Extractor、Schema 和 Response Commit；
- HTTP/1.1 协议与恶意报文；
- Record 目录、原子写、恢复、容量和脱敏；
- Supervision 重启强度和停止；
- 无 ContextVar、Task、Socket、文件句柄和临时文件泄漏；
- Build Wheel/Sdist、Clean Install、Public API Snapshot。

---

## 28. 完整实施路线

```text
P0  总纲确认与冻结
P1  单仓多包骨架、质量工具、注释与类型合同
P2  Core Kernel：Config/Context/Lifecycle/Error/Task
P3  Capability/Scope/Service/Layer/Supervision/Health/Check
P4  Application Plan Compiler
P5  HTTP 基础对象、Router、Middleware、ModuleContext
P6  Extractor、Schema、Response Commit、Error Pipeline
P7  Telemetry Event Bus 与 lingshu-record
P8  Native Server：Manager/Worker/Connection/HTTP1
P9  Admission、Backpressure、Graceful Shutdown、多 Worker
P10 Security Hardening、Fuzz、Request Smuggling
P11 Extension Runtime 与 Contract Test Kit
P12 Auth/Tenant/Tenant-Auth/RBAC/i18n/Cache/Resilience
P13 Data/SQL/MySQL/PostgreSQL/Mongo/Redis
P14 CLI、Scaffold、Inspect、Doctor、Explain
P15 性能优化、Accelerated Parser、长期压测
P16 WebSocket/OpenAPI/Observability
P17 1.0 API 冻结与发布
```

---

## 29. 开始实施前的退出条件

P0 只有满足以下条件才可结束：

1. 本 Blueprint 由多多确认；
2. v0.5 增补内容已经并入本文件；
3. 不再存在第二份具有更高优先级的总体设计文件；
4. 包结构、Core 目录、HTTP 目录、Record 目录、Server 目录已经固定；
5. 启动、请求、关闭和崩溃恢复流程已经固定；
6. 源码注释和 Docstring 标准已经固定；
7. P1 范围和验收标准能够直接编写 Issue；
8. Qwen、Gemini、GLM 等开发者只执行冻结设计，不再自行设计总体架构。

---

## 30. 当前冻结候选决策

1. LingShu 是完全独立的 Python Framework；
2. 不依赖 Sanic 或其他上层 Web Framework；
3. 不承担旧项目兼容义务；
4. 采用单仓多独立 distribution；
5. Core、HTTP、Record、Server 分包；
6. 每个请求必须有内部 Request ID 和独立 Runtime Record；
7. 目录创建失败时请求不得进入业务；
8. 所有观测通过统一 Telemetry Event Bus；
9. 路由、依赖、Layer、Extractor、Schema 和配置编译为 Application Plan；
10. 使用 Service/Layer/Permit 统一容量和背压；
11. ModuleContext 默认隔离；
12. Response Schema 是输出字段白名单；
13. 后台组件受 Supervision Tree 管理；
14. Startup、Liveness、Readiness、Degraded 分离；
15. Core 不包含 Auth、Tenant、RBAC、Data、Cache、i18n；
16. Model/BusinessModel 不进入 Core；
17. Python 3.10～3.14；
18. 公共 API Docstring、类型标注和关键设计注释是强制质量门；
19. 安全、稳定、可解释和可测试优先于极限性能；
20. 本 Blueprint 确认前不得启动生产实现。
