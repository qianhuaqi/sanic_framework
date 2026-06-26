# LingShu 全球框架能力矩阵

> 状态：Phase C0 研究已完成第一轮收敛。
>
> 目标：不按语言、流行度或厂商排名，只提取可验证的工程机制，并决定其在 LingShu API 中的去向。

## 裁决

```text
adopt      直接采用为 LingShu 原则
adapt      保留机制，按 Sanic/Python/异步环境改造
extension  作为官方或第三方扩展
reject     明确拒绝
later      当前 API 主线暂缓
```

总裁决见：

```text
docs/research/lingshu-adoption-matrix.md
```

实施映射见：

```text
docs/architecture/phase-cf-implementation-map.md
```

核心与扩展边界见：

```text
docs/adr/ADR-core-vs-extension-boundary.md
```

---

# 研究覆盖矩阵

| 能力域 | 主要样本 | 已形成结论 |
|---|---|---|
| SQL ORM / UoW | SQLAlchemy、Doctrine、Hibernate、EF Core、Ecto、Django ORM、Rails、Eloquent | 简单 CRUD + 显式短事务；strict loading；乐观锁；after_commit；外部输入与持久化分层 |
| SQL-first / Codegen | jOOQ、SQLx、sqlc、Prisma、Ent、Drizzle | ORM 与命名 SQL Repository 并存；Schema/SQL drift check；事务执行器绑定 |
| SQL 后端差异 | MySQL、SQLite | 独立 backend/dialect/pool/transaction/migration；共享最小表达式合同 |
| Document NoSQL | MongoDB | 独立 DocumentModel/ODM；双层 Schema；operator/pipeline 白名单；索引与版本治理 |
| KV / 协调 | Redis | Cache/Lock/Rate/Replay/Idempotency/Operation/Stream 能力门面；不做 ORM |
| 认证授权 | Spring Security、Symfony Security、Laravel Policy、Django Auth、Casbin、NestJS Guard | Authentication、Tenant、Gate/Policy 分离；default deny；复杂策略引擎扩展化 |
| 签名与防重放 | AWS SigV4、GitHub Webhook | versioned canonical request + HMAC-SHA256 + raw body digest + timestamp + nonce |
| 幂等 | Stripe | fingerprint、并发 owner、结果复用、unknown 正式状态；不替代数据库约束 |
| 限流与隔舱 | NestJS Throttler、Tower、Resilience4j | Rate/Concurrency/Queue/Timeout/CircuitBreaker/Retry 分离 |
| 结构化并发 | asyncio、AnyIO、Go context/errgroup、Tokio | TaskGroup、取消传播、绝对 deadline、后台任务 owner、受管 shutdown |
| 生命周期 | Sanic、NestJS、Kubernetes | configure/setup/start/ready/drain/stop/close；正序启动、逆序回滚和关闭 |
| Schema / Validation | Pydantic、Ecto、Bean Validation、ASP.NET、Symfony、Laravel、Zod | Transport/Input/Domain/Persistence/Output 五层；严格输入；PATCH 三态；输出白名单 |
| API 合同 | JSON Schema 2020-12、OpenAPI 3.1、FastAPI | 单一合同编译 OpenAPI、SDK、Mock、契约测试；operationId 稳定；合同漂移检查 |
| DI / 扩展 | NestJS Providers、ASP.NET DI、Spring Scope | Manifest、Provider Registry、作用域、DAG、scope validation、显式启用插件 |
| 事件 | Spring Events、Symfony Dispatcher、Django Signals、CloudEvents | Hook/Local/AfterCommit/Outbox/Audit 分离；耐久事件至少一次 + 消费幂等 |
| 可观测性 | OpenTelemetry、W3C Trace Context、OWASP Logging | Trace/Metrics/Logs 关联；低基数指标；审计独立；Exporter 有界 |
| 测试 | pytest、Hypothesis、Testcontainers | 真实后端、状态机、确定性并发、故障注入、load/soak、发布冒烟 |

---

# 研究文档索引

## 数据

```text
docs/research/mysql-orm-transaction-comparison.md
docs/research/sql-access-second-batch-comparison.md
docs/research/mongodb-odm-schema-comparison.md
docs/research/redis-resilience-cache-lock-comparison.md
docs/adr/ADR-database-backend-registry-and-routing.md
docs/adr/ADR-core-vs-extension-boundary.md
```

## 安全

```text
docs/research/security-authz-signing-idempotency-comparison.md
docs/adr/ADR-security-request-execution-chain.md
docs/adr/ADR-idempotency-replay-rate-limit-boundary.md
```

## 并发与生命周期

```text
docs/research/request-lifecycle-concurrency-resilience-comparison.md
docs/adr/ADR-concurrency-cancellation-backpressure.md
docs/adr/ADR-timeout-circuit-breaker-graceful-shutdown.md
```

## Schema 与合同

```text
docs/research/schema-validation-serialization-openapi-comparison.md
docs/adr/ADR-schema-contract-layering.md
docs/adr/ADR-openapi-codegen-contract-drift.md
```

## 扩展、事件与质量

```text
docs/research/extensions-di-events-observability-testing-comparison.md
docs/adr/ADR-extension-container-lifecycle.md
docs/adr/ADR-events-audit-observability-testing.md
```

---

# 已冻结的高层决定

1. 当前只解决 LingShu API，不同时建设第二运行时。
2. 一个稳定入口可以自动路由，但路由依据必须显式、可审计。
3. MySQL、SQLite、MongoDB、Redis 保持独立正确语义。
4. 安全、事务、并发、Schema 与扩展都通过明确合同和状态机实现，不依赖隐式魔法。
5. 默认拒绝 lazy load、mass assignment、万能 ORM、裸后台任务、无界队列和安全降级。
6. OpenAPI、SDK、测试和 AI 元数据都从同一合同生成。
7. 核心只包含稳定协议、安全默认和参考实现；外部驱动和重型能力扩展化。
8. 下一运行时施工从 C1 请求执行基础与生命周期开始。

---

# 研究继续条件

第一轮全球框架研究到此收敛。后续只有满足以下任一条件才新增专项研究：

- 当前 ADR 无法回答具体实现冲突；
- 新后端具有现有 capability 模型无法表达的语义；
- 官方规范发生破坏性变化；
- 性能或安全实验推翻当前假设；
- Phase PR 验收发现机制缺口。

不再以“多看几个框架”为目标无限扩张范围。