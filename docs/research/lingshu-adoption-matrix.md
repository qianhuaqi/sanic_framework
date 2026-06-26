# LingShu 全球框架取经总裁决矩阵

> 状态：Phase C0 收敛稿。
>
> 目的：将前六批研究从“参考材料”收敛为 LingShu API 的明确架构决策，供 Phase C–F 实施与验收使用。

## 裁决定义

```text
adopt      直接采用为 LingShu 原则
adapt      吸收机制，按 Sanic/Python/异步场景改造
extension  通过内置或第三方扩展提供，不进入最小核心
reject     明确拒绝
later      有价值，但当前 API 主线暂缓
```

裁决不是评价框架优劣，而是判断某项机制是否适合当前 LingShu API。

---

# 一、请求与安全

| 能力 | 参考机制 | 裁决 | LingShu 决定 |
|---|---|---|---|
| 编译后的 RoutePolicy | NestJS Guard、Spring Security、Symfony Firewall | adopt | 全局/蓝图/路由配置在启动时编译；运行时执行冻结策略 |
| 固定安全执行链 | Spring Security、NestJS | adopt | transport → maintenance → rate → signing → authn → tenant → authz → validation → idempotency → handler |
| Authentication / Authorization 分离 | Spring Security、Laravel Policy | adopt | 认证只生成 Principal；Gate/Policy 独立决定资源动作 |
| 多认证器降级规则 | Symfony Firewall | adapt | 只有 not_applicable 可继续；invalid/expired/revoked 立即失败 |
| RBAC | Django、Casbin | adopt | 核心提供简单权限与角色；稳定命名 `module.resource.action` |
| ABAC/ReBAC/外部策略引擎 | Casbin/OPA 类机制 | extension | 核心只提供 Policy Protocol；复杂引擎外置 |
| Tenant Context | 多租户安全实践 | adopt | tenant 必须来自已认证身份/API key/signing key 的可信绑定 |
| HMAC 请求签名 | AWS SigV4、GitHub Webhook | adapt | versioned canonical request + HMAC-SHA256 + raw-body digest + timestamp + nonce |
| Replay protection | AWS/GitHub | adopt | 独立 ReplayStore；nonce 原子 reserve；与幂等完全分开 |
| 幂等状态机 | Stripe | adapt | processing/succeeded/failed/unknown；同 key 不同 fingerprint 冲突；不默认缓存全部 500 |
| RateLimiter | NestJS Throttler | adopt | 多窗口、多维 tracker；trusted proxy 显式配置 |
| ConcurrencyLimiter | Tower/Resilience4j Bulkhead | adopt | 与速率限制分离；支持全局/路由/租户/依赖隔舱 |
| 自定义 Body 加密 | 旧 DES/自定义协议 | reject | 核心删除；确有需要时仅提供 AEAD 扩展协议 |
| 无效强认证自动降级到弱认证 | 常见错误做法 | reject | 安全失败立即终止 |

---

# 二、数据库与数据访问

| 能力 | 参考机制 | 裁决 | LingShu 决定 |
|---|---|---|---|
| 统一入口 + 独立后端 | Ent/Prisma 体验 + 数据库原生差异 | adopt | `db` facade + connection alias + backend registry + capabilities |
| 万能 ORM 统一 SQL/Mongo/Redis | 常见大杂烩设计 | reject | SQL ORM、Mongo ODM、Redis Capability Facade 分离 |
| MySQL 与 SQLite 共用实现分支 | 轻量方言封装 | reject | 可共享表达式合同，但 driver/pool/dialect/transaction/migration 独立 |
| 简单 CRUD | Rails/Eloquent/Django | adopt | Model API 保持简洁、链式、可读 |
| 显式事务 / Unit of Work | SQLAlchemy/Doctrine/EF Core | adapt | 短生命周期 UoW；同一事务同一连接；ContextVar 隔离 |
| 嵌套事务 | Django/jOOQ/Drizzle | adopt | 外层真事务，内层 savepoint；能力不支持时明确报错 |
| after_commit | Django | adopt | 最外层 commit 成功后执行；回滚不触发 |
| Identity Map | SQLAlchemy/Doctrine | adapt | 事务作用域内可用；不暴露完整复杂实体状态机 |
| 自动 Change Tracking | EF Core/Doctrine | later | 可选，不作为第一阶段唯一写法 |
| Lazy Loading | Hibernate/Rails | reject 默认 | 默认 strict loading；关联必须显式 preload |
| Optimistic Lock | Hibernate/Rails | adopt | version 字段、影响行数检查、稳定 Conflict 错误 |
| SQL-first Repository | jOOQ/SQLx/sqlc | adopt | 复杂报表、CTE、窗口函数、批量更新走命名 SQL/Repository |
| 任意 Raw SQL 字符串 | 传统 escape hatch | reject | 仅受控 raw/native；仍执行参数化、超时、审计、租户和脱敏 |
| Migration | Django/Prisma/Doctrine | adopt | 每个 SQL backend 独立 migration/dialect；支持 status/rollback/check |
| MongoDB DocumentModel | MongoDB 官方机制 | extension | 独立 ODM、Schema version、validator、projection、index、aggregation |
| Mongo 原始 filter/pipeline 直通客户端 | 常见 NoSQL 注入风险 | reject | operator/stage/字段白名单和预算 |
| Redis ORM | 非自然抽象 | reject | 只提供 Cache/Lock/Limiter/Idempotency/Operation/Stream 等能力 |
| Redis 分布式锁作为最终正确性 | 常见误用 | reject | owner+TTL；关键写结合 unique/version/fencing |
| 新数据库扩展 | 插件架构 | adopt | 新 backend 只实现协议、capabilities 和合同测试，不修改现有后端 |

---

# 三、Schema、验证与合同

| 能力 | 参考机制 | 裁决 | LingShu 决定 |
|---|---|---|---|
| Pydantic | Pydantic v2 | adapt | 第一版引擎候选；通过 `lingshu.schema` facade 隔离内部格式 |
| Transport/Input/Domain/Persistence/Output 分层 | Ecto、ASP.NET ViewModel、FastAPI Response Model | adopt | 五层模型边界，允许共享字段片段但不共用万能类 |
| 公共输入 extra ignore | Pydantic 默认 | reject | InputSchema 默认 `extra=forbid` |
| Mass Assignment | Eloquent 防护、Ecto cast | reject 原始写法 | 禁止 `Model(**request.json)`；InputSchema 即可写字段白名单 |
| Body 严格、Query 受控转换 | Pydantic/ASP.NET Model Binding | adopt | 不同来源使用不同 Validation Profile |
| PATCH 三态 | Pydantic fields_set / API 语义 | adopt | MISSING/NULL/VALUE 明确区分 |
| Validator 查询 DB/网络 | 常见验证耦合 | reject | Schema validator 默认纯函数；业务约束和数据库 constraint 单独处理 |
| Output Schema | FastAPI/Symfony Serializer | adopt | 所有正式接口声明输出合同；始终过滤字段 |
| Duck typed 输出 | Pydantic serialize_as_any | reject 默认 | 实际子类字段不自动输出，防止敏感字段泄漏 |
| JSON Schema 2020-12 | JSON Schema | adopt | canonical Schema 标准 |
| OpenAPI 3.1 | OpenAPI | adopt | canonical API 文档；3.0 仅兼容导出 |
| TypeScript SDK | OpenAPI codegen | adopt | 从同一合同生成类型、Client、错误和可选 Zod |
| 前端独立手写 Zod/Pydantic 合同 | 双事实源 | reject | 前端 Schema 是生成物 |
| Contract Diff | API 兼容治理 | adopt | CI 检测 operationId、必填、类型、enum、安全要求等 breaking change |
| 所有 API 自动暴露 AI/MCP | AI 工具自动化误用 | reject | 显式 tool metadata、风险、确认、权限和审计 |

---

# 四、并发、韧性与生命周期

| 能力 | 参考机制 | 裁决 | LingShu 决定 |
|---|---|---|---|
| Structured Concurrency | asyncio TaskGroup、AnyIO、errgroup | adopt | 请求子任务必须有 owner；作用域退出前完成或取消并等待 |
| 裸 create_task | 常见异步泄漏 | reject | 背景任务进入 TaskRegistry 或 Operation/Worker |
| Cancel propagation | asyncio/AnyIO/Go context | adopt | 向子任务、HTTP、DB wait、锁、队列和池传播 |
| 吞 CancelledError | 异步反模式 | reject | 清理后重新抛出；测试检测 |
| 绝对 Deadline | Go context/AnyIO | adopt | 各层只消费剩余预算，不重新获得完整 timeout |
| Bounded Queue | .NET Channels | adopt | capacity/full_mode/put_timeout 必须显式；生产默认有界 |
| Partitioned Concurrency | Actor/CSP/工作队列经验 | adapt | 同业务 key 串行，不同 key 并行；支持公平与回收 |
| Retry | Resilience 模式 | adapt | 只重试安全或幂等操作；单层负责；总预算、退避和 jitter |
| CircuitBreaker | Resilience4j | adopt | 系统错误/慢调用统计；CLOSED/OPEN/HALF_OPEN |
| CircuitBreaker 代替并发限制 | 常见误解 | reject | 必须配合 Bulkhead/ConcurrencyLimiter |
| Bulkhead | Resilience4j/Tower | adopt | 数据库、Redis、Mongo、AI、邮件等关键依赖独立隔舱 |
| Load Shedding | Tower | adopt | 队列/资源饱和时快速拒绝，不无限排队 |
| CPU 工作跑在 API event loop | 常见错误 | reject | 小任务进受控进程池，长任务进入未来 lingshu-ms |
| Managed Lifecycle | Sanic/NestJS/Kubernetes | adopt | configure/setup/start/ready/drain/stop/close |
| Graceful Shutdown | Kubernetes/Sanic | adopt | readiness=false → 停新流量 → drain → checkpoint → 逆序关闭 |
| Shutdown 仅 cancel 不 await | 常见错误 | reject | 必须等待取消完成并报告残留 |

---

# 五、扩展与依赖注入

| 能力 | 参考机制 | 裁决 | LingShu 决定 |
|---|---|---|---|
| Extension Manifest | NestJS 模块/插件生态 | adopt | name/version/requires/provides/conflicts/config/capabilities |
| Dependency DAG | DI 容器/包管理 | adopt | 启动时拓扑排序；循环立即失败；逆序回滚/关闭 |
| Provider scopes | ASP.NET/Spring | adapt | application/worker/request/operation/transient |
| Scope validation | ASP.NET Core | adopt | 长生命周期不得捕获短生命周期对象 |
| Service Locator | DI 反模式 | reject 普通业务 | 只允许框架工厂、扩展 setup 和测试 harness 动态解析 |
| Async constructor | 常见反模式 | reject | 构造只建立对象；连接进入 start/ready |
| Import side-effect registration | Django/插件常见风险 | reject | 注册必须显式且可撤销 |
| 第三方 entry points 自动发现 | Python 插件生态 | adapt | 可发现但不自动启用；项目配置显式启用 |
| 可选扩展缺失拖垮核心 | 重依赖耦合 | reject | disabled backend 不导入重依赖、不影响启动 |

---

# 六、事件、审计与可观测性

| 能力 | 参考机制 | 裁决 | LingShu 决定 |
|---|---|---|---|
| Lifecycle Hook | Symfony/NestJS | adopt | 可排序、可失败、属于框架生命周期 |
| Local Event | Spring/Django Signal | adapt | 进程内、默认同步、不耐久；不能作为可靠业务事实 |
| Domain Event stop propagation | Symfony 可中断事件 | reject | 业务事件不能被隐藏 Listener 中断 |
| After-commit Event | Django/Spring 事务事件 | adopt | 最外层事务提交后触发 |
| Durable Event / Outbox | 可靠消息模式 | adopt | 业务数据与 Outbox 同事务；消费者幂等；不宣传 exactly-once |
| CloudEvents Envelope | CloudEvents | adapt | 稳定 id/source/type/subject/time/schema + tenant/trace/operation 扩展 |
| 普通日志代替审计 | 常见误用 | reject | AuditSink 独立、追加式、高风险操作可靠记录 |
| OpenTelemetry | OTel | extension + core hooks | 核心提供观测 Hook/上下文；OTel SDK/exporter 可选扩展 |
| W3C Trace Context | W3C | adopt | HTTP/Event/Task 传播；仅用于关联，不用于身份和权限 |
| 高基数 Metric Labels | 常见监控事故 | reject | 禁止 user_id/request_id/trace_id/resource_id/raw URL |
| 无界 Telemetry Buffer | 常见故障放大 | reject | 有界队列、超时、批量与自监控 |

---

# 七、测试、发布与质量门禁

| 能力 | 参考机制 | 裁决 | LingShu 决定 |
|---|---|---|---|
| pytest fixture lifecycle | pytest | adopt | yield/finalizer 逆序清理；失败也必须释放 |
| Property/Stateful testing | Hypothesis | adopt | 事务、幂等、扩展、队列、锁、PATCH 和事件状态机 |
| Real dependency integration | Testcontainers | adopt | MySQL/Redis/Mongo 真实实例合同测试；Fake 不替代语义 |
| 并发测试随机 sleep | 常见脆弱测试 | reject | barrier/event/fake clock 控制交错 |
| Fault Injection | 韧性测试 | adopt | commit 前后断连、扩展启动失败、Redis 超时、SIGTERM 等 |
| Soak/Load | 生产稳定性 | adopt release gate | 连接重建、队列、内存、event loop lag、热重启 |
| Fresh venv / wheel / sdist | Python 发布治理 | adopt | Release 必跑 |
| Generated project smoke | 框架脚手架治理 | adopt | CLI 生成项目后安装、启动、OpenAPI、测试冒烟 |
| 只测试对象字段不测试真实拦截 | 当前 RoutePolicy 风险 | reject | 必须端到端证明安全链确实执行 |

---

# 八、明确进入 LingShu 核心的能力

```text
public context facade
error taxonomy and response envelope
RoutePolicy compiler and execution pipeline
Principal/Tenant/Policy protocols
request context/deadline/cancellation
structured concurrency and TaskRegistry contracts
backend registry / connection alias / capabilities
transaction and Store protocols
schema facade / contract registry
OpenAPI contract compiler
extension manifest/container/lifecycle
local event and audit protocols
telemetry hooks
contract/unit/reference implementations
```

核心包含协议、状态机、安全默认值和内存参考实现，不强制加载所有外部驱动。

---

# 九、内置但可选的官方扩展

```text
lingshu-mysql
lingshu-sqlite
lingshu-mongodb
lingshu-redis
lingshu-jwt
lingshu-opentelemetry
future: lingshu-aead
```

在当前单仓库阶段可以保留同一发行包内的可选模块，但导入、依赖和启用边界必须按扩展设计，后续可拆分独立包。

---

# 十、暂缓到后续项目

```text
完整 lingshu-ms 运行时
Go 第二运行时
Temporal/Celery/Ray 深度集成
Kafka/NATS/RabbitMQ 官方实现
ClickHouse/OLAP 客户端
Casbin/OPA 官方集成
Kubernetes Operator
设备 MQTT Gateway
完整 MCP Server / AI Provider
```

当前仅保证合同和扩展点不阻断未来实现。

---

# 十一、实施冻结原则

1. 研究稿完成后，不再无限增加样本；新机制必须证明现有研究没有覆盖。
2. 每个 Phase PR 必须引用对应 ADR 和测试合同。
3. 实现不得把 extension/later 能力偷偷塞入核心。
4. 遇到 ADR 与代码冲突，先更新 ADR 并重新评审，不能由实现反向决定架构。
5. 所有安全、事务、并发与数据隔离能力必须有负向和故障测试，不以“正常路径通过”作为验收。