# 扩展系统、依赖注入、事件、可观测性与测试横向对比

> 状态：Phase C0 研究稿，不是最终运行时实现。
>
> 样本：NestJS Providers/Lifecycle、ASP.NET Core DI、Spring Bean Scopes/Application Events、Symfony EventDispatcher、Django Signals、CloudEvents、OpenTelemetry、W3C Trace Context、OWASP Logging、pytest、Hypothesis、Testcontainers。

## 研究目标

LingShu API 需要在“核心小而稳定”和“扩展能力强”之间建立明确边界，解决：

1. 扩展如何注册、排序、启动、回滚和关闭；
2. 依赖注入如何避免隐藏依赖、作用域泄漏和 Service Locator；
3. 同步本地事件、事务后事件、耐久领域事件和审计日志如何区分；
4. Trace、Metrics、Logs 如何统一关联；
5. 如何控制日志敏感数据和指标高基数；
6. 如何建立真实数据库、并发、属性测试和故障注入体系；
7. 第三方扩展如何证明兼容性而不破坏框架核心。

---

# 一、NestJS Providers 与生命周期

## 值得吸收

NestJS 将依赖映射为 provider token，可通过 class、value、factory、alias 等方式注册；模块显式声明 providers 和 exports。其依赖图在启动阶段分析，并按依赖顺序解析。

生命周期提供初始化、运行、终止阶段和对应 Hook，使模块、Provider 与 Controller 能在启动和关闭时执行受管逻辑。

## LingShu 裁决

`adapt`

- 使用稳定 token/协议注册服务，不要求 token 必须是具体实现类；
- 支持 class、instance、factory、alias 四类 provider；
- 模块显式声明 exports，不允许所有 provider 自动全局可见；
- 依赖图启动时编译，循环依赖默认报错；
- async 初始化放入 lifecycle，不放入构造函数；
- provider factory 只能负责构造，长耗时连接和 readiness 进入 `start/ready`；
- 测试可按 token 替换 provider，但生产覆盖必须显式授权。

---

# 二、ASP.NET Core DI

## 值得吸收

ASP.NET Core 区分 singleton、scoped、transient，并提供 scope validation，能够发现 singleton 捕获 scoped service 的生命周期错误。官方还建议避免 Service Locator、静态访问容器、配置阶段重复 Build Container，并提醒 Container 线程安全不代表解析出的 Singleton 对象本身线程安全。

## LingShu 裁决

`adopt/adapt`

LingShu 候选作用域：

```text
application
worker
request
operation
transient
```

规则：

- application provider 不得直接依赖 request/operation provider；
- request provider 在请求结束时统一释放；
- background task 需要显式创建自己的 operation scope；
- scope validation 在启动和测试中默认开启；
- 禁止业务代码随处 `container.get()`；
- 构造函数/声明式依赖优先，动态解析只允许框架适配器和工厂；
- 可释放对象由创建它的 scope 负责关闭；
- Singleton 持有可变状态时必须自行保证并发安全。

---

# 三、Spring Bean Scopes

## 值得吸收

Spring 支持 singleton、prototype、request、session、application、websocket 等作用域，说明对象生命周期应由容器配置而不是硬编码在类中。

## LingShu 裁决

`adapt`

- Python API 框架暂不引入 session/websocket 完整 DI scope，但保留可扩展 scope protocol；
- request scope 与 ContextVar 请求上下文配合，但对象释放必须由 Scope 管理而非依赖垃圾回收；
- prototype/transient provider 每次构造，不自动承担资源关闭；
- application scope 默认共享，不能依赖 request context；
- 自定义 scope 作为高级扩展，需要唯一名称、enter/exit、dispose 和并发语义。

---

# 四、Extension Manifest 与依赖图

LingShu 扩展候选 Manifest：

```text
name
version
framework_version_range
requires
optional_requires
provides
conflicts
priority
configuration_schema
capabilities
```

生命周期：

```text
configure
setup
start
ready
drain
stop
close
health
```

要求：

- `configure` 解析配置，无外部副作用；
- `setup` 注册 provider、route、schema、event subscriber；
- `start` 建立连接或启动任务；
- `ready` 完成自检后才允许应用 ready；
- `drain` 停止接收新工作；
- `stop/close` 释放运行资源；
- 初始化失败按已完成步骤逆序回滚；
- 强依赖拓扑排序，循环立即失败；
- optional dependency 缺失只能关闭可选功能，不改变核心安全默认值；
- 同一 capability 多实现时必须有显式选择或优先级冲突错误。

---

# 五、本地事件系统：Spring、Symfony 与 Django

## Spring Application Events

Spring 默认同步调用 Listener，发布方法会等待 Listener 完成；同步 Listener 可共享发布者当前事务上下文。异步化后线程本地上下文不自动传播。

### LingShu 裁决

- `LocalEventBus` 默认同步、进程内、非耐久；
- Listener 失败默认向发布者传播，除非事件策略声明隔离；
- 同步 Listener 不允许执行长时间网络调用；
- 需要事务提交后触发时使用 `after_commit`；
- 异步 Listener 必须进入受管 TaskGroup/Operation，显式传播 trace/tenant，不能直接裸 create_task。

## Symfony EventDispatcher

Symfony 支持 Listener Priority、Subscriber 和 stop propagation。

### LingShu 裁决

- 生命周期和框架 Hook 可使用明确 priority；
- 相同 priority 的顺序必须稳定；
- Domain Event 不允许 Listener 随意 stop propagation，因为会让业务结果依赖隐藏顺序；
- stop propagation 仅保留给可中断的框架 Filter/Hook，且进入文档和测试；
- Event Subscriber 在启动时注册并可检查，不通过 import 副作用偷偷注册。

## Django Signals

Django Signal Receiver 按注册顺序调用，默认使用弱引用，并通过 dispatch UID 防止重复连接。Signal 可同步或异步发送。

### LingShu 裁决

- 不采用弱引用 Listener 默认值，扩展注册生命周期必须明确；
- 每个 subscriber 需要稳定 subscriber_id，防止重复注册；
- 禁止因模块重复导入而重复订阅；
- Receiver 参数合同版本化，不依赖任意 `**kwargs` 作为长期公共协议；
- Signal/Event 仅用于解耦，不用于隐藏关键业务流程。

---

# 六、四种“事件”必须分开

## 1. Lifecycle Hook

框架启动、请求前后、关闭等可排序 Hook。

特点：

- 进程内；
- 同步或受控异步；
- 可失败并阻止生命周期继续；
- 不是业务事件。

## 2. Local Application Event

同一进程模块解耦，例如缓存失效提示、内存指标更新。

特点：

- 不耐久；
- 默认同步；
- 不能作为跨服务事实来源。

## 3. Durable Domain/Integration Event

订单创建、素材生成完成等需要可靠传递的业务事实。

特点：

- 有 event_id、version、occurred_at；
- 通过 Outbox 与数据库事务协调；
- 至少一次投递，消费者必须幂等；
- 可跨进程、跨语言；
- 使用稳定 Schema 和兼容规则。

## 4. Audit Record

记录谁在什么时候对什么资源做了什么以及结果。

特点：

- 安全与合规用途；
- 追加式；
- 不由普通 Listener 决定是否存在；
- 不能等同普通 Debug Log；
- 不能被业务 Event 的重试产生重复含义。

---

# 七、CloudEvents

## 值得吸收

CloudEvents 规定事件上下文属性独立于数据，可在不解析 payload 的情况下路由和检查；必需属性包括 specversion、id、source、type，并支持 subject、time、datacontenttype、dataschema 等扩展。

## LingShu 裁决

`adapt`

耐久事件 Envelope 候选：

```json
{
  "specversion": "1.0",
  "id": "evt_...",
  "source": "lingshu://orders",
  "type": "orders.order.created.v1",
  "subject": "order/1001",
  "time": "...",
  "datacontenttype": "application/json",
  "dataschema": "...",
  "tenantid": "...",
  "traceparent": "...",
  "operationid": "...",
  "data": {}
}
```

规则：

- event id 全局唯一；
- type 带稳定版本或 Schema version；
- source 表示产生事件的逻辑组件，不用临时 Pod 地址；
- payload 不直接塞 ORM 实体；
- tenant、trace、operation 作为受控 extension；
- 敏感信息和凭据禁止进入事件 metadata；
- Consumer 以 event_id + consumer_name 去重。

---

# 八、审计记录

候选审计字段：

```text
audit_id
occurred_at
recorded_at
actor_type
actor_id
client_id
tenant_id
action
resource_type
resource_id
result
reason_code
request_id
trace_id
operation_id
source_ip_hash/user_agent_summary
before_digest
after_digest
metadata
```

原则：

- 记录 when/where/who/what/result；
- 默认不记录密码、token、secret、完整签名、支付敏感数据和大正文；
- 高风险变更可保存字段级差异，但先脱敏或摘要；
- 登录失败、权限拒绝、配置修改、密钥轮换、数据导入导出、管理员跨租户访问必须审计；
- 审计写失败对高风险路由默认 fail-closed 或进入可靠缓冲，不能静默丢失；
- 防篡改可采用 hash chain、WORM/只追加存储或外部审计 Sink；
- 读取审计日志本身也要审计。

---

# 九、OpenTelemetry 与 W3C Trace Context

## 值得吸收

OpenTelemetry 将 Traces、Metrics、Logs 和 Baggage 作为关联信号；Context Propagation 通过服务间注入和提取 trace context 保持因果链。W3C Trace Context 定义 `traceparent` 和 `tracestate` 的跨供应商传播规则。

## LingShu 裁决

`adopt`

- 默认采用 W3C Trace Context；
- 入站解析有效 traceparent，非法值丢弃并创建新 Trace；
- 出站 HTTP、事件和未来任务合同注入 Trace Context；
- 日志加入 trace_id/span_id/request_id/operation_id；
- 使用 OpenTelemetry Semantic Conventions 命名 HTTP、DB、RPC 等属性；
- 自定义属性使用 `lingshu.*` 命名空间；
- Baggage 不放 secret、token、完整 user profile 或高基数大字段；
- 不信任外部 Baggage 作为权限或 tenant 事实；
- Trace Context 只用于关联，不用于认证。

---

# 十、Metrics 与高基数控制

核心指标：

```text
http.server.request.duration
http.server.active_requests
http.server.errors
security.denied
idempotency.conflict
rate_limit.rejected
db.pool.in_use
db.pool.waiters
db.operation.duration
queue.depth
queue.dropped
circuit_breaker.state
extension.health
```

规则：

- metric label 禁止 user_id、request_id、trace_id、完整 URL、任意 resource_id；
- route 使用模板，不使用实际路径；
- tenant 维度只在明确受控规模和配置开启时使用；
- 错误码允许稳定有限枚举，不记录任意 exception message；
- Histogram bucket 与单位固定；
- 指标采集失败不阻塞主业务，但需要自监控。

---

# 十一、Logs

采用结构化 LogRecord，不再以字符串拼接作为唯一日志形式。

候选字段：

```text
timestamp
severity
event_name
message
service.name/service.version
request_id
trace_id/span_id
operation_id
tenant_id_hash
route
error_code
safe_attributes
```

原则：

- 日志与 Trace 可直接关联；
- Logger Adapter 自动加入上下文；
- SQL、Mongo filter、Redis key 记录安全摘要；
- 参数和 payload 默认不全量记录；
- 日志注入字符进行清洗；
- 生产关闭高噪 Debug，安全事件不允许完全关闭；
- 日志输出失败不能递归产生无限日志。

---

# 十二、测试体系

## 1. Unit

纯函数、Schema、Policy、Query 编译、错误映射。

## 2. Component

单个 extension/backend 使用 fake dependencies，验证生命周期与合同。

## 3. Integration

使用真实 MySQL/SQLite/MongoDB/Redis 或容器实例，不以 Mock Driver 替代数据库语义。

## 4. Contract

- Backend contract；
- Extension contract；
- OpenAPI/SDK contract；
- Event Schema compatibility；
- Trace/metric attribute contract。

## 5. Property / Stateful

使用 Hypothesis 生成：

- 任意 Query 表达式；
- PATCH 三态组合；
- 幂等状态转换；
- 事务/savepoint 序列；
- Extension install/start/fail/rollback/stop；
- Queue/lock/lease 状态机。

Invariant 示例：

```text
关闭后无已注册资源
同幂等键最多一个 owner
回滚后数据库状态不变
Extension setup 失败后容器无残留 provider
```

## 6. Concurrency

使用 barrier/event 控制交错，不依赖随机 sleep：

- 100/1000 并发 ContextVar 隔离；
- 事务不串线；
- 重复幂等只执行一次；
- shutdown 与请求并发；
- subscriber 注册与 dispatch 并发。

## 7. Fault Injection

注入：

- DB commit 前后断连；
- Redis 超时；
- Event listener 失败；
- extension start 第 N 步失败；
- telemetry exporter 阻塞；
- task cancellation；
- process SIGTERM。

## 8. Load / Soak

- 连接池耗尽；
- Event loop lag；
- 内存增长；
- 队列积压；
- 24/72 小时连接重建和资源泄漏；
- 多次热重启/零停机重启。

## 9. Security

- 权限负向矩阵；
- Mass assignment；
- SQL/NoSQL/operator 注入；
- Signature canonicalization；
- 日志敏感信息扫描；
- malicious baggage/header；
- 高基数指标攻击。

---

# 十三、pytest、Hypothesis 与 Testcontainers

## pytest

- 资源 fixture 使用 `yield`，teardown 逆序执行；
- 一个 fixture 尽量只做一个可回滚状态变化；
- fixture scope 明确，避免 session fixture 泄漏跨测试状态；
- 失败清理必须经过专门测试；
- 真实时间、随机数、UUID、环境变量由 fixture 注入。

## Hypothesis

- State machine 用于状态转换复杂组件；
- invariant 在每一步后验证；
- 失败序列自动缩减，保留回归样例；
- 生成输入设置大小和性能上限，避免把 property test 变成长时间 fuzz。

## Testcontainers

- 数据库和消息组件使用真实容器；
- 容器按模块/session 复用，数据按测试隔离；
- 明确 cleanup，不依赖隐含后台清理；
- CI 无 Docker 环境时测试必须明确 skip/fail policy；
- 版本固定，避免 `latest` 导致漂移。

---

# 十四、明确拒绝

- 所有 Provider 全局单例；
- Singleton 捕获 request/operation 对象；
- 业务随处调用 Service Locator；
- async 连接建立放在构造函数；
- 扩展通过 import 副作用注册；
- 依赖循环时延迟到运行中才报错；
- 本地 Event 作为耐久业务事实；
- Listener 隐藏核心业务流程；
- Domain Event 允许 stop propagation；
- 普通日志代替审计；
- Trace/Baggage 作为认证或权限依据；
- metric label 使用 user_id/request_id；
- 测试只用 Mock DB；
- 并发测试依赖 sleep 碰运气；
- Extension 启动失败后不做逆序回滚。

---

# 十五、必须验证的测试

1. Provider scope validation；
2. singleton 不得依赖 request scope；
3. request/operation scope 正确 dispose；
4. container override 只在测试或显式配置生效；
5. Extension DAG 拓扑和循环检测；
6. start 第 N 步失败逆序 rollback；
7. optional dependency 缺失行为稳定；
8. Subscriber 不重复注册；
9. Local event listener 顺序和错误传播；
10. after_commit 事件仅成功提交后产生；
11. Outbox 事件重复投递消费者幂等；
12. audit 必填字段、脱敏与防丢策略；
13. W3C traceparent 解析和传播；
14. invalid trace context 安全重建；
15. logs/traces 通过 trace_id 关联；
16. metric cardinality 限制；
17. telemetry exporter 故障不拖死请求；
18. Testcontainers 真实后端合同测试；
19. Hypothesis 状态机验证事务/幂等/扩展不变量；
20. fixture teardown 在测试异常时仍执行；
21. 故障注入后无资源泄漏；
22. 72 小时 soak 指标无持续增长。

## 官方资料

- NestJS Custom Providers: https://docs.nestjs.com/fundamentals/custom-providers
- NestJS Lifecycle Events: https://docs.nestjs.com/fundamentals/lifecycle-events
- .NET Dependency Injection: https://learn.microsoft.com/en-us/dotnet/core/extensions/dependency-injection/overview
- .NET DI Guidelines: https://learn.microsoft.com/en-us/dotnet/core/extensions/dependency-injection/guidelines
- Spring Bean Scopes: https://docs.spring.io/spring-framework/reference/core/beans/factory-scopes.html
- Spring Application Events: https://docs.spring.io/spring-framework/reference/core/beans/context-introduction.html
- Symfony EventDispatcher: https://symfony.com/doc/current/components/event_dispatcher.html
- Django Signals: https://docs.djangoproject.com/en/5.2/topics/signals/
- CloudEvents Specification: https://github.com/cloudevents/spec/blob/main/cloudevents/spec.md
- OpenTelemetry Signals: https://opentelemetry.io/docs/concepts/signals/
- OpenTelemetry Context Propagation: https://opentelemetry.io/docs/concepts/context-propagation/
- OpenTelemetry Semantic Conventions: https://opentelemetry.io/docs/specs/semconv/
- OpenTelemetry Logs: https://opentelemetry.io/docs/specs/otel/logs/
- W3C Trace Context: https://www.w3.org/TR/trace-context/
- OWASP Logging Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
- pytest Fixtures: https://docs.pytest.org/en/stable/how-to/fixtures.html
- Hypothesis Stateful Testing: https://hypothesis.readthedocs.io/en/latest/stateful.html
- Testcontainers Python Guide: https://testcontainers.com/guides/getting-started-with-testcontainers-for-python/
