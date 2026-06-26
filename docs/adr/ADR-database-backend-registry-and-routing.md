# ADR：数据库后端注册、连接别名与自动路由

- 状态：Draft
- 阶段：Phase C0 研究
- 范围：LingShu API 数据访问层

## 背景

LingShu 需要同时支持 MySQL、SQLite、Redis、MongoDB，并为 PostgreSQL、ClickHouse、Elasticsearch、DuckDB 等未来后端保留扩展能力。

如果把所有数据库逻辑塞进同一个 ORM 文件，会产生：

- SQL、Document、KV 语义混乱；
- 大量 backend `if/else`；
- 一种数据库改动破坏其他数据库；
- 方言、事务和迁移行为被错误统一；
- 测试矩阵不可控；
- 新增后端必须修改框架核心。

另一方面，如果每个后端完全独立且没有统一入口，业务代码又会承担连接选择、生命周期、上下文、错误、日志和指标等重复工作。

## 决策

采用：

> 统一 `db` 门面 + 连接别名 + 后端注册中心 + 独立 backend 包 + capabilities。

```text
business code
    -> db facade
        -> connection alias
            -> registry
                -> backend instance
```

统一门面不实现数据库查询语义，只负责资源发现和公共生命周期。

## 目录边界

```text
src/lingshu/data/
├── facade.py
├── registry.py
├── contracts.py
├── capabilities.py
├── context.py
├── lifecycle.py
├── errors.py
└── backends/
    ├── mysql/
    ├── sqlite/
    ├── mongodb/
    └── redis/
```

## 连接配置

候选配置结构：

```yaml
connections:
  primary:
    backend: mysql
    role: primary

  local:
    backend: sqlite

  documents:
    backend: mongodb

  cache:
    backend: redis
```

Model 或业务代码绑定连接别名：

```python
class User(TableModel):
    connection = "primary"
    table_name = "users"

class Asset(DocumentModel):
    connection = "documents"
    collection_name = "assets"
```

框架依据显式配置自动路由，不根据方法名、参数或 SQL 字符串猜测后端。

## 公共协议

后端只实现最小公共生命周期协议：

```text
configure
connect
health
ready
close
capabilities
normalize_error
```

连接实例需要提供：

```text
backend_name
connection_name
state
metrics
native_client
```

查询、事务、ORM、ODM、Cache、Lock 等能力不放入一个万能基类。

## 后端能力声明

后端必须声明 capabilities，示例：

```text
transactions
savepoints
isolation_levels
concurrent_writes
returning
upsert
json
schema_migration
streaming_cursor
document_validation
ttl
pipeline
streams
pubsub
```

调用不支持的能力时：

- 返回稳定的 `CapabilityNotSupported`；
- 包含 backend、connection、capability；
- 不静默降级；
- 不自动改用另一个后端。

## 数据模型边界

### MySQL / SQLite

```text
TableModel
Query
Transaction
Migration
SQL Repository
```

二者可共享表达式合同，但 driver、dialect、transaction、migration、pool 和 capability 独立。

### MongoDB

```text
DocumentModel
DocumentQuery
Projection
Aggregation
Index
SchemaVersion
```

不得伪造 SQL Join、关系事务或 TableModel 语义。

### Redis

```text
Cache
Lock
RateLimiter
IdempotencyStore
OperationStore
Counter
Stream
PubSub
```

不得暴露通用 ORM 方法。

## 事务路由

事务上下文必须绑定：

```text
app instance
connection name
backend instance
current execution context
```

在事务内：

- 相同连接别名的 Model 自动复用当前事务资源；
- 其他连接仍使用自身资源；
- 禁止把一个后端事务伪装成跨库事务；
- nested transaction 的行为由 capability 决定；
- transaction session 不得被并发子任务共享。

## Raw / Native 入口

每个后端可以提供显式高级入口：

```python
db.mysql.raw(...)
db.mongo.native(...)
db.redis.native(...)
```

但仍必须经过：

- timeout/cancellation；
- tracing；
- logging redaction；
- tenant/security policy；
- metrics；
- connection lifecycle。

Native 入口不是逃离框架安全边界的后门。

## 插件扩展

新增后端步骤：

1. 创建独立 backend 包；
2. 实现最小生命周期协议；
3. 声明 capabilities；
4. 注册 backend name；
5. 提供后端合同测试；
6. 不修改已有后端实现。

候选注册：

```python
registry.register_backend("mysql", MySQLBackend)
registry.register_backend("sqlite", SQLiteBackend)
registry.register_backend("mongodb", MongoBackend)
registry.register_backend("redis", RedisBackend)
```

后续评估 Python package entry points 支持第三方插件。

## 统一错误分类

公共错误只归一化稳定大类：

```text
ConnectionUnavailable
AcquireTimeout
OperationTimeout
ConstraintViolation
Conflict
Deadlock
SerializationFailure
CapabilityNotSupported
InvalidQuery
PermissionDenied
```

后端原始错误保留为 cause 和受控诊断信息，不直接暴露给客户端。

## 可观测性

公共指标：

```text
pool_size
pool_in_use
pool_waiters
acquire_latency
query_latency
operation_count
error_count
reconnect_count
```

后端可追加特有指标：

- MySQL deadlock、rows affected；
- SQLite busy/locked；
- MongoDB server selection、document count；
- Redis hit rate、eviction、big key、pending stream。

## 安全决策

- connection alias 来自配置或 Model 元数据，不接受客户端任意指定；
- tenant 上下文由可信身份链生成；
- SQL 标识符、Mongo operator、Redis key namespace 分别由后端验证；
- credential 不进入日志和错误响应；
- 动态切库、跨租户和管理员连接必须通过显式 Policy。

## 被拒绝方案

### 一个万能 ORM

拒绝原因：不同数据库语义无法正确统一，长期必然形成大量条件分支。

### 业务代码自行获取所有驱动客户端

拒绝原因：会绕过生命周期、安全、观测和错误标准。

### 完全隐式后端猜测

拒绝原因：不可审计、存在歧义，事务与安全边界不明确。

### 为统一 API 静默降级能力

拒绝原因：相同代码在不同后端产生不同正确性和性能，风险不可接受。

## 影响

### 正面

- 每种数据库独立演进；
- 业务入口稳定；
- 新增后端影响范围小；
- 测试和性能边界清晰；
- 不同数据库可采用最适合自己的 API。

### 代价

- 不能承诺所有后端完全相同的 CRUD API；
- 需要维护 registry、capabilities 和合同测试；
- SQL 后端之间仍需处理部分重复实现；
- 文档必须清楚说明各后端差异。

这些代价低于万能 ORM 长期产生的语义错误和维护风险。

## 验收条件

1. 新增 fake backend 不修改 `db` facade；
2. MySQL、SQLite、MongoDB、Redis 独立加载和关闭；
3. 同一 app 多连接可并存；
4. 多 app、多请求并发不串线；
5. Model 根据 connection alias 稳定路由；
6. 客户端输入不能选择任意连接；
7. capability 不支持时明确报错；
8. transaction 只影响指定连接；
9. native 入口仍记录 timeout、trace 和审计；
10. 一个后端缺失依赖时不阻止未启用后端启动。

## 后续

研究完成后，将本 ADR 与 MySQL Unit of Work、DocumentModel、Redis Capability Facade ADR 一起冻结，再进入运行时代码阶段。