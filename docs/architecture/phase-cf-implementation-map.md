# LingShu Phase C–F 实施映射

> 状态：Phase C0 收敛稿。
>
> 原则：不做大爆炸 PR；上一子阶段未验收通过，不进入下一子阶段。

## 总体顺序

```text
C0 收敛与治理修正
-> C1 请求执行基础
-> C2 认证授权与租户
-> C3 签名、防重放、限流与幂等
-> D1 数据入口与后端注册
-> D2 MySQL ORM/事务/Migration
-> D3 SQLite 独立后端
-> D4 MongoDB ODM
-> D5 Redis 能力后端
-> E1 Schema/Validation/Serialization
-> E2 OpenAPI/SDK/Contract Diff
-> E3 Extension/DI/Lifecycle
-> E4 Event/Audit/OpenTelemetry
-> F1 CLI/脚手架/文档
-> F2 CI/Packaging/Compatibility/Cleanup
```

当前阶段只施工 LingShu API。微服务、Go、Vue Runtime 和硬件网关仅保留合同，不进入此路线。

---

# C0：研究收敛与治理修正

## 目标

- 合并研究文档和 ADR；
- 更新过期 `docs/codex/CURRENT_PHASE.md`；
- 更新 Issue #5 的 C–F 详细子阶段；
- 冻结第一版公共合同和拒绝项；
- 不修改运行时代码。

## 交付

```text
lingshu-adoption-matrix.md
ADR-core-vs-extension-boundary.md
phase-cf-implementation-map.md
updated CURRENT_PHASE.md
```

## 验收

- 所有 ADR 互不矛盾；
- core/extension/later 边界明确；
- 每个后续 PR 有输入、输出与测试合同；
- 研究分支只包含文档和治理修改。

---

# C1：请求执行基础与生命周期

## 范围

```text
RequestExecutionContext
RoutePolicy model/compiler skeleton
Deadline/Cancellation
TaskRegistry
Lifecycle/ShutdownCoordinator
health/live/ready/drain
```

## 不在本阶段

- JWT；
- HMAC 签名；
- Redis；
- 具体权限引擎；
- 完整幂等实现。

## 关键合同

```text
request_id/trace_id/operation_id
deadline remaining budget
context cleanup
compiled route policy
application lifecycle state
```

## 测试

- 100/1000 并发 ContextVar 隔离；
- 异常、取消、超时后的清理；
- drain 后拒绝新业务；
- shutdown 逆序释放；
- route policy 覆盖规则确定。

---

# C2：Authentication、Authorization 与 Tenant

## 范围

```text
Principal
Authenticator protocol
AuthResult taxonomy
TenantContext
Gate/Policy
permission/scope
route security enforcement
```

## 第一版实现

- 一个简单 Bearer/JWT 官方实现；
- 一个测试 Authenticator；
- RBAC/permission reference policy；
- Resource Policy protocol。

## 安全要求

- invalid/expired/revoked 不降级；
- tenant 不直接信任 Header；
- 401/403 稳定错误；
- 不返回内部 exception 文本；
- public route 必须显式声明。

## 测试

- 端到端真实拦截；
- 权限负向矩阵；
- tenant 越权；
- 多认证器顺序；
- Policy 未注册默认拒绝。

---

# C3：签名、防重放、限流、并发限制与幂等

建议拆为两个 PR，避免过大。

## C3.1 签名与防重放

```text
canonical request
HMAC-SHA256
raw body digest
timestamp/nonce
ReplayStore protocol
key rotation
webhook profile
```

测试跨 Python/Go/TypeScript 固定向量，即使 Go/TS 只提供测试夹具，不实现运行时。

## C3.2 限流、并发与幂等

```text
RateLimiter protocol
ConcurrencyLimiter
Memory reference store
IdempotencyStore protocol
operation unknown state
Retry-After/202/409 policies
```

Redis 实现留到 D5；C3 只提供协议和内存参考实现。

## 测试

- nonce 并发只成功一次；
- 同幂等键 100/1000 并发只有一个 owner；
- 同 key 不同 fingerprint 冲突；
- unknown 不重跑；
- rate 与 concurrency 独立；
- trusted proxy 伪造测试。

---

# D1：数据入口、注册中心与公共资源合同

## 范围

```text
db facade
connection aliases
backend registry
capabilities
normalized errors
pool/resource lifecycle
transaction/store protocols
```

## 验收

- fake backend 不修改 facade 即可注册；
- 多 app/多连接隔离；
- 缺失 backend、配置和 capability 有明确错误；
- 未启用后端不导入重依赖；
- native 入口仍经过公共 timeout/trace/redaction。

---

# D2：MySQL ORM、事务与 Migration

建议至少拆三个 PR。

## D2.1 MySQL Driver/Pool/Transaction

```text
独立 pool
acquire/connect/read/write timeout
transaction ContextVar
commit/rollback
savepoint
after_commit
normalized errors
```

## D2.2 TableModel/Query/SQL Repository

```text
simple CRUD
expression/query builder
strict relation loading
optimistic locking
stream/chunk
SQL-first named repository
safe raw
```

## D2.3 Migration/CLI

```text
make migration
migrate
status
rollback
schema drift check
```

## 测试

- 真实 MySQL；
- 事务隔离与死锁；
- pool 耗尽；
- SQL/identifier/operator 注入；
- N+1 strict loading；
- 大结果内存；
- Migration upgrade/rollback。

---

# D3：SQLite 独立后端

## 原则

SQLite 不是 MySQL 测试替身，而是独立后端。

## 范围

```text
sqlite driver
transaction/savepoint
lock/busy handling
dialect
migration
capabilities
```

可以共享 TableModel 表达式协议，但不得通过大量 `if sqlite` 写在 MySQL 实现中。

## 测试

- 并发读写；
- busy timeout；
- DDL 差异；
- upsert/returning 能力；
- 文件/内存数据库生命周期。

---

# D4：MongoDB ODM

建议拆两个 PR。

## D4.1 Backend/DocumentModel/Schema

```text
connection lifecycle
DocumentModel
schema validation/version
projection
indexes
optimistic version
tenant boundary
```

## D4.2 Query/Aggregation/Bulk/Transaction

```text
operator allowlist
aggregation builder/stage budget
bulk write
native pipeline policy
explicit transactions
```

## 测试

- 真实 MongoDB；
- operator injection；
- collection validator；
- index conflict；
- document/array/depth budget；
- projection 敏感字段；
- schema upgrade。

---

# D5：Redis 能力后端

建议拆三个 PR。

## D5.1 Backend/Cache

```text
pool/lifecycle
safe serializer
namespace/TTL
pipeline
stampede protection
big/hot key guards
```

## D5.2 Lock/Rate/Replay/Idempotency

实现 C3 协议的 Redis adapter：

```text
owner token
TTL/release compare
fencing option
atomic reserve
multi-window limiter
unknown operation state
```

## D5.3 Stream/Operation Store

```text
Stream consumer group
ack/pending/recovery/dead-letter
OperationStore
bounded retention
```

## 测试

- 真实 Redis；
- pipeline 非事务语义；
- lock 旧 owner；
- 1000 并发 reserve；
- stampede；
- Stream 重复投递；
- pool/timeout/failover 行为。

---

# E1：Schema、Validation 与 Serialization

## 范围

```text
lingshu.schema facade
Transport/Input/Output base
strict profiles
PATCH tri-state
ValidationIssue/error mapping
Output filtering
```

## 测试

- unknown/overposting；
- body/query 转换差异；
- missing/null/value；
- 深度/大小/错误数量预算；
- 子类敏感字段不泄漏；
- ORM lazy relation 不因序列化触发。

---

# E2：OpenAPI 3.1、SDK 与 Contract Diff

建议拆两个 PR。

## E2.1 Contract Compiler

```text
Route Contract
Schema Registry
OpenAPI 3.1
Error Components
security/idempotency metadata
operationId checks
```

## E2.2 TypeScript SDK/CI

```text
TS types/client
AbortSignal
Idempotency-Key
operation unknown
optional Zod
contract diff
generation drift
```

## 测试

- OpenAPI validation；
- example validation；
- TS build；
- breaking change fixtures；
- reproducible output。

---

# E3：Extension、DI 与 Lifecycle

## 范围

```text
ExtensionManifest
ProviderRegistry
Scopes
DAG
setup/start/ready/drain/stop/close
rollback
health
entry-point discovery（可先只做协议）
```

## 测试

- captive dependency；
- 循环依赖；
- start 第 N 步失败逆序回滚；
- optional dependency；
- scope disposal；
- disabled extension 不加载依赖。

---

# E4：Events、Audit 与 OpenTelemetry

建议拆三个 PR。

## E4.1 Local/AfterCommit Events

```text
LocalEventBus
subscriber registry
failure policies
after_commit
```

## E4.2 Outbox/Audit Contracts

```text
CloudEvent-like envelope
Outbox model/protocol
consumer idempotency
AuditSink/audit levels
```

第一阶段可以实现内存/数据库参考，外部消息代理留作扩展。

## E4.3 Telemetry Hooks/OTel Extension

```text
W3C propagation
span/metric/log hooks
structured log context
bounded exporter behavior
```

## 测试

- rollback 不发事件；
- Outbox 崩溃恢复；
- Audit 脱敏；
- trace 跨 HTTP/event；
- metric cardinality；
- exporter 故障不拖死请求。

---

# F1：CLI、脚手架与文档自动化

## 范围

```text
make module/model/business-model/schema/migration
openapi export
schema export
client generate
contract check/diff
dry-run/diff/conflict detection
manual/generated separation
```

## 验收

- 新项目生成后安装、启动、测试；
- 重复生成可预期；
- 手写文件不被覆盖；
- 模板版本可追踪；
- 文档与合同生成可复现。

---

# F2：CI、Packaging、升级与遗留清理

## 范围

```text
optional dependency boundaries
extras/package layout
wheel/sdist
fresh venv
Python version matrix
real backend CI
security/fault/soak gates
migration guide
legacy crypto/cache/auth removal
```

## Release Gate

```text
unit
integration
contract
security
concurrency
fault selected
OpenAPI/SDK
wheel/sdist
fresh install
generated project smoke
upgrade/migration
```

Nightly 增加 load/soak/full stateful。

---

# PR 纪律

1. 每个 PR 只完成一个可独立验收的子阶段。
2. 不把后续阶段“顺手实现”进当前 PR。
3. PR 正文列出对应 ADR、测试合同和明确不做内容。
4. 运行时实现前先写失败测试或合同测试。
5. Codex 不自行合并；独立验收后再进入下一阶段。
6. 任何公共 API 变化必须更新 OpenAPI/ADR/迁移说明。

# 第一施工入口

研究收敛 PR 合并后，第一段运行时代码应从 **C1 请求执行基础与生命周期** 开始，而不是直接写 JWT、Redis 或 ORM。

原因：认证、数据库、幂等、Schema、扩展和审计都依赖统一 Context、Deadline、Lifecycle 和编译后的 RoutePolicy。