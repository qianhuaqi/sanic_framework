# MongoDB ODM、Schema 与安全边界第一批研究

> 状态：第一批研究结论，不是最终 ODM API 冻结稿。

## 研究结论概览

MongoDB 不应复用 MySQL `TableModel`，也不应被包装成“另一种 SQL ORM”。

LingShu 对 MongoDB 的正确定位是：

```text
DocumentModel
DocumentQuery
Projection
Aggregation
Index Definition
Schema Version
Native Driver Escape Hatch
```

统一的是资源入口、生命周期、安全和观测；不统一的是查询、事务和数据建模语义。

---

## MongoDB 官方机制中值得吸收的部分

### 1. Flexible schema 不等于无 schema

MongoDB 默认允许同一 collection 中的文档字段和类型不同，但官方提供 collection schema validation，可限制字段类型、范围和规则，并默认拒绝产生无效文档的 insert/update。

LingShu 应采用双层校验：

```text
API Schema / DocumentModel validation
              +
MongoDB collection validator
```

应用校验用于快速反馈和结构化错误；数据库 validator 用于防止并发、旁路脚本或旧服务写入错误结构。

### 2. 文档级原子性优先，跨文档事务谨慎

MongoDB 的自然优势是单文档内嵌数据的原子更新。多文档事务应作为显式高级能力，而不是把 MongoDB 假装成关系数据库。

设计文档时优先判断：

- 是否应嵌入；
- 是否应引用；
- 是否需要独立更新；
- 文档是否会无限增长；
- 是否存在热点文档；
- 是否真的需要跨文档事务。

### 3. Schema 演进必须显式

DocumentModel 应支持：

```text
schema_version
upgrade_from(previous_version)
read compatibility
write current version only
```

读取旧文档时可以兼容或迁移；新写入必须使用当前版本。禁止靠业务代码到处判断字段是否存在。

---

# LingShu MongoDB 后端建议

## 1. 独立后端包

```text
backends/mongodb/
├── backend.py
├── odm.py
├── query.py
├── projection.py
├── aggregation.py
├── indexes.py
├── schema.py
├── transaction.py
└── errors.py
```

MongoDB 与 MySQL 只共享最小资源协议，不共享 Query Builder 实现。

## 2. Model 绑定连接与 collection

```python
class Asset(DocumentModel):
    connection = "documents"
    collection_name = "assets"
    schema_version = 2
```

业务调用：

```python
asset = await Asset.get(asset_id)
items = await (
    Asset.query()
    .where(Asset.project_id == project_id)
    .project("id", "name", "status")
    .limit(50)
    .all()
)
```

API 可以保持 LingShu 风格，但编译结果必须是 MongoDB 查询，不模拟 SQL join。

## 3. 外部查询输入必须编译，不得直通

禁止：

```python
await collection.find(request.json)
```

正确流程：

```text
外部过滤条件
  -> Schema 校验
  -> 字段白名单
  -> operator 白名单
  -> 深度/数量限制
  -> 编译为 Mongo 查询
```

默认允许的 operator 应非常有限，例如：

```text
eq
ne
in
nin
gt
gte
lt
lte
exists
```

`$where`、任意 JavaScript、任意正则、任意深层表达式、客户端自定义 pipeline 默认禁止。

## 4. Projection 是安全机制，不只是性能优化

DocumentModel 应声明：

- 默认输出字段；
- 敏感字段；
- 内部字段；
- 可查询字段；
- 可排序字段；
- 可聚合字段。

例如密码摘要、内部密钥、风控字段、租户内部标记不能因为文档存在就默认返回。

## 5. Index 进入模型合同

候选：

```python
class Asset(DocumentModel):
    indexes = [
        UniqueIndex("tenant_id", "external_id"),
        Index("project_id", "status"),
        TTLIndex("expires_at"),
    ]
```

框架至少提供：

- index diff；
- dry-run；
- 创建前风险提示；
- 唯一索引冲突报告；
- 启动时只检查，不默认在线自动重建危险索引。

## 6. 乐观并发

候选文档字段：

```text
_version
updated_at
```

更新条件自动包含当前版本：

```text
_id = ? AND _version = current
```

成功后版本递增；影响文档数为 0 时返回明确并发冲突，而不是静默覆盖。

## 7. 多租户强制边界

`tenant_id` 或 `project_id` 由可信上下文注入，不能由客户端自由覆盖。

默认规则：

- 普通 Model 查询自动加入租户条件；
- 跨租户访问必须进入显式管理员 API；
- aggregation 每个入口都要验证租户条件；
- native driver 入口仍受 policy 检查和审计。

## 8. Aggregation 单独建模

不允许普通业务传入任意 pipeline。

候选：

```python
pipeline = (
    Asset.aggregate()
    .match(Asset.project_id == project_id)
    .group(by=Asset.status, total=count())
    .limit(20)
)
```

高级 native pipeline 仅对受信代码开放，并限制：

- 最大 stage 数；
- 最大执行时间；
- 是否允许 `$lookup`、`$out`、`$merge`；
- 结果大小；
- 日志和审计。

## 9. 大文档和无限数组保护

框架应支持模型级预算：

```text
max_document_bytes
max_array_items
max_nested_depth
max_batch_size
```

对于事件、日志、历史记录，不应无限追加到单个文档；应拆 collection 或采用时间序列/事件存储模式。

## 10. 事务 API

MongoDB 后端可以提供：

```python
async with db.mongo.transaction():
    ...
```

但必须：

- 明确部署是否支持；
- 明确事务超时；
- 保持事务短小；
- 禁止把网络调用放进事务；
- 不宣传与 MySQL 相同的隔离语义；
- 不自动将所有多文档操作包入事务。

---

# 与 MySQL ORM 明确不同的地方

| 能力 | MySQL | MongoDB |
|---|---|---|
| 模型 | TableModel | DocumentModel |
| 关系 | FK / Join | Embed / Reference / Aggregation |
| Schema | DDL / Migration | Validator / Schema Version |
| 原子性 | 事务内多行多表 | 单文档优先，多文档事务显式 |
| 查询 | SQL expression | Document filter/operator |
| 批处理 | insert/update/upsert | bulk write |
| 并发 | isolation/row lock/version | document atomic/version/filter |
| 高级入口 | parameterized raw SQL | native filter/pipeline/driver |

---

# 初步拒绝项

- 复用 SQL TableModel。
- 客户端原始 JSON 直接作为 Mongo filter。
- 客户端直接提交 aggregation pipeline。
- 没有 collection validator，只依赖 Python 校验。
- 将动态 schema 理解为无需版本治理。
- 将无限事件追加到单个文档数组。
- 默认返回完整文档和敏感字段。
- 默认把所有写操作包成多文档事务。

---

# 必须验证的测试

1. 非法 operator 注入被拒绝；
2. 未授权字段 projection 不可见；
3. tenant 条件无法被外部输入覆盖；
4. collection validator 拒绝旁路错误写入；
5. schema_version 旧文档读取与升级；
6. optimistic version 冲突；
7. unique index 并发冲突转稳定错误；
8. aggregation stage 和执行时间预算；
9. 文档大小、数组数量和嵌套深度限制；
10. bulk write 部分失败错误明细；
11. transaction commit/rollback/cancel；
12. pool 耗尽、断线和 graceful shutdown。

## 官方资料

- MongoDB Schema Validation: https://www.mongodb.com/docs/manual/core/schema-validation/
- MongoDB Transactions: https://www.mongodb.com/docs/manual/core/transactions/
