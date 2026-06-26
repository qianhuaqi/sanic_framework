# ADR：LingShu 核心与扩展边界

- 状态：Draft
- 阶段：Phase C0 收敛
- 范围：LingShu API 最小核心、官方扩展与后续生态

## 背景

LingShu 需要支持数据库、安全、Schema、OpenAPI、事件、可观测性、任务与未来 AI/MCP，但如果所有能力都进入核心，会造成：

- 依赖沉重；
- 未使用功能也被导入；
- 安全与数据库实现互相耦合；
- 新后端必须修改核心；
- 发布和升级风险扩大；
- 最小项目难以理解和测试。

反过来，如果核心只剩空壳，业务又会缺少统一安全、错误、上下文和生命周期合同。

## 决策

采用三层结构：

```text
LingShu Core
Official Extensions
Third-party / Future Integrations
```

核心负责稳定协议、状态机、安全默认值和参考实现；具体驱动、外部系统和重型能力通过扩展接入。

## LingShu Core

核心必须包含：

### 公共上下文与错误

```text
app/request/config/logger/db facade
ContextVar isolation
request_id/trace/operation context
error taxonomy
code/msg/data envelope
language/abort facade
```

### 请求合同与安全执行链

```text
RoutePolicy model/compiler
transport guard
maintenance gate
Authenticator/AuthorizationPolicy protocols
Principal/TenantContext
Signature/Replay/Idempotency/Rate protocols
policy execution pipeline
```

核心可以提供安全的 in-memory reference store 供测试和单进程开发，但不把 Redis 作为强制依赖。

### 并发与生命周期

```text
Deadline/Cancellation context
TaskGroup/TaskRegistry contracts
CapacityLimiter protocol
BoundedQueue reference
Lifecycle/ShutdownCoordinator
health/readiness model
```

### 数据访问公共层

```text
db facade
connection alias
backend registry
capabilities
resource lifecycle
transaction/store protocols
normalized errors
```

核心不实现一个跨所有数据库的万能 Query/ORM。

### Schema 与 API 合同

```text
lingshu.schema facade
Input/Output/Transport contract base
validation error model
Schema registry
OpenAPI contract compiler protocol
contract diff protocol
```

Python 第一阶段可将 Pydantic 作为核心运行依赖，但业务代码只依赖 LingShu facade。

### 扩展协议

```text
ExtensionManifest
ProviderRegistry
Scope-aware Container
Dependency DAG
configure/setup/start/ready/drain/stop/close
extension health and contract test
```

### 事件、审计与观测接口

```text
LocalEventBus reference
AfterCommit registry
DurableEvent/AuditSink protocols
Telemetry hooks/context propagation API
```

核心不内置 Kafka、ClickHouse 或特定 OpenTelemetry exporter。

## 官方扩展

官方维护、与框架版本同步，但默认按配置启用。

### 数据扩展

```text
mysql
sqlite
mongodb
redis
```

每个扩展拥有独立：

```text
driver dependency
backend implementation
ORM/ODM/capability API
transaction/index/migration behavior
health and metrics
contract tests
```

Redis 扩展提供 Cache/Lock/Rate/Replay/Idempotency/Operation/Stream 等组件，不提供 ORM。

### 安全扩展

```text
JWT/Bearer authenticator
session authenticator（按需要）
API key authenticator
optional AEAD body protection
```

HMAC 签名协议可位于核心合同，密钥存储与分布式 ReplayStore 作为扩展。

### 可观测性扩展

```text
OpenTelemetry SDK/exporter
structured logging integrations
external audit sinks
```

核心只生成标准 hooks 和字段。

## 第三方与后续集成

```text
PostgreSQL
ClickHouse
Elasticsearch/OpenSearch
Kafka/NATS/RabbitMQ
Temporal/Celery/Ray
Casbin/OPA
cloud secret managers
MCP/AI providers
```

这些能力通过稳定 Extension、Backend、Store、EventSink、Policy 等协议接入。

## 依赖策略

### 最小安装

```text
pip install lingshu-framework
```

能够运行基础 HTTP、Schema、安全策略编译、内存参考 Store 和测试工具。

### Extra/可选依赖候选

```text
lingshu-framework[mysql]
lingshu-framework[sqlite]
lingshu-framework[mongodb]
lingshu-framework[redis]
lingshu-framework[otel]
lingshu-framework[all]
```

当前仓库是否立即拆 Extras 由 Phase F 决定，但代码必须先满足：

- 未启用扩展不导入可选驱动；
- 可选依赖缺失时报清晰错误；
- 缺失 Mongo/Redis 不影响纯 MySQL 项目；
- 扩展版本和核心兼容范围可检查。

## 核心入口稳定性

业务可以继续使用统一入口：

```python
from lingshu import db

await db.connection("primary")
await db.mysql...
await db.redis.cache...
```

`db` facade 属于核心，`mysql/redis` 实际能力由扩展注册。

未启用时：

```text
BackendNotInstalled
BackendNotConfigured
CapabilityNotSupported
```

不得返回 None 或延迟到深层 AttributeError。

## 扩展不能绕过的核心底线

所有扩展必须遵守：

```text
context isolation
timeout/cancellation
security policy
logging redaction
trace/metrics hooks
health/readiness
lifecycle rollback
error taxonomy
contract tests
```

扩展的 native/raw 入口也不能绕过这些底线。

## 核心禁止项

以下不进入核心：

- 完整消息代理客户端；
- 完整工作流引擎；
- ClickHouse/OLAP；
- AI Provider/MCP Server；
- 设备网关；
- 特定云厂商实现；
- 所有数据库驱动强制安装；
- 业务级用户/订单/资产模型。

## 单仓库过渡方案

当前可以保持：

```text
src/lingshu/extensions/mysql/
src/lingshu/extensions/sqlite/
src/lingshu/extensions/mongodb/
src/lingshu/extensions/redis/
```

即使仍在同一 wheel 中，也必须：

- 延迟导入第三方驱动；
- 通过 Manifest 注册；
- 独立测试；
- 不修改核心 facade 即可增删；
- 为未来拆包保留兼容 import path 或迁移策略。

## 被拒绝方案

- 将 aiomysql/motor/redis 等全部能力直接写进 `db` facade；
- 所有扩展自动启用；
- 缺失可选依赖导致框架 import 失败；
- 扩展自行创建无监管任务；
- native client 完全绕过超时、日志、权限和生命周期；
- 为减少文件把核心与后端实现重新合并。

## 验收条件

1. 最小安装不需要未启用数据库驱动；
2. db facade 不包含具体方言和驱动逻辑；
3. 新 fake backend 不改核心即可注册；
4. 禁用 Redis/Mongo 不影响 MySQL 启动；
5. 扩展依赖缺失返回清晰错误；
6. 扩展 start 失败可逆序回滚；
7. native/raw 仍应用公共策略；
8. 每个官方扩展拥有独立合同与真实集成测试；
9. 核心公共 API 不暴露第三方驱动类型；
10. 后续拆分独立包时业务入口保持稳定。