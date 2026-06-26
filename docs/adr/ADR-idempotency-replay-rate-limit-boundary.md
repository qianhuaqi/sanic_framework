# ADR：幂等、防重放与限流边界

- 状态：Draft
- 阶段：Phase C0 研究
- 范围：LingShu API 写请求、签名请求与流量治理

## 背景

幂等、防重放和限流经常被混在一起，但三者解决的问题不同：

```text
幂等：允许客户端安全重试同一个业务操作
防重放：拒绝攻击者或错误客户端再次发送同一个已签名请求
限流：限制单位时间或同时执行的请求数量
```

如果混用会产生严重问题：

- 用 nonce 防重放后，正常网络重试也被拒绝；
- 用幂等键代替签名，不能证明请求身份和完整性；
- 用限流代替幂等，低频重复请求仍会重复执行；
- 同一个 Redis key 同时承担三种语义，状态难以恢复和审计。

## 决策

三种能力使用独立协议、独立状态和独立存储接口，可以共享 Redis 等物理后端，但不得共享业务 key 空间和状态机。

---

# 一、Request Replay Protection

## 目标

验证签名请求：

- 来自已知 key；
- 在允许时间窗口内；
- method/path/query/body 未被篡改；
- 相同 nonce 没有在窗口内使用过。

## 候选签名头

```text
X-LingShu-Signature-Version
X-LingShu-Key-Id
X-LingShu-Timestamp
X-LingShu-Nonce
X-LingShu-Content-SHA256
X-LingShu-Signature
```

## Canonical Request

```text
METHOD
CANONICAL_PATH
CANONICAL_QUERY
CANONICAL_HEADERS
SIGNED_HEADERS
CONTENT_SHA256
TIMESTAMP
NONCE
```

规则必须冻结并提供跨语言测试向量：

- path 编码；
- query 排序；
- 重复 query 参数；
- header 名小写；
- header 空白归一化；
- 空 body；
- Unicode；
- content type；
- 原始 body bytes。

## ReplayStore

接口候选：

```python
await replay_store.reserve(
    key_id=key_id,
    nonce=nonce,
    timestamp=timestamp,
    ttl=window,
)
```

reserve 必须原子。重复返回 `ReplayDetected`。

ReplayStore 只保存短期 nonce 使用记录，不保存业务结果。

## 时间窗口

- 按 route/signature profile 配置；
- 默认分钟级；
- 明确允许 clock skew；
- 服务端使用可靠时钟；
- 超窗请求拒绝；
- 响应可返回服务器时间提示，但不能泄漏更多安全信息。

---

# 二、Idempotency

## 目标

对于客户端因超时、断网、进程重启而重试的同一个业务意图：

- 最多执行一次业务副作用；
- 或重复请求可查询/复用第一次结果；
- 同一个 key 不允许表示不同业务参数。

## Idempotency Key

候选 header：

```text
Idempotency-Key
```

约束：

- 客户端生成高熵随机值或稳定业务操作 ID；
- 不包含敏感个人信息；
- 最大长度受限；
- namespace 至少包含 tenant/client/route；
- GET/HEAD 默认不需要；
- DELETE 是否要求由路由语义决定，不能简单假定所有 DELETE 都业务幂等。

## Fingerprint

```text
HTTP method
route identity
canonical path parameters
canonical validated body
selected semantic headers
tenant/client identity
```

不应包含：

- request_id；
- trace_id；
- 无关时间戳；
- 签名值本身。

同 key 不同 fingerprint 返回 `IdempotencyConflict`。

## 状态机

```text
reserved
processing
succeeded
failed
unknown
cancelled
expired
```

记录候选字段：

```text
namespace
idempotency_key
fingerprint
owner_token
operation_id
status
response_status
result_ref
error_code
lease_expires_at
created_at
updated_at
expires_at
```

## 并发重复请求

同 key 并发进入时，只有一个 owner。

非 owner 按 RoutePolicy 选择：

- 短暂等待结果；
- 返回 202 + operation_id；
- 返回 409 in-progress；
- 已完成时直接 replay。

禁止两个请求都进入 handler。

## 结果策略

### 成功

保存稳定 response 摘要或 result reference。

### 确定失败

业务校验、数据库约束等确定失败是否保存由策略决定。一般：

- handler 执行前 schema validation 失败不占用 key；
- 进入业务执行后的确定业务失败可保存；
- 同 key 重试返回同一业务结果。

### 500 / 系统失败

不统一默认缓存所有 500。

RoutePolicy 可选择：

```text
replay-all
replay-success-and-business-failure
operation-status-only
```

### Unknown

出现以下情况进入 unknown：

- 数据库 commit 返回前连接中断；
- 外部服务结果未知；
- 进程在副作用后、记录结果前崩溃。

unknown 不能直接允许重新执行。需要：

- operation reconciliation；
- 查询业务唯一记录；
- 人工或自动恢复；
- 最终转 succeeded/failed。

## 最终正确性

IdempotencyStore 不替代：

- 数据库 unique constraint；
- optimistic version；
- business operation id；
- state machine；
- Outbox/Inbox。

---

# 三、Rate Limiting

## 目标

控制：

- 暴力登录；
- API 滥用；
- 单租户资源占用；
- 外部供应商调用频率；
- 突发流量；
- 后端过载。

## Rate 与 Concurrency 分离

```text
RateLimiter        -> 时间窗口内允许多少请求
ConcurrencyLimiter -> 同时允许多少请求执行
```

例如一个 30 秒长请求，即使每分钟只有 10 次，也可能积累 5 个并发；必须分别限制。

## 限流维度

支持组合：

```text
IP
principal
client_id
API key
tenant
route
resource class
external provider
```

不能只使用 IP：共享 NAT 会误伤，攻击者也可能分散 IP。

## 算法

候选能力：

```text
fixed window
sliding window
token bucket
leaky bucket
concurrency semaphore
```

框架不应假装所有算法相同。每个 Policy 明确算法、容量、补充速率和存储。

## 多窗口

支持：

```text
3 / second
20 / 10 seconds
100 / minute
```

短窗口防突发，长窗口防持续滥用。

## Store

- Memory：开发、测试、单进程参考；
- Redis：分布式部署扩展；
- 未来可增加网关/外部限流器。

Store 不可用时：

```text
fail_closed
fail_open_with_audit
local_fallback
```

按路由等级配置。登录、验证码、支付等高风险接口默认不允许静默失去限流。

## Trusted Proxy

来源 IP 解析只信任明确配置的代理链。

- 不无条件信任 `X-Forwarded-For`；
- 明确 trusted proxy CIDR / hop count；
- 保存解析前后的诊断信息但日志脱敏；
- 测试伪造 header。

## 响应

```text
HTTP 429
Retry-After
稳定错误码
request_id
```

可选返回剩余额度，但不得泄漏内部安全策略细节。

---

# 四、三种能力的组合顺序

签名写请求候选：

```text
coarse rate limit
-> signature verify
-> replay nonce reserve
-> authentication/tenant
-> fine rate/concurrency limit
-> authorization
-> schema validation
-> idempotency reserve
-> handler
```

说明：

- replay nonce 是“这份签名报文是否已用过”；
- idempotency key 是“这个业务操作是否已执行”；
- 正常客户端重试必须生成新的 timestamp/nonce/signature，但可以复用同一个 idempotency key。

---

# 五、存储命名空间

即使都使用 Redis，key 也必须分离：

```text
replay:{key_id}:{nonce}
idempotency:{tenant}:{route}:{key}
rate:{policy}:{tracker}:{window}
concurrency:{policy}:{tracker}
```

每类有独立 TTL、序列化、指标和清理策略。

---

# 六、被拒绝方案

- nonce 与 idempotency key 使用同一个字段；
- 同一个 key 状态机同时承担 replay/idempotency/rate；
- timestamp 合法就不存 nonce；
- 幂等记录处于 unknown 时重新执行；
- 所有 500 无条件缓存或无条件重试；
- 限流只看 IP；
- 分布式部署使用每进程内存限流并声称全局一致；
- Redis 不可用时所有安全策略静默失效；
- `X-Forwarded-For` 无条件可信。

## 验收条件

1. 正常重试使用新 nonce + 同 idempotency key 成功复用；
2. 相同签名 nonce 重放被拒绝；
3. 同 idempotency key 不同参数冲突；
4. 100/1000 并发相同 key 只有一个 owner；
5. unknown 状态不重复执行；
6. 业务唯一约束与幂等记录故障组合测试；
7. 多窗口限流；
8. rate 与 concurrency 独立生效；
9. trusted proxy 伪造测试；
10. Redis 故障策略按 route policy 生效；
11. key namespace、TTL 和敏感信息检查；
12. 指标能区分 replay、idempotency conflict、rate exceeded 和 concurrency exceeded。