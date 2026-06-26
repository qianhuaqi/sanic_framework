# 安全、授权、签名、幂等与限流第一批对比

> 状态：第一批安全研究结论，不是最终公共 API 冻结稿。
>
> 样本：Spring Security、Symfony Security、Laravel Authorization、Django Auth、NestJS Guards/Throttler、Apache Casbin、AWS SigV4、Stripe Idempotency、GitHub Webhook Signature。

## 研究目标

LingShu API 的安全层不能只有一个 `auth_required` 开关。必须回答：

1. 认证和授权如何分离；
2. 路由级权限和资源级权限如何组合；
3. 多租户上下文何时建立；
4. 请求签名如何覆盖 method/path/query/body；
5. 防重放与幂等为什么不是一回事；
6. 限流如何同时支持 IP、用户、租户、路由和外部服务；
7. 安全错误如何稳定、可审计且不泄漏敏感信息；
8. 多种认证方式如何避免自动降级到较弱方案。

---

# 一、Spring Security

## 值得吸收

Spring Security 将认证结果保存在 Authentication 中，授权由 AuthorizationManager 读取 principal、authority 和被保护对象后做最终决策。AuthorizationManager 可用于请求、方法和消息级授权，也支持组合多个授权管理器。

它的关键经验：

- 认证负责回答“你是谁”；
- authority/claim 只是授权输入，不是最终授权逻辑；
- 授权必须拿到 secure object / invocation context；
- 可以做 pre-invocation 与 post-invocation 决策；
- 支持 role hierarchy，但复杂业务不应只靠角色字符串。

## LingShu 裁决

`adopt/adapt`

- 分离 `Authenticator` 与 `AuthorizationPolicy`；
- 路由权限只是第一层，资源级权限必须拿到业务对象或资源标识后判断；
- 支持 policy composition；
- 内部可以有 allow/deny/abstain，最终必须 default-deny；
- role hierarchy 作为可选能力，不作为复杂授权的唯一模型；
- post-authorization 只用于字段过滤或结果保护，不允许把明显应提前拒绝的写操作拖到执行后。

---

# 二、Symfony Security

## 值得吸收

Symfony 以 firewall 定义请求由哪套认证系统处理；每个请求只匹配一个 firewall，且匹配顺序非常重要。认证完成后，再通过 access control、authorization checker 与 voter 处理权限。

Voter 适合资源级规则，例如“用户只能编辑自己的文章”。Symfony 还明确区分不同 firewall 的认证状态，不会默认在多个安全域之间共享。

## LingShu 裁决

`adapt`

- 路由必须先解析唯一 SecurityProfile，而不是同时命中多套模糊认证链；
- 不同 API 域可配置不同认证方式，例如 public、session、bearer、signed-service；
- 多认证器顺序必须显式；
- 一个认证器返回“未提供凭据”可交给下一认证器，但“凭据无效”不能静默降级；
- 资源授权采用 Policy/Voter 风格；
- 不同安全域之间的 principal 不自动共享。

---

# 三、Laravel Gate / Policy

## 值得吸收

Laravel 将 Gate 用于与模型无关的动作，将 Policy 用于围绕模型或资源组织授权规则。Policy 的方法直接接收用户和资源实例，清晰表达 create、view、update、delete 等动作。

## LingShu 裁决

`adopt`

- 引入 `Gate` 与 `Policy` 两层概念：
  - Gate：系统级动作，例如查看后台、导出全局报表；
  - Policy：资源级动作，例如更新某订单、删除某素材；
- Policy 与 Model 可以按约定发现，但生产环境启动时必须完成注册校验；
- 未找到 Policy、未定义动作、返回不明确结果时默认拒绝；
- 403 由统一异常层转换，不允许控制器自行拼接。

候选：

```python
await authorize("admin.dashboard.view")
await authorize("update", order)
```

---

# 四、Django Permission

## 值得吸收

Django 使用 `app_label.permission_codename` 表达稳定权限，并提供装饰器和 mixin 在入口处执行权限检查。认证失败与权限不足可以映射为不同处理。

## LingShu 裁决

`adapt`

- 权限标识采用稳定命名空间：

```text
module.resource.action
orders.order.read
orders.order.update
system.audit.export
```

- 支持单权限、all-of、any-of；
- 区分未认证与已认证但无权限；
- API 默认使用 401/403，不做 Web 登录重定向；
- 权限常量可由 Schema/CLI 生成并进入 contract check。

---

# 五、NestJS Guard

## 值得吸收

NestJS 将认证的通用 token 解析放在 middleware/guard，将依赖具体 handler metadata 的授权放在 Guard。Guard 在 middleware 之后、interceptor/pipe 之前执行，并可以读取即将执行的 handler 与 metadata。

## LingShu 裁决

`adapt`

- RoutePolicy 必须在 handler 执行前可读取；
- Authentication 与 Authorization 都应有清晰执行位置；
- 路由、controller/blueprint、全局策略支持明确覆盖规则；
- 不允许装饰器元数据与全局策略产生不可预测的覆盖；
- 启动时编译 RoutePolicy，运行时只读取已冻结策略。

---

# 六、Apache Casbin

## 值得吸收

Casbin 支持 ACL、RBAC、带 domain 的 RBAC、ABAC、ReBAC、priority model 等多种授权模型，说明授权引擎必须将 subject、object、action、domain/context 分开，而不是只判断角色字符串。

## LingShu 裁决

`extension/adapt`

- LingShu 核心提供 Policy 协议，不直接内置完整 Casbin 引擎；
- Policy 输入至少包含：

```text
principal
subject attributes
resource/object
action
tenant/domain
request context
```

- RBAC 是默认简单实现；
- ABAC、ReBAC、Casbin/OPA 作为扩展；
- 外部策略引擎失败时的 fail-open/fail-closed 必须按路由安全等级配置，默认 fail-closed。

---

# 七、AWS SigV4

## 值得吸收

AWS SigV4 先构造 canonical request，再计算签名，并将请求 method、path、query、headers 与 body digest 纳入签名。服务端重新计算并比较。时间戳窗口用于降低重放风险。

## LingShu 裁决

`adapt`

LingShu 服务间签名候选内容：

```text
version
key_id
algorithm
HTTP method
canonical path
canonical query
selected canonical headers
timestamp
nonce
SHA-256(raw body)
```

候选签名：

```text
HMAC-SHA256(secret, canonical_request)
```

要求：

- 签名版本显式；
- canonicalization 规则冻结并提供跨语言测试向量；
- 使用原始 body bytes 计算 digest；
- 比较使用 constant-time compare；
- timestamp 超窗拒绝；
- nonce/key_id/window 进入 replay store；
- secret 支持轮换，验证期可同时接受 current/previous key；
- key_id、signature、nonce 不进入普通业务日志全文；
- body size 在计算 hash 前受限。

不直接照搬 AWS region/service/date 派生密钥复杂度，除非后续多区域场景证明需要。

---

# 八、GitHub Webhook Signature

## 值得吸收

GitHub 使用高熵 secret 对原始 payload 做 HMAC-SHA256，并要求使用 constant-time compare，避免普通字符串比较带来的 timing attack。

## LingShu 裁决

`adopt`

- Webhook 验签独立于普通用户 JWT 认证；
- 原始 payload 在任何 JSON 重编码前验签；
- 使用 `sha256=` 等版本化前缀或明确 algorithm header；
- webhook secret 不硬编码、不进入仓库；
- 验签失败统一返回安全错误，不暴露期望签名；
- delivery_id 进入去重/重放记录。

---

# 九、Stripe Idempotency

## 值得吸收

Stripe 允许客户端为写请求提供幂等键；服务端保存首次执行结果，后续同键请求返回同一结果。相同 key 但参数不一致会被拒绝。验证失败或尚未真正进入 endpoint execution 的并发冲突不保存结果。

## 需要调整

Stripe 会保存包括 500 在内的首次结果。LingShu 不应默认无条件复制这一行为，因为：

- 某些 500 发生在副作用前；
- 某些 500 发生在副作用后；
- 如果框架无法知道结果，缓存 500 可能把可恢复操作永久固定为失败；
- 盲目重试又可能重复执行。

## LingShu 裁决

`adapt`

- idempotency key 命名空间：tenant/client/route/key；
- 使用 canonical fingerprint 比较 method、route、body 与关键 headers；
- 同 key 不同 fingerprint 返回冲突；
- 保存 operation 状态，不只缓存 HTTP response；
- 500 是否复用由 RoutePolicy 指定；
- `unknown` 是正式状态；
- 数据库唯一约束和业务状态机仍是最终正确性保障；
- key 不允许包含手机号、邮箱等敏感数据；
- TTL 路由可配置。

---

# 十、NestJS Throttler

## 值得吸收

NestJS Throttler 支持全局/路由策略、多组时间窗口、自定义 tracker/key/storage，并提醒代理环境必须正确配置 trusted proxy，否则 IP 识别会错误。

## LingShu 裁决

`adapt`

- 支持多个命名限流策略，例如 short/medium/long；
- RoutePolicy 可以覆盖或收紧，默认不能随意关闭关键安全端点限流；
- tracker 支持 IP、principal、API key、tenant、route、external provider；
- trusted proxy 必须显式配置，不能无条件信任 `X-Forwarded-For`；
- 内存 store 仅用于开发/单进程参考；Redis store 作为分布式扩展；
- RateLimiter 与 ConcurrencyLimiter 分离；
- 返回 429、Retry-After 和结构化错误；
- store 故障时 fail-open/fail-closed 按策略决定，并必须记录审计事件。

---

# 十一、LingShu 安全模型初步结构

## Principal

```text
principal_id
authentication_method
authentication_time
assurance_level
scopes
authorities
claims
token_id
client_id
```

敏感凭据和原始 token 不放入 Principal。

## TenantContext

```text
tenant_id
workspace_id
membership_id
roles
permissions
```

tenant 不允许仅从客户端 header 直接信任，必须通过已认证 principal、API key binding 或签名 key binding 解析。

## RoutePolicy

候选字段：

```text
maintenance_check
authentication_schemes
signature_policy
tenant_required
authorization_policy
permissions/scopes
idempotency_policy
rate_limit_policy
concurrency_policy
body_limit
timeout_policy
audit_level
```

## Authenticator

候选接口：

```python
class Authenticator:
    async def authenticate(request, policy) -> AuthResult: ...
```

结果必须区分：

```text
not_applicable
authenticated
invalid_credentials
expired
revoked
unavailable
```

`invalid_credentials` 不允许自动尝试更弱认证方式。

## AuthorizationPolicy

候选：

```python
result = await policy.authorize(
    principal=principal,
    action="order.update",
    resource=order,
    context=security_context,
)
```

最终结果：

```text
allow
deny
```

内部组合可以有 abstain，但最终 default deny。

---

# 十二、认证与授权错误

统一错误大类：

```text
AuthenticationRequired      -> 401
InvalidCredential           -> 401
CredentialExpired           -> 401
AccessDenied                -> 403
TenantRequired              -> 403/400（按接口合同）
SignatureRequired           -> 401
InvalidSignature            -> 401
ReplayDetected              -> 409/401（按签名协议固定）
RateLimitExceeded           -> 429
IdempotencyConflict         -> 409
SecurityDependencyUnavailable -> 503
```

原则：

- 不把内部 exception、token 内容、签名原文返回客户端；
- 401 可返回适当 `WWW-Authenticate`；
- 某些资源为了避免存在性泄漏，可由 Policy 映射为 404；
- 每次拒绝记录安全事件，但日志脱敏并限频。

---

# 十三、初步拒绝项

- 认证和授权混在同一个布尔函数；
- 只凭 `role == admin` 处理所有资源权限；
- 多认证器遇到无效凭据后自动降级；
- tenant_id 直接信任请求 header；
- JWT claims 作为永久实时权限唯一来源；
- 签名只覆盖 body、不覆盖 path/query/method；
- 普通字符串比较签名；
- 用幂等键替代数据库唯一约束；
- 用 replay nonce 替代幂等机制；
- 仅按 IP 限流；
- 无条件信任反向代理 header；
- 限流 Redis 故障时静默放行且不审计。

---

# 十四、必须验证的测试

1. 多认证器中 invalid credential 不降级；
2. anonymous、expired、revoked、invalid 映射稳定；
3. RoutePolicy 覆盖规则确定且启动时可检查；
4. 权限 any/all、Gate、resource Policy；
5. tenant header 无法绕过可信绑定；
6. role hierarchy 无循环；
7. canonical request 跨 Python/Go/TypeScript 测试向量一致；
8. query 排序、重复参数、URL 编码、header 大小写的 canonicalization；
9. raw body digest；
10. constant-time compare；
11. timestamp 超窗；
12. nonce 并发重复只允许一次；
13. key rotation；
14. webhook delivery 去重；
15. idempotency 同 key 同 fingerprint；
16. 同 key 不同 fingerprint 冲突；
17. 首请求执行中并发重复的 wait/202/409 策略；
18. unknown operation 恢复；
19. 多维度限流；
20. trusted proxy 与伪造 X-Forwarded-For；
21. Redis store 故障策略；
22. 安全日志无 token/secret/signature/body 泄漏。

## 官方资料

- Spring Security Authorization Architecture: https://docs.spring.io/spring-security/reference/servlet/authorization/architecture.html
- Symfony Security: https://symfony.com/doc/current/security.html
- Laravel Authorization: https://laravel.com/docs/12.x/authorization
- Django Auth: https://docs.djangoproject.com/en/5.2/topics/auth/default/
- NestJS Guards: https://docs.nestjs.com/guards
- NestJS Rate Limiting: https://docs.nestjs.com/security/rate-limiting
- Apache Casbin Overview: https://casbin.apache.org/docs/overview/
- AWS Signature Version 4: https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_sigv.html
- Stripe Idempotent Requests: https://docs.stripe.com/api/idempotent_requests
- GitHub Webhook Signature: https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries
