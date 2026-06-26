# ADR：Schema 合同分层与验证边界

- 状态：Draft
- 阶段：Phase C0 研究
- 范围：LingShu API 输入、领域命令、持久化模型与输出合同

## 背景

将数据库 Model 直接用作请求与响应 Schema，看似省代码，实际会导致：

- 客户端可写入内部字段；
- ORM 新增字段意外暴露给 API；
- Create、Update、Patch、Admin 等约束相互冲突；
- 数据库关系和 lazy loading 混入序列化；
- 输入转换、业务规则与持久化状态耦合；
- OpenAPI 与真实运行行为漂移；
- 前端、SDK 和 AI 工具无法得到稳定合同。

## 决策

LingShu 建立独立 Schema 合同层，并明确五种模型边界：

```text
Transport Schema
Input Schema
Domain Command / Mutation
Persistence Model
Output Schema
```

它们可以共享字段片段和类型定义，但不得默认由同一类同时承担全部职责。

## Transport Schema

负责 HTTP 数据来源：

```text
path
query
header
cookie
body
file
```

每个字段来源必须明确。禁止同名字段在多个来源之间隐式猜测。

示例：

```python
class GetUserPath(PathSchema):
    user_id: UserId

class ListUserQuery(QuerySchema):
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)
```

## Input Schema

负责不可信外部数据：

```python
class CreateUserInput(BodySchema):
    name: str
    email: Email
```

默认：

- extra fields forbidden；
- 有最大长度、数量和深度；
- 字段是 mass-assignment allowlist；
- 自定义 validator 无 I/O 和副作用；
- 不包含 tenant、role、审计、version 等服务端字段。

## Domain Command / Mutation

在认证、Tenant 和业务上下文建立后由服务端构造：

```python
CreateUserCommand(
    tenant_id=tenant.id,
    actor_id=principal.id,
    name=input.name,
    email=input.email,
    operation_id=request.operation_id,
)
```

它可以包含服务端可信字段和业务上下文，不直接接受原始 HTTP payload。

## Persistence Model

```text
TableModel
DocumentModel
```

负责：

- 数据库字段；
- 映射；
- 事务；
- 关系/索引；
- 乐观锁；
- 持久化生命周期。

Persistence Model 不自动决定 API 可写和可见字段。

## Output Schema

```python
class UserDetailOutput(OutputSchema):
    id: UserId
    name: str
    email: str
```

负责：

- 响应字段白名单；
- alias；
- datetime/Decimal/enum 序列化；
- OpenAPI response；
- SDK 类型；
- 安全过滤。

ORM/ODM 对象只有经过 OutputSchema 映射后才能作为正式 API 响应。

## Schema Engine

Python 第一版候选使用 Pydantic，但业务 API 通过 LingShu facade：

```text
lingshu.schema
```

目的：

- 统一默认安全配置；
- 统一错误结构；
- 保留未来替换或升级 Schema 引擎的边界；
- 防止业务代码依赖大量引擎内部细节。

## Strict Profile

### Body Profile

- extra forbidden；
- 安全敏感类型严格；
- 禁止模糊 bool；
- Decimal/金额不经 float；
- datetime 使用明确格式和时区；
- 数组、字符串、对象深度受限。

### String Source Profile

query/path/header 天然为字符串，允许声明式转换，但转换集合固定且可审计。

### Trusted Internal Profile

允许内部受信构造，但方法名和权限必须显式，例如：

```text
from_trusted_data
construct_unchecked
```

不得接受请求原始数据，也不得作为业务推荐写法。

## PATCH

采用三态：

```text
MISSING
NULL
VALUE
```

- MISSING：保持原值；
- NULL：清空，前提是字段允许；
- VALUE：更新。

使用 fields-set 或 Missing sentinel 保留调用者实际提供字段。

PUT 和 PATCH 可以共享 controller 的 update handler，但必须绑定不同 Schema/语义。

## 验证阶段

```text
transport limits
-> parse
-> source binding
-> structural/type validation
-> field constraints
-> pure cross-field validation
-> authorization/business policy
-> database/business invariants
```

数据库唯一性、库存、余额等不得伪装成纯 Schema 验证。

## Error Contract

内部错误对象：

```text
location
pointer
code
message_key
safe_params
source
```

外部响应使用稳定 code 和本地化 message。不得暴露：

- 密码；
- token；
- secret；
- 完整签名；
- 大段原始输入；
- 内部 exception repr。

## Schema Composition

允许：

```text
inherit/composition
pick
omit
partial
shared scalar types
shared field fragments
```

但生成后的每个公开 Schema 必须有独立稳定名称，不能依赖复杂运行时 group 才知道实际约束。

## 被拒绝方案

- ORM Model 直接作为公共 request/response；
- 默认忽略未知字段；
- 原始 payload 直接 mass assignment；
- validator 访问数据库或网络；
- 业务唯一性检查替代数据库约束；
- PATCH 缺失与 null 混淆；
- 动态 group 导致同一路由响应不可预测；
- 业务代码大量直接依赖 Pydantic 私有结构。

## 验收条件

1. Input 与 Persistence 字段独立；
2. extra field 和 overposting 被拒绝；
3. body/query 转换策略不同；
4. trusted construction 无法从公共 API 调用；
5. PATCH 三态正确；
6. Schema validator 无 I/O；
7. DB constraint 错误可转稳定业务错误；
8. OutputSchema 始终过滤内部字段；
9. Schema engine 错误映射不泄漏内部格式；
10. Schema 可导出稳定 JSON Schema。