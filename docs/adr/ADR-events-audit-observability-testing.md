# ADR：事件、审计、可观测性与测试基线

- 状态：Draft
- 阶段：Phase C0 研究
- 范围：LingShu API 进程内事件、耐久事件、审计、OpenTelemetry 和质量门禁

## 背景

事件、日志、审计和 Trace 经常被混用：

- 用本地 Signal 代替可靠消息；
- 用 Debug Log 代替审计记录；
- 事件 Listener 隐藏关键业务副作用；
- Trace Context 被误当身份凭据；
- 指标标签包含用户或请求 ID，造成高基数；
- 测试只使用 Mock，无法发现数据库、连接池和并发语义问题。

## 决策

明确分离：

```text
Lifecycle Hook
Local Event
Durable Domain/Integration Event
Audit Record
Telemetry Signal
```

并建立统一测试基线。

## LocalEventBus

候选接口：

```python
await events.publish_local(
    CacheInvalidated(...),
    policy="fail_fast",
)
```

语义：

- 进程内；
- 默认同步；
- 不持久；
- Listener 顺序由 priority + registration order 决定；
- 默认 Listener 异常向发布者传播；
- 不用于关键跨进程事实。

策略：

```text
fail_fast
collect_errors
best_effort
```

`best_effort` 仅用于非关键遥测或缓存提示。

Domain Event 不支持 stop propagation。可中断传播只用于框架 Hook，并必须显式声明 `cancellable=True`。

## After Commit Event

事务内业务事件：

```python
async with db.transaction():
    order = await Order.create(...)
    events.after_commit(OrderCreated.from_order(order))
```

规则：

- 最外层 commit 成功后才发布；
- rollback/savepoint 回滚时丢弃对应事件；
- 本地 after_commit 仍不保证进程崩溃后的可靠传递；
- 需要可靠传递时使用 Outbox。

## Durable Event / Outbox

写入流程：

```text
business transaction
├── business rows
└── outbox event row
commit
    ↓
outbox publisher
    ↓
message transport
```

事件状态：

```text
pending
publishing
published
failed
dead
```

要求：

- Outbox 与业务记录同事务；
- Publisher 使用 lease/owner，支持崩溃恢复；
- transport 至少一次投递；
- Consumer 用 event_id + consumer_id 幂等；
- Event Schema 有版本和兼容测试；
- 不承诺“恰好一次”副作用。

## CloudEvent Envelope

候选公共合同：

```text
specversion
id
source
type
subject
time
datacontenttype
dataschema
traceparent
tenantid
operationid
data
```

- `id` 全局唯一；
- `type` 使用稳定命名和版本；
- `source` 为逻辑组件；
- `subject` 为资源定位；
- extension attribute 采用小写稳定名称；
- data 由独立 JSON Schema 描述；
- metadata 不含 secret/token。

## AuditSink

审计不依赖普通 Event Listener 是否成功注册。

候选：

```python
await audit.record(
    action="orders.order.cancel",
    resource=order,
    result="denied",
    reason_code="order.state.invalid",
)
```

审计等级：

```text
none
basic
security
critical
```

关键接口在 RoutePolicy 中声明审计等级。

### critical

- 审计 Sink 不可用时默认拒绝操作或写入可靠本地缓冲；
- 不允许静默丢弃；
- 缓冲容量和磁盘预算受限；
- 恢复后补送并去重。

### basic/security

- 按配置 fail-closed 或 fail-open-with-alert；
- 任何降级必须产生高等级告警。

## 审计内容安全

记录：

```text
actor/client/tenant
action/resource/result/reason
request/trace/operation
source summary
before/after safe diff or digest
```

不记录：

```text
password
access/refresh token
API secret
private key
full signature
sensitive payment data
full request body by default
```

字段差异通过 Schema 的 sensitivity metadata 脱敏。

## Telemetry

采用 OpenTelemetry API/SDK 边界：

```text
Traces
Metrics
Logs
Context Propagation
```

### Trace

入站：

- 解析 W3C `traceparent/tracestate`；
- 非法 Header 丢弃并新建 Trace；
- 不信任外部 Span 名称或 Baggage 为安全事实。

出站：

- HTTP/RPC/Event/Task 注入上下文；
- async child task 继承受控 Context；
- thread/process 边界显式传播允许字段。

### Span

至少覆盖：

```text
HTTP request
security stages
database operation
external HTTP/RPC
cache/lock
outbox publish
extension lifecycle
```

避免记录 SQL 参数、Token 和完整 payload。

### Metrics

指标标签必须来自低基数集合：

```text
route template
method
status class
error code
backend name
extension name
```

禁止：

```text
user_id
request_id
trace_id
resource_id
raw URL
exception message
```

### Logs

结构化日志自动关联：

```text
trace_id
span_id
request_id
operation_id
```

Telemetry exporter 必须使用有界队列和超时；Exporter 故障不允许无限阻塞请求。

## Sampling

- Metrics 不采样；
- Trace 支持 head sampling，后续可接 Collector tail sampling；
- 安全审计不受 Trace sampling 影响；
- Error Trace 可提高采样，但不能把秘密附加到 Span；
- sampling 配置变更需要审计。

## Testing Baseline

### 必跑快速套件

```text
unit
schema/contract
security negative
backend fake contract
extension lifecycle
```

### PR 集成套件

```text
real MySQL/SQLite/Redis/MongoDB
HTTP integration
OpenAPI/SDK build
concurrency deterministic tests
fault injection selected cases
```

### Nightly/Release

```text
load
soak
full property/stateful
multi-worker
shutdown/restart
package/fresh venv
upgrade/migration
security scans
```

## Real Dependency Testing

- SQLite 测试不能替代 MySQL 事务和方言；
- Memory Redis fake 不能替代 Lua/TTL/Stream/故障切换；
- Mongo Mock 不能替代索引、validator 和 transaction；
- 每个 Backend 提供真实容器合同测试；
- 可选依赖未安装时，未启用后端测试和框架启动仍正常。

## Determinism

测试注入：

```text
Clock
UUID generator
Random source
Retry jitter
Scheduler
Network fault controller
```

禁止核心测试依赖真实 `sleep()` 和墙上时钟碰运气。

并发测试使用 barrier、event、fake clock 控制交错。

## Property / Stateful Testing

优先对象：

```text
Idempotency state machine
Transaction/savepoint
Extension lifecycle rollback
Queue full modes
Lock/lease/fencing
Schema PATCH tri-state
Event consumer deduplication
```

每个状态机定义 invariant 和可接受终态。

## Fault Injection Interface

测试专用 fault points：

```text
before_db_commit
after_db_commit_before_response
before_outbox_mark_published
extension_start_step
telemetry_export
redis_reserve
shutdown_drain
```

Fault point 不进入生产公共 API；构建/配置必须确保生产默认关闭。

## Test Cleanup

- fixture 使用 yield/finalizer 逆序清理；
- 每个 fixture 尽量只改变一个状态；
- 测试失败、取消、超时时仍清理；
- 残留容器、任务、连接、临时文件检测为测试失败；
- Session 级资源也要验证测试间数据隔离。

## Contract Compatibility

### Extension

- Manifest 与生命周期协议；
- Provider scope；
- Health；
- Telemetry hooks；
- Error taxonomy。

### Event

- Schema backward/forward policy；
- required field 变更；
- enum 扩展；
- version migration；
- unknown field tolerance。

### Telemetry

- metric/span 名称稳定；
- 单位和 attribute 类型；
- cardinality budget；
- Dashboard/alert 依赖检查。

## 被拒绝方案

- Signal 代替 Outbox；
- 普通日志代替审计；
- Listener 决定是否记录关键审计；
- Domain Event stop propagation；
- 宣传 exactly-once；
- Trace/Baggage 参与权限判断；
- 高基数指标；
- Telemetry exporter 无界缓冲；
- 只用 Fake DB；
- 并发测试用 sleep；
- Fault injection 生产默认可调用；
- 测试完成后不检查资源残留。

## 验收条件

1. Local/AfterCommit/Outbox/Audit 类型边界清晰；
2. rollback 不发布 after_commit event；
3. Outbox 崩溃恢复不丢事件；
4. Consumer 重复事件只产生一次业务副作用；
5. critical audit sink 故障策略正确；
6. 审计无敏感数据；
7. W3C Trace Context 跨 HTTP/Event 保持关联；
8. Telemetry exporter 故障不会拖死请求；
9. 指标高基数字段被拒绝；
10. 真实四类数据库集成测试；
11. 属性测试可缩减失败序列；
12. 故障注入覆盖 commit unknown 和 extension rollback；
13. 测试后 TaskRegistry、连接池和临时资源清空；
14. Release 套件包含 fresh venv、wheel/sdist 和生成项目冒烟。