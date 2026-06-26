# ADR：LingShu API 安全请求执行链

- 状态：Draft
- 阶段：Phase C0 研究
- 范围：HTTP API 请求进入 handler 前后的安全执行顺序

## 背景

当前 `RoutePolicy` 只有少量布尔字段，无法表达：

- 多种认证方式；
- 服务间请求签名；
- 多租户；
- 资源级授权；
- 幂等；
- 限流；
- 并发限制；
- 请求体限制；
- 超时和审计等级。

安全能力如果由各控制器自行调用，会导致：

- 执行顺序不一致；
- 某些路由漏掉校验；
- 认证失败后仍执行数据库查询；
- 无效签名仍消耗大量资源；
- 限流和幂等边界混乱；
- 错误响应不一致；
- 安全测试难以覆盖。

## 决策

采用编译后的 RoutePolicy 与固定安全执行链。

候选顺序：

```text
0. transport/request guard
1. route policy resolution
2. maintenance gate
3. coarse pre-auth rate limit
4. request signature + timestamp + replay check（按策略）
5. authentication
6. tenant/context resolution
7. fine-grained rate/concurrency limit
8. authorization gate/policy
9. schema validation + canonical operation fingerprint
10. idempotency reservation（按策略）
11. handler / transaction / business operation
12. idempotency finalization + operation status
13. response security headers + audit + cleanup
```

不是所有路由都启用每一步，但顺序固定，跳过行为必须由已编译策略决定。

## 0. Transport / Request Guard

最先处理：

- trusted proxy；
- method/path 基础合法性；
- header 数量与大小；
- body 最大长度；
- content type；
- request timeout budget；
- request_id / trace_id；
- raw body 保存策略。

原因：验签、JSON解析和认证之前必须先限制资源消耗。

## 1. Route Policy Resolution

RoutePolicy 在应用启动时编译并冻结：

- 全局默认；
- blueprint/controller 级配置；
- route 级配置；
- 显式覆盖规则。

启动时检查：

- 安全路由是否缺少认证；
- 幂等是否用于支持的方法；
- 签名策略是否配置 replay store；
- Policy 名称是否注册；
- 限流策略是否存在；
- 路由是否尝试放宽不可覆盖的全局安全底线。

运行时不得动态拼接模糊策略。

## 2. Maintenance Gate

维护模式在昂贵认证和数据库访问之前执行。

策略支持：

- 全局维护；
- 模块/版本维护；
- 只读模式；
- 白名单 principal/client；
- Retry-After；
- 503 结构化响应。

安全健康检查、内部运维接口可按独立策略放行。

## 3. Coarse Pre-auth Rate Limit

在未识别身份前，按可信网络信息做粗限流：

- 来源 IP；
- API host；
- route group；
- body size class。

它只负责降低暴力请求和资源消耗，不能替代认证后的用户/租户限流。

## 4. Signature / Replay

签名路由必须在 JSON 重新序列化前使用 raw body bytes。

验证顺序：

1. version/algorithm/key_id 格式；
2. timestamp 窗口；
3. body digest；
4. canonical request；
5. constant-time signature compare；
6. nonce reserve/replay check。

签名成功可以提供 client identity，但不自动代表业务用户身份或资源权限。

## 5. Authentication

Authenticator 只回答：

```text
凭据是否存在
凭据是否合法
principal 是谁
认证方式和可信等级是什么
```

支持：

- session；
- bearer/JWT；
- API key；
- signed service client；
- custom extension。

多认证器规则：

- `not_applicable` 才可尝试下一种；
- `invalid/expired/revoked` 立即失败；
- 禁止从强认证无效自动降级为弱认证；
- RoutePolicy 明确允许的 scheme 才可使用。

## 6. Tenant Resolution

tenant/workspace 必须从可信绑定产生：

- principal membership；
- API key binding；
- signing key binding；
- 受控管理员切换。

客户端传入 tenant header 只能作为选择提示，必须校验其属于当前 principal。

TenantContext 建立后，数据库和缓存层才允许执行租户隔离操作。

## 7. Fine Rate / Concurrency Limit

身份建立后按以下组合限流：

```text
principal
client_id
tenant
route
resource class
external provider
```

请求速率和同时执行数量分开：

- RateLimiter：时间窗口内请求数量；
- ConcurrencyLimiter：当前正在执行数量。

## 8. Authorization

分两层：

### Gate / Route Authorization

检查：

- authenticated；
- scope；
- permission；
- system action；
- tenant membership。

### Resource Policy

检查：

- action；
- resource/object；
- owner；
- resource tenant；
- resource state；
- principal attributes；
- environmental context。

对需要读取资源才能授权的接口，应使用受控 repository 先按 tenant 加载最小授权字段，再执行 Policy。

最终默认拒绝。

## 9. Schema Validation 与 Fingerprint

先完成不产生业务副作用的请求验证：

- content schema；
- 类型；
- 字段 allowlist；
- body size/depth；
- route params；
- canonical body。

然后计算 operation fingerprint。

验证失败不创建成功幂等记录；避免客户端修正参数后仍被旧错误锁定。

## 10. Idempotency Reservation

仅对策略要求的写操作执行。

原子 reserve 结果：

```text
owner            -> 当前请求负责执行
replay           -> 返回已完成结果
in_progress       -> wait / 202 / 409（路由策略）
conflict          -> 同 key 不同 fingerprint
unknown           -> 进入 operation reconciliation
```

IdempotencyStore 不是业务数据库唯一约束的替代。

## 11. Handler

进入 handler 前，以下上下文已经建立：

```text
request_id / trace_id
route_policy
principal
tenant_context
authorization_context
idempotency_record
timeout_budget
```

Handler 不应重复解析 token、tenant 和幂等键。

## 12. Finalization

根据 handler/事务真实结果更新：

```text
succeeded
failed
unknown
cancelled
```

规则：

- 数据库 commit 成功后才标记业务成功；
- commit 结果不确定时不得标记失败并鼓励盲目重试；
- response 发送失败不代表业务失败；
- 可恢复结果应通过 operation_id 查询；
- 500 是否缓存由 RoutePolicy 决定。

## 13. Response / Audit / Cleanup

统一处理：

- 401 `WWW-Authenticate`；
- 429 `Retry-After`；
- request_id / operation_id；
- 安全响应头；
- 安全审计事件；
- ContextVar 清理；
- 锁、lease、限流 token 和资源释放；
- 敏感日志脱敏。

## RoutePolicy 候选结构

```python
RoutePolicy(
    maintenance="check",
    authentication=("bearer",),
    signature=None,
    tenant="required",
    authorization="orders.order.update",
    idempotency="required",
    rate_limit="write-default",
    concurrency_limit="tenant-write",
    body_limit=1_048_576,
    timeout=10,
    audit="security",
)
```

具体 API 待研究冻结。

## 被拒绝方案

- 控制器手工拼接认证、权限、限流和幂等；
- 只靠 middleware 顺序约定而无启动期验证；
- invalid credential 自动尝试更弱认证；
- tenant 在认证前直接从 header 注入；
- handler 执行后才检查写权限；
- body 无大小限制直接计算签名或解析 JSON；
- schema 验证失败仍占用幂等 key；
- response 断开即把业务标记失败。

## 验收条件

1. 所有路由都有可检查的编译后策略；
2. 安全步骤执行顺序可测试、不可被控制器绕过；
3. raw body 验签发生在重编码前；
4. invalid credential 不降级；
5. tenant 只来自可信绑定；
6. 认证与资源 Policy 分离；
7. schema validation 在幂等执行前完成；
8. 并发同 key 只有一个 owner；
9. commit 不确定能进入 unknown；
10. 所有退出路径清理 ContextVar 和 lease；
11. 日志不包含 secret/token/full signature；
12. 安全依赖不可用时按策略 fail-closed 或明确降级并审计。