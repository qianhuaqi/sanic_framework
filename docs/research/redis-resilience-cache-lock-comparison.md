# Redis 缓存、锁、幂等与韧性第一批研究

> 状态：第一批研究结论，不是最终 Redis API 冻结稿。

## 研究结论概览

Redis 不进入通用 ORM，不提供 `RedisModel.find()` 之类伪关系语义。

LingShu 对 Redis 的正确抽象是能力门面：

```text
Cache
Lock
RateLimiter
IdempotencyStore
OperationStore
Counter
Stream
PubSub
Native Client
```

统一入口负责资源、生命周期、超时、取消、日志、指标和租户上下文；每项能力有独立安全规则。

---

## 官方机制中值得吸收的部分

### 1. Pipeline 是 RTT 优化，不是事务

Redis pipelining 允许客户端一次发送多条命令，再批量读取响应，减少网络往返成本。

LingShu 应明确区分：

```text
pipeline = 批量发送与减少 RTT
transaction = MULTI/EXEC 语义
atomic operation = 单命令或 Lua/Function
```

禁止把 pipeline 宣传成原子事务。

### 2. 锁必须先定义安全保证

Redis 官方锁文档强调最基本的目标包括：互斥、死锁可恢复、故障容忍。简单主从故障切换因为复制异步，可能出现两个客户端同时持有锁。

单实例锁至少需要：

```text
SET key unique_owner NX PX ttl
```

释放时必须比较 owner，再删除，不能无条件 `DEL key`。

### 3. Redis 锁不是数据库约束

锁过期、进程暂停、时钟变化、网络分区都可能让旧持有者继续执行。因此关键写入不能只靠“拿到 Redis 锁”保证正确性。

LingShu 对关键业务应组合：

- 数据库唯一约束；
- optimistic version；
- lease/owner；
- fencing token；
- 幂等键。

---

# LingShu Redis 后端建议

## 1. 独立能力包

```text
backends/redis/
├── backend.py
├── cache.py
├── lock.py
├── limiter.py
├── idempotency.py
├── operation.py
├── counter.py
├── stream.py
├── pubsub.py
├── serializer.py
└── errors.py
```

不将这些能力塞进一个巨型 `redis.py`。

## 2. Cache

候选体验：

```python
await db.redis.cache.set(
    "user:1",
    user,
    ttl=300,
    namespace="users",
)

user = await db.redis.cache.get(
    "user:1",
    namespace="users",
)
```

默认要求：

- namespace；
- TTL；
- serializer；
- 最大 value 大小；
- tenant/project 隔离；
- 是否允许缓存空值；
- 是否允许 stale 数据；
- cache key 版本。

禁止无 TTL 的普通业务缓存，除非策略明确允许。

## 3. Cache stampede

框架需要至少支持：

```text
single-flight
soft TTL + hard TTL
jitter
negative cache
refresh-ahead（可选）
```

候选：

```python
value = await cache.get_or_load(
    key,
    loader=load_from_db,
    ttl=300,
    stale_ttl=30,
    single_flight=True,
)
```

要求：

- 同一个 key 只允许一个 loader；
- loader 失败不能让所有等待者无限挂起；
- 空值缓存必须有短 TTL；
- TTL 增加随机抖动，避免同一时刻大量过期。

## 4. Lock

候选：

```python
async with db.redis.lock.acquire(
    "order:1001",
    ttl=10,
    wait_timeout=2,
    auto_renew=False,
) as lease:
    ...
```

锁对象必须包含：

```text
key
owner_token
acquired_at
expires_at
fencing_token（可选后端）
```

规则：

- 释放必须校验 owner；
- wait_timeout 和 ttl 分开；
- 自动续约默认关闭或非常谨慎；
- 取消时尽力释放，但不能假设一定成功；
- 锁失效后业务必须能够检测；
- 关键数据库写入优先使用 version/fencing 检查。

## 5. IdempotencyStore

候选状态：

```text
reserved
processing
succeeded
failed
unknown
expired
```

候选接口：

```python
record = await db.redis.idempotency.reserve(
    key=idempotency_key,
    fingerprint=request_fingerprint,
    ttl=86400,
)
```

要求：

- 同 key 同 fingerprint 返回原结果或原状态；
- 同 key 不同 fingerprint 拒绝；
- reserve 必须原子；
- processing 超时后不能直接认为未执行；
- 敏感 payload 不直接存入 Redis；
- 大响应存引用，不存无限大正文；
- 最终业务正确性仍需数据库唯一约束。

## 6. OperationStore

用于解决网络抖动后的结果未知：

```python
await operations.create(operation_id, status="pending")
await operations.succeed(operation_id, result_ref=...)
await operations.fail(operation_id, error_code=...)
```

前端可以查询：

```text
pending
paused
retrying
unknown
succeeded
failed
cancelled
```

OperationStore 可以先用 Redis，但合同不能绑定 Redis，将来可换数据库实现。

## 7. RateLimiter

必须明确算法：

```text
fixed window
sliding window
token bucket
leaky bucket
concurrency limiter
```

不能只有：

```python
incr(key)
```

限流维度至少支持：

- IP；
- user；
- tenant；
- route；
- API key；
- external provider；
- project/task。

返回稳定的剩余额度、重试时间和错误码。

## 8. Stream / PubSub

明确边界：

- Pub/Sub：在线即时广播，不保证离线消费和持久重放；
- Stream：持久消息、consumer group、pending、ack、claim；
- 关键任务不能使用纯 Pub/Sub 作为唯一通道。

Stream adapter 必须处理：

- ack/nack；
- retry；
- pending recovery；
- dead-letter；
- max length；
- consumer identity；
- 重复消息幂等。

## 9. Pipeline 与批量

候选：

```python
async with db.redis.pipeline(transaction=False) as pipe:
    pipe.get("a")
    pipe.get("b")
```

规则：

- 命令数和总 payload 有上限；
- pipeline 失败返回每条命令的错误明细；
- 大 pipeline 分块；
- transaction 参数必须显式；
- 取消时正确丢弃/关闭连接。

## 10. 序列化

默认安全序列化：

- JSON / MessagePack 等明确格式；
- 禁止默认 pickle 反序列化不可信数据；
- 数据结构带版本；
- 压缩有大小阈值和解压上限；
- secret、token、cookie 不应明文长期缓存。

## 11. Key 设计与运维保护

统一 key 构造器：

```text
{environment}:{app}:{tenant}:{capability}:{version}:{business_key}
```

需要检测：

- big key；
- hot key；
- 无 TTL key；
- key 数量增长；
- 慢命令；
- pool 使用率；
- timeout；
- reconnect；
- eviction；
- memory pressure。

普通业务 API 禁止：

- `KEYS *`；
- 无边界 scan 结果一次性加载；
- 阻塞式危险命令；
- 任意 Lua；
- 任意 key 前缀删除。

---

# Redis 与其他数据库的边界

| 场景 | Redis 定位 | 最终正确性来源 |
|---|---|---|
| 普通缓存 | 加速读取 | MySQL/MongoDB |
| 幂等结果 | 快速去重和状态 | 业务唯一约束/状态机 |
| 分布式锁 | 协调并发 | version/fencing/数据库约束 |
| 限流 | 流量控制 | Redis 原子脚本/命令 |
| 任务进度 | 临时状态 | 任务数据库或可恢复记录 |
| Pub/Sub | 在线通知 | 不作为可靠事实存储 |
| Stream | 可恢复消息 | consumer 幂等 + ack 状态 |

---

# 初步拒绝项

- Redis 通用 ORM。
- 默认无 TTL 缓存。
- 直接 `DEL` 释放锁。
- 认为拿到 Redis 锁就绝不会重复写。
- 将 pipeline 当成事务。
- 使用 pickle 处理不可信缓存数据。
- 用 Pub/Sub 承载不可丢失任务。
- 业务代码自行拼接无规范 key。
- 无限重试 Redis 连接和命令。
- 故障时静默绕过限流、幂等或锁而不记录。

---

# 必须验证的测试

1. pipeline 减少往返且保持结果顺序；
2. pipeline 部分错误和分块；
3. 锁 owner 校验；
4. 锁 TTL 到期后旧 owner 释放不影响新 owner；
5. 锁失效后的业务写保护；
6. fencing token 顺序；
7. idempotency 同 key 同参数复用；
8. 同 key 不同参数冲突；
9. 100/1000 并发 reserve 只有一个执行者；
10. cache stampede single-flight；
11. negative cache 与 TTL jitter；
12. big key/value 拒绝；
13. 无 TTL 策略拒绝；
14. Stream 重复投递和 pending recovery；
15. pool 耗尽和命令 timeout；
16. Sentinel/Cluster 切换下的明确失败语义；
17. graceful shutdown 关闭连接和停止续约任务。

## 官方资料

- Redis Pipelining: https://redis.io/docs/latest/develop/using-commands/pipelining/
- Redis Distributed Locks: https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/
