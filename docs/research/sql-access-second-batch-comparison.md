# 关系型 ORM 与 SQL 访问第二批对比

> 状态：第二批研究结论，不是最终公共 API 冻结稿。
>
> 样本：Doctrine ORM、Hibernate ORM、jOOQ、Django ORM、Rails Active Record、Laravel Eloquent、Drizzle ORM、SQLx、sqlc。

## 研究目标

第一批已经确认：LingShu 需要“常用 CRUD 简单、复杂事务显式、数据库后端独立、Raw SQL 有受控逃生口”。

第二批继续回答：

1. ORM 的便利性应该做到什么程度；
2. lazy loading、change tracking、identity map 如何避免失控；
3. 嵌套事务和 savepoint 如何定义；
4. 批量读取和大结果如何控制内存；
5. 是否需要 SQL-first / codegen 模式补充 ORM；
6. 不同数据库方言如何保持独立；
7. 安全默认值应该落在哪里。

---

# 一、Doctrine ORM

## 值得吸收

Doctrine 的 EntityManager 维护 identity map：同一个 EntityManager 内，同一实体类型和主键只对应一个对象实例。`persist()` 与 `remove()` 不立即执行 SQL，而是采用 transactional write-behind，在 `flush()` 时由 Unit of Work 统一同步。

这带来两个重要经验：

- 一次业务操作中的对象身份应稳定；
- 写入可以聚合后统一提交，减少零散 SQL 并维护引用完整性。

Doctrine 也明确指出，flush 成本主要取决于当前 Unit of Work 的规模和 change tracking 策略，并建议不要每次修改都 flush，而应形成合理的工作单元。

## 风险

- Unit of Work 过大时，flush 扫描和对象内存成本明显上升；
- persist/remove 与数据库状态存在时间差；
- managed/detached/removed/new 状态增加学习成本；
- 级联与生命周期事件过多时，实际 SQL 难以预测。

## LingShu 裁决

`adapt`

- 保留短生命周期 UoW 和 identity map 思想；
- 不向普通业务暴露复杂对象状态机；
- 提供 UoW 大小指标和阈值告警；
- 禁止无限积累实体后一次 flush；
- 批处理采用显式分块、flush/clear 或后端 bulk API；
- 生命周期 Hook 进入受控扩展，不默认堆叠魔法。

---

# 二、Hibernate ORM

## 值得吸收

Hibernate 明确规定 Session/EntityManager 不是线程安全对象，只能由单一线程在同一时间使用。其 `@Version` 乐观锁通过版本字段检测冲突，避免 last-commit-wins 导致的 lost update。

Hibernate 还展示了 fetch join 对解决 N+1 的重要性，同时警告并行抓取多个 to-many collection 会形成笛卡尔积，导致严重性能问题。

## LingShu 裁决

`adopt/adapt`

- `adopt`：一个事务会话绝不能由多个并发协程共享；
- `adopt`：默认支持 version 字段乐观锁；
- `adapt`：关系加载必须显式；
- `adapt`：一次查询最多预取有限数量的 to-many 关系；
- Query Plan 应检测可能的笛卡尔积与 N+1 风险；
- 不使用“请求结束后仍允许 lazy load”的 open-session-in-view 模式。

---

# 三、jOOQ

## 值得吸收

jOOQ 不试图隐藏 SQL，而是提供类型安全 DSL。事务回调接收局部 Configuration/DSLContext，避免事务代码错误地使用全局连接。其默认事务提供器可通过 savepoint 实现嵌套事务。

## LingShu 裁决

`adapt`

- ORM 之外提供 SQL Expression / Query Builder 高级层；
- 事务内部必须绑定局部执行器，业务 Model 自动使用当前事务，但高级用户可显式取得 `tx`；
- 嵌套事务默认语义明确为 savepoint，而不是“启动第二个真实事务”；
- 后端不支持 savepoint 时，必须明确拒绝或按配置使用 join-existing，不得伪造成功；
- 查询表达式应保留数据库方言能力，不追求所有后端完全一致。

---

# 四、Django ORM

## 值得吸收

Django 默认 autocommit，只在显式 `atomic()` 中建立事务；嵌套 `atomic()` 使用 savepoint，外层决定最终 commit/rollback。Django 还支持 `on_commit()`，只有外层事务真正提交后才执行回调。

Django 文档明确提醒：给每个 HTTP 请求自动开启事务虽然简单，但在流量增加时会引入额外开销；流式响应生成发生在视图返回后，不应在其中继续数据库写入。

QuerySet 的惰性组合体验很好，但 QuerySet 在 iteration、len、bool、repr 等场景会触发执行，这类隐式求值容易导致意外查询。

## LingShu 裁决

`adapt`

- 默认 autocommit + 显式 transaction；
- 不默认每个请求包事务；
- 支持嵌套 savepoint；
- 增加 `after_commit()`，用于发事件、删缓存或调度后续任务；
- streaming/SSE 开始发送响应后禁止依赖未提交数据库写入；
- Query 对象保持可组合，但执行入口显式为 `.all()/.first()/.exists()/.count()`；
- 不让 `bool(query)`、`len(query)`、日志打印等动作隐式执行 SQL。

---

# 五、Rails Active Record

## 值得吸收

Rails 的链式 Relation、Scope 与 Active Record API 开发效率极高。它提供：

- `strict_loading`，在发生意外 lazy load 时抛出错误；
- `lock_version` 乐观锁；
- 悲观锁；
- `find_each` / `find_in_batches`，避免一次加载整个大表；
- EXPLAIN 接口与 eager loading 工具。

## 风险

- Model 同时承担数据、校验、关联、回调、Scope 和业务逻辑时容易膨胀；
- default scope 可能隐式改变所有查询；
- callback 过多时副作用难以追踪；
- 统一 API 会掩盖不同数据库的方言差异。

## LingShu 裁决

- `adopt`：链式 Query 与可复用 Scope；
- `adopt`：strict loading 默认在开发/测试开启，生产可配置为报错或告警；
- `adopt`：批量游标/分块迭代；
- `adapt`：乐观锁和悲观锁；
- `reject`：任意 default scope；租户过滤必须是框架强制策略，而不是普通可覆盖 Scope；
- `reject`：Model 中堆积复杂业务回调。

---

# 六、Laravel Eloquent

## 值得吸收

Eloquent 默认要求 `$fillable` 或 `$guarded`，用于防止 mass assignment。官方示例特别指出，恶意用户可能提交 `is_admin` 字段完成权限提升。

Eloquent 还提供：

- `preventLazyLoading`；
- `preventSilentlyDiscardingAttributes`；
- chunk/lazy/cursor；
- Scope、Cast、Observer、Soft Delete。

## LingShu 裁决

`adopt/adapt`

- 外部写入字段必须 allowlist；
- 未允许字段默认抛错，不静默丢弃；
- lazy loading 默认禁止或至少在测试中阻断；
- 大结果使用 cursor/chunk，但必须说明驱动是否真正流式；
- Soft Delete 不进入所有模型默认行为，作为显式能力；
- Observer/Callback 不允许替代 BusinessModel 和显式事件。

---

# 七、Drizzle ORM

## 值得吸收

Drizzle 的 API 接近 SQL，类型清晰，事务回调使用专用 `tx`；嵌套事务映射 savepoint；同时暴露方言特定事务配置，例如 isolation level、read/write、consistent snapshot。

## LingShu 裁决

`adapt`

- Query Builder 保持接近 SQL 的结构，而不是创造难以理解的自定义语言；
- nested transaction 映射 savepoint；
- transaction options 由 backend capabilities 决定；
- MySQL、SQLite、PostgreSQL 的事务配置独立；
- 不支持的 isolation/access mode 立即报错；
- 业务条件触发 rollback 应通过明确异常或 `tx.abort(reason)`，不能静默跳出。

---

# 八、SQLx

## 值得吸收

SQLx 的 `query!()` 对静态 SQL 做编译期检查，并根据数据库 schema 推导参数和结果类型。它还支持离线模式，将查询元数据提交到版本库，并在 CI 使用 `prepare --check` 检测 SQL 与 schema 漂移。

## LingShu 裁决

`adapt/later`

Python 无法完整复制 Rust 宏的编译期能力，但可吸收：

- SQL 文件作为正式资源；
- 命名查询；
- Schema 快照；
- CI 对 SQL 参数、返回列和数据库版本做验证；
- SQL 查询与 DTO 映射生成；
- Raw SQL 不能只是任意字符串。

候选 LingShu 工具：

```text
lingshu sql check
lingshu sql prepare
lingshu sql generate
```

运行时第一阶段不实现完整生成器，但在研究和 Phase F 中保留。

---

# 九、sqlc

## 值得吸收

sqlc 以 SQL 为事实源，生成类型化查询代码；`WithTx()` 将同一组 Queries 绑定到事务执行器，而不复制所有业务查询逻辑。它还支持 query lint/vet、schema 变更验证和命名参数。

## LingShu 裁决

`adapt`

- ORM 之外支持“命名 SQL Repository”；
- 事务中将 Repository 绑定当前 tx；
- SQL 参数命名必须语义明确；
- CI 校验 SQL、Schema 和生成结果一致；
- 生成代码与手写代码分离；
- SQL-first 模式适合复杂报表、批量更新、性能敏感查询，不强迫所有业务都通过 ORM。

---

# 十、LingShu 第二批综合决策

## 1. 两条关系型数据访问路径并存

### Model / ORM 路径

适合：

- 单表 CRUD；
- 普通关联查询；
- 业务模型；
- 乐观锁；
- 常用分页。

```python
user = await User.get(user_id)
users = await User.query().where(User.status == 1).limit(20).all()
```

### SQL-first Repository 路径

适合：

- 复杂统计；
- 多层 CTE；
- 窗口函数；
- 批量更新；
- 数据导出；
- 性能敏感查询。

```python
report = await db.mysql.queries.sales_summary(
    tenant_id=tenant_id,
    start_at=start_at,
    end_at=end_at,
)
```

两条路径共享事务、连接、超时、租户、安全和观测。

## 2. 事务语义

候选规则：

```text
outer transaction -> real transaction
nested transaction -> savepoint
requires_new       -> only if backend explicitly supports
join_existing      -> optional policy
```

- 外层成功才 commit；
- 内层异常默认 rollback to savepoint；
- `after_commit` 仅在最外层成功提交后执行；
- 不支持 savepoint 的后端明确报错；
- transaction session 禁止跨并发 task 共享。

## 3. 默认阻止的隐式行为

- 默认 lazy loading；
- Query 对象在 bool/len/repr 时自动执行；
- 未授权字段静默丢弃；
- 无条件 update/delete；
- default scope 隐式改变查询；
- callback 内发网络请求；
- 每个 HTTP 请求自动开启事务；
- Session/EntityManager 长时间存活。

## 4. 大数据查询

统一提供：

```text
stream()
iterate(batch_size=...)
chunk_by_id(...)
```

并明确：

- stream 是否真流式由驱动 capability 声明；
- cursor 不一定等于零内存；
- 批处理使用稳定且唯一的游标字段；
- 批处理中数据变化可能导致遗漏或重复，需文档和策略；
- 默认最大批大小与总处理预算。

## 5. N+1 保护

- 关系默认不隐式加载；
- 开发/测试启用 strict loading；
- 允许显式 `select_related/preload/include` 风格能力；
- 记录每请求 SQL 数量；
- 超过阈值告警或测试失败；
- 并行预取多个 to-many 关系时提示笛卡尔积风险。

## 6. Mass Assignment

- `Model(**request.json)` 禁止作为公共推荐写法；
- Create/Update Schema 定义允许字段；
- tenant、role、permission、audit、version 字段只由可信上下文写入；
- 未知字段默认错误；
- 数据库约束错误转换成稳定错误码。

---

# 十一、追加测试合同

1. Session/事务不能跨并发协程共享；
2. nested transaction 正确创建/释放/回滚 savepoint；
3. after_commit 在外层回滚时不执行；
4. strict loading 捕获 N+1；
5. 多 to-many preload 笛卡尔积风险检测；
6. 乐观锁阻止 lost update；
7. 悲观锁等待和 timeout；
8. 未允许字段写入失败；
9. Query 的 repr/bool/len 不触发 SQL；
10. cursor/chunk 的内存上限和边界重复测试；
11. SQL-first Repository 在事务内绑定当前 tx；
12. SQL 文件与 schema 快照 CI drift check；
13. MySQL/SQLite 方言不支持能力时明确失败；
14. 每请求 SQL 数量指标和慢查询摘要。

---

# 官方资料

- Doctrine Working with Objects: https://www.doctrine-project.org/projects/doctrine-orm/en/current/reference/working-with-objects.html
- Hibernate ORM User Guide: https://docs.hibernate.org/orm/current/userguide/html_single/
- jOOQ Transaction Management: https://www.jooq.org/doc/latest/manual/sql-execution/transaction-management/
- Django Transactions: https://docs.djangoproject.com/en/5.2/topics/db/transactions/
- Django QuerySet API: https://docs.djangoproject.com/en/5.2/ref/models/querysets/
- Rails Active Record Querying: https://guides.rubyonrails.org/active_record_querying.html
- Laravel Eloquent: https://laravel.com/docs/12.x/eloquent
- Drizzle Transactions: https://orm.drizzle.team/docs/transactions
- SQLx query macro: https://docs.rs/sqlx/latest/sqlx/macro.query.html
- sqlc Transactions: https://docs.sqlc.dev/en/latest/howto/transactions.html
- sqlc Named Parameters: https://docs.sqlc.dev/en/latest/howto/named_parameters.html
