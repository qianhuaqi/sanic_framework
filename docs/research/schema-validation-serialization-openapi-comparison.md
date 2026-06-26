# Schema、Validation、Serialization 与 OpenAPI 横向对比

> 状态：Phase C0 研究稿，不是最终公共 API 冻结稿。
>
> 样本：Pydantic、Ecto Changeset、Jakarta Bean Validation/Hibernate Validator、ASP.NET Core Model Binding、Symfony Validator/Serializer、Laravel Form Request、Zod、FastAPI Response Model、JSON Schema 2020-12、OpenAPI 3.1。

## 研究目标

LingShu API 需要建立一套合同层，使同一份可信元数据能够驱动：

```text
请求解析
输入验证
输出序列化
错误结构
JSON Schema
OpenAPI
TypeScript SDK
契约测试
Mock
AI 工具元数据
```

但“同一份合同”不等于“数据库模型、领域模型、请求模型、响应模型共用一个类”。

本批重点回答：

1. 输入、输出、持久化和领域对象如何分层；
2. 严格验证与自动类型转换如何取舍；
3. PATCH 如何区分缺失、null 和具体值；
4. 未知字段如何处理；
5. 输出如何防止敏感字段泄漏；
6. 校验错误如何稳定、可本地化、可生成前端提示；
7. OpenAPI 是否应采用 3.1 与 JSON Schema 2020-12；
8. 文档和 SDK 如何从合同生成且避免漂移。

---

# 一、Pydantic

## 值得吸收

Pydantic 模型可以基于 Python 类型标注完成解析、验证、序列化和 JSON Schema 生成。它保证验证后的输出符合声明类型，但默认可能执行类型转换，例如字符串数字转换为整数。

Pydantic 同时提供：

- strict mode；
- `extra=forbid/ignore/allow`；
- `model_fields_set` 区分哪些字段由调用者明确提供；
- `model_dump` / `model_dump_json`；
- JSON Schema Draft 2020-12；
- OpenAPI 3.1 兼容 Schema；
- 自定义 validator 和 serializer；
- 输入、输出 Schema 生成模式。

## 需要警惕

- 默认忽略未知字段，不适合安全优先的公共 API；
- 自动 coercion 可能把错误输入“修正”为另一种含义；
- Python mode 和 JSON mode 的严格行为可能不同；
- `model_construct()` 可绕过验证；
- duck-typed / `serialize_as_any=True` 可能把子类新增敏感字段序列化出去；
- validator 中执行数据库或网络 I/O 会把纯 Schema 变成不可预测业务流程。

## LingShu 裁决

`adopt/adapt`

- Pydantic 作为 Python 第一版 Schema 引擎候选；
- LingShu 对外提供自己的 Schema facade 和稳定错误结构，不让业务强依赖 Pydantic 内部错误格式；
- 公共请求 Schema 默认 `extra=forbid`；
- JSON body 默认采用安全严格配置，query/path/header 采用受控字符串转换配置；
- 安全敏感字段、金额、版本号、布尔开关、权限字段采用严格类型；
- `model_construct()` 等跳过验证入口只允许框架内部受信路径使用；
- 输出序列化默认按声明 Schema，不启用 duck typing；
- 自定义 validator 必须尽量纯函数、无副作用。

---

# 二、Ecto Changeset

## 值得吸收

Ecto 明确区分：

```text
cast()   外部不可信数据：转换、白名单和校验
change() 内部可信数据：应用内部直接修改
```

Changeset 同时承载：

- 参数白名单；
- 类型转换；
- 字段和跨字段校验；
- 变更集合；
- 数据库 constraint 到结构化错误的转换。

其重要经验是：应用层唯一性检查存在竞态，最终仍需数据库唯一约束。

## LingShu 裁决

`adopt`

- 区分 External Input 与 Internal Mutation；
- 不允许 HTTP payload 直接进入 ORM/ODM Model；
- 输入 Schema 的字段白名单即 mass-assignment 白名单；
- 数据库约束错误进入统一 Validation/Conflict 错误；
- Schema 验证不替代数据库 constraint；
- 不把数据库查询型唯一验证放进纯 Schema 核心。

---

# 三、Jakarta Bean Validation / Hibernate Validator

## 值得吸收

Jakarta Validation 提供声明式约束、对象图级联验证、方法参数和返回值验证、容器元素约束以及 validation groups。Groups 允许同一对象在不同操作中应用不同约束集合。

## 风险

- 动态 group 和 group sequence 容易形成隐藏执行逻辑；
- 领域实体上堆积大量操作相关约束，会让 Create、Update、Import、Admin 等场景相互影响；
- annotation 过多会让 Schema 变成难以理解的元编程系统。

## LingShu 裁决

`adapt`

- 吸收声明式约束和级联验证；
- 对外推荐显式 Schema：`CreateUserInput`、`UpdateUserInput`、`AdminUserOutput`；
- validation group 仅作为高级复用机制，不作为主要业务 API；
- 支持方法/handler 输入输出合同检查，但启动时编译，运行时避免大量反射；
- 约束必须有稳定 code，不只提供自然语言 message。

---

# 四、ASP.NET Core Model Binding / Validation

## 值得吸收

ASP.NET Core 将 HTTP 不同来源绑定到参数或模型：route、query、form、body、header 等，并建立 ModelState 保存绑定和校验错误。官方针对 overposting 建议使用专用 ViewModel，而不是只依赖 `[Bind]` 排除字段。

## LingShu 裁决

`adopt`

- 每个输入字段必须知道来源：path/query/header/cookie/body/file；
- 同名字段跨来源冲突必须有固定优先级或明确拒绝；
- 使用专用 InputSchema 防止 overposting；
- 不允许一个参数同时隐式从多个来源猜测；
- 绑定错误与业务校验错误可以统一返回，但内部保留阶段分类；
- path/query/header 的字符串转换规则与 JSON body 分开。

候选：

```python
class ListUsersQuery(QuerySchema):
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)

class CreateUserBody(BodySchema):
    name: str
    email: EmailStr
```

---

# 五、Symfony Validator / Serializer

## 值得吸收

Symfony Validator 支持约束、级联和 validation groups；Serializer 使用 serialization groups 决定不同上下文下哪些字段可以输出，例如 public-view 与 admin-view。

## 风险

- 同一个实体同时承载持久化、验证与多个输出 group，长期容易形成复杂矩阵；
- 运行时随意组合 `*` 或动态字段集合可能造成敏感字段泄漏；
- group 名称过多会使接口实际响应难以从 OpenAPI 预测。

## LingShu 裁决

`adapt`

- 吸收 named output view 思想；
- 优先使用显式 OutputSchema，不把 ORM 实体直接序列化；
- 允许少量可复用 View/Profile，例如 public、internal、admin；
- 每个路由只能选择已声明并进入 OpenAPI 的响应视图；
- 禁止生产接口动态 `serialize all fields`；
- 字段级权限必须基于已声明视图或明确 union，不得静默改变合同。

---

# 六、Laravel Form Request

## 值得吸收

Laravel Form Request 将请求授权和校验组织在专用请求类中；验证成功后通过 `validated()` 获取实际经过校验的数据。JSON 校验失败返回结构化 422 错误，并保留嵌套字段路径。

## LingShu 裁决

`adapt`

- 复杂接口允许专用 Request Contract；
- 授权仍由 LingShu 安全链执行，Schema 可声明所需 action/policy 元数据，但不在 validator 中重复解析身份；
- handler 只接收经过验证的 InputSchema；
- 未验证的原始 payload 不推荐继续传给业务层；
- 结构化错误包含嵌套 path；
- 支持 fail-fast 和 collect-all 两种策略，默认收集合理数量的错误并设置上限。

---

# 七、Zod

## 值得吸收

Zod 提供 `parse` 与 `safeParse`、对象组合、partial/pick/omit、refine/superRefine、异步 refine 和结构化 issues。它非常适合作为前端运行时校验与生成 TypeScript 类型的参考。

## 风险

- 前后端分别手写 Pydantic 和 Zod 会产生合同漂移；
- 异步 refinement 直接查数据库可能重复后端业务逻辑；
- 前端验证只能改善体验，不能替代服务端验证。

## LingShu 裁决

`adapt`

- TypeScript SDK 可从 OpenAPI/JSON Schema 生成 Zod 或等价 validator；
- 前端 Schema 属于生成物，不作为第二事实源；
- Zod issues 与 LingShu ValidationIssue 做字段映射；
- 前端异步唯一性检查仅用于提示，服务端数据库约束仍是最终裁决；
- 生成器必须保留 nullable、optional、union、enum、discriminator 和 format 语义。

---

# 八、FastAPI Response Model

## 值得吸收

FastAPI 使用 response model 对返回数据进行文档、校验、转换和字段过滤。即使 handler 返回的对象包含额外字段，输出仍以声明模型为边界，这对防止密码或内部字段泄漏十分重要。

## LingShu 裁决

`adopt`

- 每个正式 API 必须声明 OutputSchema；
- 响应序列化始终按 OutputSchema 过滤字段；
- ORM/ODM 对象不能直接无约束 JSON 化；
- 子类新增字段不自动出现在父类声明的响应中；
- 输出合同错误在开发/测试中立即失败，生产中记录高等级错误并返回安全 500；
- 是否执行完整输出重新验证可按性能策略配置，但字段投影和安全过滤必须始终执行。

---

# 九、JSON Schema 2020-12 / OpenAPI 3.1

## 值得吸收

OpenAPI 3.1 的 Schema Object 基于并扩展 JSON Schema Draft 2020-12，能够更自然表达：

- `oneOf/anyOf/allOf`；
- nullable 通过类型联合表达；
- const；
- 条件 Schema；
- `$ref/$defs`；
- discriminator 与复杂多态；
- 自定义 annotation 和扩展元数据。

Pydantic 也能生成 JSON Schema 2020-12 和 OpenAPI 3.1 兼容结构。

## LingShu 裁决

`adopt`

- canonical contract 采用 JSON Schema 2020-12；
- canonical API 文档采用 OpenAPI 3.1；
- 可在工具兼容需求下提供 OpenAPI 3.0 降级导出，但不是事实源；
- Schema 必须声明 `$id`/稳定名称策略；
- 生成结果可复现、排序稳定；
- 自定义元数据使用 `x-lingshu-*` 或声明的 vocabulary/annotation；
- 不使用无法被客户端生成器理解的大量私有动态逻辑。

---

# 十、LingShu Schema 分层

## 1. Transport Schema

负责 HTTP 来源和解析：

```text
PathSchema
QuerySchema
HeaderSchema
CookieSchema
BodySchema
FileSchema
```

## 2. Input Schema

负责外部不可信数据：

```text
CreateUserInput
UpdateUserInput
ImportUserInput
```

特性：

- unknown field 默认拒绝；
- 字段来源明确；
- 类型转换策略明确；
- 业务可写字段白名单；
- 长度、数量、深度和格式限制；
- 纯跨字段校验。

## 3. Domain Command / Mutation

由服务端在认证、租户和业务上下文建立后创建：

```text
CreateUserCommand
UpdateOrderCommand
```

可以增加：

- tenant_id；
- principal_id；
- server timestamp；
- operation_id；
- 内部计算字段。

## 4. Persistence Model

```text
TableModel
DocumentModel
```

不直接承担 HTTP 输入和响应合同。

## 5. Output Schema

```text
UserSummaryOutput
UserDetailOutput
AdminUserOutput
```

只声明允许暴露的字段，并驱动 OpenAPI 和 SDK。

---

# 十一、严格与转换策略

## JSON Body

默认：

- unknown fields forbidden；
- 布尔值不接受随意字符串；
- 数字不接受会丢失信息的转换；
- money 使用 Decimal/整数最小单位，不使用 float；
- datetime 要求明确格式与时区策略；
- enum 不接受未声明值；
- ID 不接受浮点或空白变体。

允许按字段显式配置安全转换。

## Query / Path / Header

这些来源天然是字符串，可做受控转换：

```text
"1" -> int
"true" -> bool（只允许固定字面量）
ISO datetime -> datetime
comma list -> 仅在字段声明允许时
```

禁止模糊转换，例如任意非空字符串都视为 true。

## Internal Data

内部服务数据也不默认完全跳过验证。允许显式 trusted construction，但：

- 只能由框架或受信模块调用；
- 方法名必须体现 unsafe/trusted；
- contract test 覆盖；
- 不能接受直接来自请求的数据。

---

# 十二、PATCH 语义

PATCH 必须区分：

```text
字段缺失      -> 不修改
字段为 null   -> 明确清空（字段允许 nullable 时）
字段有值      -> 设置新值
```

不能将所有可选字段简单定义为 `None` 后无法区分缺失与清空。

候选依赖：

```text
model_fields_set
Missing sentinel
UpdateSchema.partial()
```

PUT 与 PATCH 虽可共享 controller handler，但 Schema 与语义必须不同：

- PUT：完整替换或按项目约定的完整更新；
- PATCH：部分更新。

---

# 十三、Validation Pipeline

候选顺序：

```text
body/header/query size guard
-> media type / JSON parse
-> source binding
-> structural/type validation
-> field constraints
-> cross-field pure validation
-> canonical normalized value
-> authorization/resource checks
-> business invariant / DB constraint
```

说明：

- JSON 语法错误属于 parse error；
- 类型、格式、未知字段属于 validation error；
- 权限不是 validation error；
- 唯一性、余额、库存等并发业务约束不是纯 Schema 校验；
- 数据库 constraint 是最终正确性保障。

---

# 十四、统一错误结构

候选：

```json
{
  "code": 100100,
  "msg": "validation failed",
  "data": {
    "errors": [
      {
        "location": ["body", "users", 0, "email"],
        "pointer": "/users/0/email",
        "code": "string.email",
        "message": "email format is invalid",
        "params": {}
      }
    ]
  },
  "request_id": "..."
}
```

规则：

- `code` 是稳定机器码；
- `location` 是结构化路径；
- `message` 可本地化，不作为程序判断依据；
- `params` 只包含安全约束信息，例如 min/max，不返回 secret 或完整输入；
- 错误数量有上限，防止恶意大 payload 产生巨量错误；
- malformed JSON、unsupported media type、validation、business conflict 使用不同错误类别。

候选 HTTP：

```text
400 malformed request / JSON parse
415 unsupported media type
422 structurally valid but schema invalid
409 business/database conflict
```

最终 HTTP 与现有 LingShu code envelope 一起冻结。

---

# 十五、输出序列化安全

必须始终执行：

- OutputSchema 字段白名单；
- secret/private/internal 字段禁止输出；
- alias 和命名策略；
- datetime/timezone；
- Decimal；
- enum；
- bytes/binary；
- 循环引用与最大深度；
- 列表最大输出数量；
- ORM lazy relation 不在序列化时自动触发查询。

禁止：

```python
return model.__dict__
return orm_object
return document_without_projection
serialize_as_any=True
```

Named View 可以存在，但每条路由的响应合同必须明确进入 OpenAPI。

---

# 十六、OpenAPI 编译与检查

应用启动或构建阶段编译：

```text
Route metadata
+ Input/Output Schema
+ Security Policy
+ Error Responses
+ Operation metadata
-> OpenAPI 3.1
```

必须检查：

- operationId 唯一且稳定；
- path 参数与路径一致；
- request body media type；
- 每个成功和主要错误响应有 Schema；
- security scheme 与 RoutePolicy 一致；
- nullable/optional 不混淆；
- enum/discriminator 正确；
- Schema 名称冲突；
- 循环 `$ref`；
- 示例能通过 Schema；
- deprecated/version metadata；
- 输出中不存在未声明字段。

---

# 十七、代码生成与漂移检查

候选命令：

```text
lingshu schema export
lingshu openapi export
lingshu client generate typescript
lingshu contract check
lingshu contract diff old.json new.json
```

生成物：

```text
OpenAPI JSON/YAML
JSON Schema bundle
TypeScript types
API client
optional Zod validators
Mock fixtures
contract tests
```

原则：

- 生成结果可复现；
- 生成目录与手写代码隔离；
- CI 发现生成物漂移；
- breaking change diff 阻断发布；
- SDK 版本与 API contract version 对齐；
- 不在运行时动态下载未知 Schema 执行。

---

# 十八、AI 工具元数据边界

Schema 可为后续 AI/MCP 提供元数据，但不是所有 API 自动成为工具。

候选扩展：

```text
x-lingshu-tool-exposed
x-lingshu-risk-level
x-lingshu-side-effect
x-lingshu-confirmation-required
x-lingshu-idempotency
x-lingshu-permissions
```

高风险写操作必须显式暴露、权限检查、确认和审计。

---

# 十九、明确拒绝

- ORM Model 同时作为请求和响应 Schema；
- 公共输入默认忽略未知字段；
- `Model(**request.json)`；
- validator 中随意访问数据库或外部网络；
- 应用层唯一性验证代替数据库 constraint；
- PATCH 用 `None` 混淆缺失和清空；
- 直接返回 ORM/ODM 对象；
- duck-typed 输出导致子类敏感字段泄漏；
- 前端 Zod 成为第二事实源；
- OpenAPI 文档与运行时 Schema 分别手写；
- 使用动态 serialization group 让实际响应无法预测；
- 为兼容旧工具把 OpenAPI 3.0 作为长期唯一事实源。

---

# 二十、必须验证的测试

1. unknown field 默认拒绝；
2. JSON body strict 与 query string conversion 分离；
3. bool/int/Decimal/datetime 边界；
4. 额外字段与 overposting；
5. external cast 与 internal mutation 分离；
6. PATCH missing/null/value；
7. 嵌套 path 错误；
8. 错误数量和深度上限；
9. 敏感输入不进入错误和日志；
10. 数据库唯一并发冲突映射；
11. OutputSchema 过滤 secret；
12. 子类新增字段不会泄漏；
13. lazy relation 序列化不触发查询；
14. serialization view 与 OpenAPI 一致；
15. JSON Schema 2020-12 校验；
16. OpenAPI 3.1 operationId/security/response 检查；
17. TypeScript SDK 生成和编译；
18. Zod validator 与后端 Schema 合同样例一致；
19. contract diff 检测 breaking change；
20. 生成物 CI drift check；
21. 大 payload、深嵌套、超大数组性能和拒绝测试；
22. 输出验证失败返回安全错误且记录 trace。

## 官方资料

- Pydantic Models: https://docs.pydantic.dev/latest/concepts/models/
- Pydantic Strict Mode: https://docs.pydantic.dev/latest/concepts/strict_mode/
- Pydantic Serialization: https://docs.pydantic.dev/latest/concepts/serialization/
- Pydantic JSON Schema: https://docs.pydantic.dev/latest/concepts/json_schema/
- Ecto Changeset: https://hexdocs.pm/ecto/Ecto.Changeset.html
- Jakarta Validation 3.1: https://jakarta.ee/specifications/bean-validation/3.1/jakarta-validation-spec-3.1
- ASP.NET Core Model Binding: https://learn.microsoft.com/en-us/aspnet/core/mvc/models/model-binding
- ASP.NET Core Validation: https://learn.microsoft.com/en-us/aspnet/core/mvc/models/validation
- Symfony Validation: https://symfony.com/doc/current/validation.html
- Symfony Serializer: https://symfony.com/doc/current/serializer.html
- Laravel Validation: https://laravel.com/docs/12.x/validation
- Zod API: https://zod.dev/api
- FastAPI Response Model: https://fastapi.tiangolo.com/tutorial/response-model/
- JSON Schema Draft 2020-12: https://json-schema.org/draft/2020-12/json-schema-core
- OpenAPI 3.1.1: https://spec.openapis.org/oas/v3.1.1.html
