# ADR：OpenAPI 3.1、代码生成与合同漂移控制

- 状态：Draft
- 阶段：Phase C0 研究
- 范围：LingShu API 合同编译、文档、SDK 与兼容性检查

## 背景

如果后端验证、OpenAPI、前端类型、SDK、Mock 和测试分别手写，会出现：

- 文档字段与运行时不一致；
- 前端把可选字段当必填或反之；
- nullable 与 missing 混淆；
- 安全方案未体现在文档中；
- API 已变更但 SDK 未更新；
- 错误响应没有 Schema；
- AI 工具读取到不完整或危险元数据。

## 决策

采用：

```text
LingShu Route Contract
+ LingShu Schema
+ RoutePolicy
+ Error Contract
       ↓ compile
OpenAPI 3.1 + JSON Schema 2020-12
       ↓ generate
TypeScript SDK / optional Zod / mocks / contract tests
```

OpenAPI 是编译产物和对外协议，不是另一份手写事实源。

## Canonical Version

- JSON Schema：Draft 2020-12；
- OpenAPI：3.1；
- OpenAPI 3.0 仅作为可选兼容导出；
- 降级导出不能反向覆盖 canonical contract。

## Route Contract

每个路由至少提供：

```text
operation_id
summary
description
tags
path/query/header/cookie/body schemas
success response schema
known error response schemas
security policy
idempotency metadata
rate/concurrency metadata
deprecation/version
```

候选：

```python
@route.post(
    "/users",
    operation_id="users.create",
    input=CreateUserInput,
    output=UserDetailOutput,
    errors=(ValidationError, ConflictError),
    policy=CreateUserPolicy,
)
async def create_user(input: CreateUserInput):
    ...
```

具体装饰器 API 后续冻结。

## Operation ID

要求：

- 全局唯一；
- 稳定；
- 不自动依赖 Python 函数路径；
- 作为 SDK 方法、审计动作和兼容性追踪标识；
- 重命名视为可能 breaking change。

推荐命名：

```text
module.resource.action
users.user.create
orders.order.cancel
```

## Schema Registry

Schema 编译时进入注册中心：

```text
stable schema name
version
input/output mode
JSON Schema
source location
dependencies
```

必须检测：

- 名称冲突；
- 同名不同结构；
- 循环引用；
- 无法生成 Schema 的字段；
- 不稳定动态名称；
- 私有/内部 Schema 被错误公开。

## OpenAPI 编译检查

构建失败条件：

- path 参数未声明或多余；
- operationId 重复；
- 正常响应无 OutputSchema；
- RoutePolicy 与 security schemes 不一致；
- idempotency-required 路由未声明 header/operation response；
- 422/401/403/409/429/503 等启用错误无合同；
- Schema example 不能通过验证；
- response status 和 body schema 冲突；
- multipart/file 定义错误；
- duplicate component schema；
- route 可见但被标记为内部-only。

## Output Contract

正式 API 响应始终经过声明的 OutputSchema。

开发与测试：

- 完整验证；
- 错误立即失败；
- contract test 校验示例和实际响应。

生产：

- 字段过滤和安全序列化始终开启；
- 完整二次验证可按路由配置或采样；
- 任何输出合同异常都记录高等级日志与 trace；
- 返回安全 500，不把内部对象直接透传。

## Error Components

统一生成：

```text
ErrorEnvelope
ValidationErrorResponse
AuthenticationErrorResponse
AuthorizationErrorResponse
ConflictErrorResponse
RateLimitErrorResponse
DependencyUnavailableResponse
```

每个业务错误码可以有文档索引，但不能把全部业务错误展开成巨大 oneOf 破坏工具兼容性。

## SDK Generation

首个目标：TypeScript。

生成内容：

```text
request/response types
API client
error types
operation metadata
optional Zod validators
SSE/WebSocket event types（后续）
```

生成 SDK 必须：

- 支持 AbortSignal；
- 传递 request_id/idempotency key；
- 不自动重试非幂等写；
- 保留 HTTP status 和 LingShu error code；
- 区分 missing/nullable；
- 支持 operation_id 和 unknown outcome。

## Generated vs Handwritten

```text
generated/
manual wrappers/
```

- 生成目录禁止手工修改；
- 业务便捷封装写在独立目录；
- 重生成不能覆盖手写代码；
- 生成文件头包含 generator/version/contract hash；
- CI 比较生成结果。

## Contract Diff

候选命令：

```text
lingshu contract diff old.json new.json
```

Breaking change 示例：

- 删除 path/operation；
- 改 operationId；
- 删除或改名响应字段；
- 必填字段增加；
- 类型收窄；
- enum 删除值；
- status code 或 security requirement 改变；
- nullable 变 non-nullable；
- 请求字段由可选变必填。

可能兼容：

- 新增可选请求字段；
- 新增响应字段（仍需考虑严格客户端）；
- 新增 enum 值对部分客户端可能不兼容，应按策略标记；
- 新增可选 endpoint。

Diff 工具必须支持项目自定义兼容政策。

## CI

至少执行：

```text
schema compile
openapi validate
examples validate
SDK generate
SDK typecheck/build
contract drift check
breaking change check
runtime contract tests
```

生成物未更新或与源码不一致时失败。

## 文档分层

### 机器合同

- OpenAPI；
- JSON Schema；
- SDK；
- 错误码索引。

### 人工说明

- 概念；
- 流程；
- 安全注意事项；
- 示例；
- 迁移指南。

机器生成文档不能覆盖人工说明；人工说明也不能重复手写字段清单。

## AI Tool Metadata

OpenAPI 扩展元数据仅作为候选：

```text
x-lingshu-tool-exposed
x-lingshu-risk-level
x-lingshu-side-effect
x-lingshu-confirmation-required
x-lingshu-required-permissions
x-lingshu-idempotency
```

规则：

- 默认不暴露为 AI 工具；
- 高风险操作必须显式启用；
- 工具元数据不绕过 RoutePolicy；
- 自动生成工具前需单独安全审计；
- 参数说明不得暴露内部字段和 secrets。

## 被拒绝方案

- 手写 OpenAPI 与运行时 Schema；
- 以 OpenAPI 3.0 永久限制 canonical Schema；
- operationId 自动取函数名且可随重构变化；
- 生成代码与手写代码混在同一文件；
- CI 不检查生成物漂移；
- SDK 默认重试所有请求；
- 输出不声明 Schema；
- 所有 API 自动暴露给 AI/MCP。

## 验收条件

1. 同一 Schema 可生成 JSON Schema 2020-12；
2. OpenAPI 3.1 文档通过验证；
3. operationId 稳定且唯一；
4. RoutePolicy 与 security 文档一致；
5. 错误响应组件完整；
6. TypeScript SDK 可编译；
7. missing/nullable/union/enum 正确；
8. 生成物可复现；
9. 手写封装不被覆盖；
10. CI 检测 drift；
11. contract diff 检测 breaking change；
12. AI metadata 默认关闭且不绕过权限。