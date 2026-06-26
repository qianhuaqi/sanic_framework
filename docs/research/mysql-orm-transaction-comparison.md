# MySQL ORM 与事务机制第一批对比

> 状态：第一批研究结论，不是最终 API 冻结稿。
>
> 范围：SQLAlchemy、Ecto、EF Core、Prisma、Ent，并结合 MySQL/SQLite 后端差异评估 LingShu API 的关系型数据访问设计。

## 研究问题

LingShu 需要同时解决：

1. 普通 CRUD 足够简单；
2. 多步骤事务可靠；
3. 并发请求不共享事务状态；
4. 外部输入不能直接污染模型；
5. 查询行为可预期，避免 N+1 和隐式写入；
6. MySQL、SQLite 和未来 PostgreSQL 可以独立扩展；
7. 原生 SQL 有逃生口，但不能绕过安全边界。

---

## SQLAlchemy：成熟 UoW，但隐式状态必须收敛

### 值得吸收

- Session 代表一次数据库会话和事务作用域。
- identity map 保证同一 Session 中同一主键通常对应同一个对象实例。
- Unit of Work 统一收集变更并 flush。
- `with session.begin()` 明确 commit/rollback 边界。
- Core、ORM 和 raw SQL 并存，复杂查询有逃生口。

### 需要警惕

- autoflush 会在查询、commit、savepoint 等时点隐式执行 SQL。
- lazy loading 可能在属性访问时发出查询。
- 对象可能处于 transient、pending、persistent、expired、detached 等状态。
- AsyncSession 不应在并发 task 之间共享。

### LingShu 裁决

`adapt`

- 吸收事务作用域、identity 和 UoW 思想。
- 第一阶段不向普通业务暴露完整对象状态机。
- 默认禁止隐式 lazy load；关系必须显式 preload/eager load。
- 事务对象通过 ContextVar 绑定当前协程，但每个并发 task 必须独立事务上下文。

---

## Ecto：输入边界比“模型自动赋值”更安全

### 值得吸收

Ecto Changeset 将以下步骤放在一个显式结构里：

- 外部字段白名单；
- 类型转换；
- 业务校验；
- 数据库约束；
- 结构化错误。

尤其重要的是：应用级预检查不能替代数据库唯一约束。数据库 constraint 才能在并发下安全处理唯一性。

### LingShu 裁决

`adapt`

候选设计：

```python
mutation = User.mutate(payload)
mutation.allow("name", "email")
mutation.validate()
await mutation.insert()
```

或者更轻量：

```python
await User.create_from(
    payload,
    fields={"name", "email"},
    schema=CreateUserSchema,
)
```

最终 API 待后续 Schema 研究后冻结，但原则立即生效：

- ORM Model 拥有字段，不代表客户端可以写这些字段。
- `tenant_id`、`role`、`is_admin`、审计字段默认不可由外部输入赋值。
- 唯一性最终交给数据库约束，并转换成稳定错误码。

---

## EF Core：短生命周期 Context 与变更追踪

### 值得吸收

- DbContext 明确设计为短生命周期 Unit of Work。
- 查询得到的实体自动被跟踪。
- SaveChanges 根据属性级变更生成更新。
- 原始值、当前值和实体状态可诊断。

### 风险

- Context 生命周期过长会积累对象和状态。
- 自动跟踪可能增加内存和认知成本。
- 读请求不需要变更追踪时应使用 no-tracking 模式。

### LingShu 裁决

`adapt`

- 事务/会话严格限制在请求或显式业务操作作用域。
- 普通查询默认返回轻量结果，是否启用对象跟踪需谨慎。
- 若后续实现 dirty tracking，必须可关闭并有清晰诊断。
- 不把数据库实体长期放入全局缓存或跨请求复用。

---

## Prisma：开发体验、生成和事务预算

### 值得吸收

- Schema 作为生成 Client、类型和 Migration 的来源。
- 区分 nested write、batch operation、sequential transaction、interactive transaction。
- 事务支持 `maxWait`、`timeout` 和 isolation level。
- 官方明确建议保持短事务，避免性能下降和死锁。
- 支持 optimistic concurrency 和 idempotent API 的工程指导。

### 风险

- 统一 Client 容易让开发者忽视不同数据库的方言和隔离能力。
- 生成层对高级数据库特性的覆盖不可能完整。

### LingShu 裁决

- `adopt`：事务必须有等待预算和执行预算。
- `adopt`：Schema/模型信息驱动 Migration、文档、类型和测试。
- `adapt`：批量 API 与事务 API 分开。
- `reject`：通过统一 API 假装所有 SQL 后端支持相同能力。

---

## Ent：事务 Client 与能力生成

### 值得吸收

- Schema/codegen 带来类型安全查询。
- 事务中获取专用 tx client，业务函数可以使用事务 client 而不改变查询逻辑。
- `WithTx` 统一处理 panic、rollback、commit 错误。
- 支持 commit/rollback hook。

### LingShu 裁决

`adapt`

LingShu 事务内部的 Model/Query 应自动绑定当前事务连接，避免业务代码手工层层传递 connection：

```python
async with db.mysql.transaction():
    await User.create(...)
    await AuditLog.create(...)
```

但底层必须能够显式取得当前事务资源用于高级场景：

```python
async with db.mysql.transaction() as tx:
    await tx.execute(...)
```

---

# LingShu 关系型数据层初步方案

## 1. 后端独立

```text
backends/mysql/
backends/sqlite/
future: backends/postgresql/
```

可以共享表达式协议和合同测试，但以下必须独立：

- driver；
- pool；
- dialect；
- transaction；
- migration；
- capability；
- error mapping。

## 2. 统一入口基于连接别名路由

```python
class User(TableModel):
    connection = "primary"
    table_name = "users"
```

```text
primary -> backend=mysql
```

框架按配置路由，不允许运行时猜测。

## 3. 事务 API

候选：

```python
async with db.mysql.transaction(
    timeout=5,
    acquire_timeout=2,
    isolation="repeatable_read",
):
    ...
```

约束：

- 进入事务时获取或绑定连接。
- 同一事务内所有 ORM 操作使用同一连接。
- 正常退出 commit；异常、取消、超时 rollback。
- rollback 失败也必须记录，不能覆盖原始异常。
- 事务结束后清理 ContextVar，禁止泄漏到下一个请求。
- 并发子 task 不得默认继承并共同使用同一数据库事务。

## 4. 写入模式

### 单次普通写入

允许 ORM 方法内部使用短事务：

```python
await User.create(...)
```

### 多步骤业务写入

必须显式事务：

```python
async with db.mysql.transaction():
    order = await Order.create(...)
    await Inventory.decrease(...)
```

### 外部副作用

HTTP、消息、文件和支付调用不得长时间放在数据库事务中。使用 Outbox、状态机或补偿流程。

## 5. 查询模式

候选：

```python
users = await (
    User.query()
    .where(User.status == 1)
    .order_by(User.id.desc())
    .limit(20)
    .all()
)
```

必须满足：

- 值参数化；
- 字段和操作符来自模型元数据；
- 默认最大 limit；
- 大数据使用 stream/cursor；
- update/delete 没有条件时默认拒绝；
- 关系加载显式声明；
- 支持查看安全 SQL 摘要和执行计划入口。

## 6. 并发控制

提供明确机制，而不是让开发者自行拼 SQL：

- version 字段的 optimistic lock；
- `for_update()` 悲观锁；
- unique constraint；
- 影响行数检查；
- deadlock/write-conflict 错误分类。

自动重试仅允许：

- 错误被后端明确判定为可重试；
- 回调声明为幂等或由框架事务执行器控制；
- 有最大次数和总时间预算；
- 带退避和抖动。

## 7. Raw SQL 逃生口

```python
await db.mysql.raw(
    "SELECT ... WHERE id = %s",
    [user_id],
)
```

必须继续执行：

- 参数化；
- timeout；
- tracing；
- 日志脱敏；
- tenant/audit policy；
- 只读/写入权限判断。

动态表名、字段名必须通过受信标识符对象或白名单，不能作为普通参数字符串拼接。

---

# 初步拒绝项

- 一个 ORM 文件同时处理 MySQL、SQLite、MongoDB、Redis。
- 默认 lazy load。
- Session/transaction 在多个并发协程间共享。
- 所有写操作自动无限重试。
- 无条件 update/delete。
- 外部 payload 直接 `Model(**payload)`。
- Raw SQL 完全绕过框架。
- 为追求简短 API 隐藏 commit、rollback 和连接生命周期。

---

# 必须验证的测试

1. commit、异常 rollback、取消 rollback、超时 rollback；
2. 同一事务复用同一连接；
3. 两个并发请求事务不串线；
4. 事务结束 ContextVar 清空；
5. 子 task 并发使用事务时明确拒绝或隔离；
6. optimistic lock 冲突；
7. deadlock 错误分类和受限重试；
8. 无条件 update/delete 被拒绝；
9. 字段、排序和 operator 注入被拒绝；
10. 外部输入无法修改受保护字段；
11. 默认分页上限；
12. 大结果流式读取不爆内存；
13. pool 耗尽时背压或超时；
14. graceful shutdown 归还连接；
15. MySQL 与 SQLite capability 差异明确生效。

## 官方资料

- SQLAlchemy Session Basics: https://docs.sqlalchemy.org/en/20/orm/session_basics.html
- Ecto Changeset: https://hexdocs.pm/ecto/Ecto.Changeset.html
- EF Core Change Tracking: https://learn.microsoft.com/en-us/ef/core/change-tracking/
- Prisma Transactions: https://www.prisma.io/docs/orm/prisma-client/queries/transactions
- Ent Transactions: https://entgo.io/docs/transactions/
- SQLite Transactions: https://www.sqlite.org/lang_transaction.html
