# LingShu Framework 总体架构设计总纲（Blueprint v0.7）

（说明：在 v0.6 基础上完成“冻结缺口补丁”，补齐运行一致性、ID体系、时间系统、异常语义、配置版本、序列化规范、异步上下文规则、Telemetry标准字段、资源预算模型）

---

## 31. 统一时间系统（新增冻结）

```text
system_time        → 日志展示
monotonic_time     → 所有超时 / Deadline / 调度
```

规则：

- 禁止 datetime.now() 参与任何业务逻辑决策；
- 所有 timeout 必须基于 monotonic clock；
- Deadline = monotonic_start + budget；
- 日志时间仅用于展示，不参与逻辑。

---

## 32. 全局 ID 体系（新增冻结）

```text
request_id   → ULID（时间有序全局唯一）
connection_id→ worker-local monotonic sequence
trace_id     → 可选外部兼容链路ID
operation_id → async task / internal operation id
```

规则：

- request_id 必须在 request-line 校验后立即生成；
- connection_id 不跨 worker；
- 不允许自定义字符串ID替代标准ID；
- 所有日志 / record / telemetry 必须包含 request_id。

---

## 33. 异常语义模型（新增冻结）

```text
retryable         → 是否允许重试
client_visible    → 是否返回给客户端
system_fatal      → 是否影响 readiness
record_sensitive  → 是否脱敏写入
```

规则：

- 所有异常必须分类；
- Exception 默认不可 retryable（除显式标记）；
- system_fatal = true 必须触发 readiness 降级；
- 禁止 blanket except Exception: pass。

---

## 34. 配置版本化机制（新增冻结）

```text
config.schema.version 必须存在
```

规则：

- 不允许 silent fallback；
- version mismatch 必须失败启动；
- 必须提供 migration function；
- runtime reload 必须 validate → prepare → swap → rollback。

---

## 35. 序列化与数据协议（新增冻结）

统一规范：

```text
datetime → RFC3339
bytes    → base64
None     → null
float    → 禁止 NaN / Inf
stream   → JSONL
```

规则：

- 所有 HTTP / Record / Telemetry 使用统一序列化协议；
- 禁止隐式 pickle / repr 序列化；
- schema mismatch 必须失败。

---

## 36. Async / Context 规则（新增冻结）

```text
request_context → 显式传播
task_context    → 默认不继承
background task → 必须 detach
```

规则：

- 不允许 ContextVar 自动泄漏；
- 不允许 Singleton 持有 request context；
- 子任务必须显式绑定 execution context；
- request 生命周期结束必须清理 context。

---

## 37. Telemetry 标准字段（新增冻结）

```text
request_id
trace_id
span_id
duration_ms
status_code
error_code
component
```

规则：

- 所有事件必须包含 request_id；
- duration 必须基于 monotonic_time；
- 不允许组件私有字段污染主事件流；
- Telemetry 是唯一观测入口。

---

## 38. Worker 资源预算模型（新增冻结）

```text
max_memory_per_worker
max_concurrent_requests
max_connection_count
max_record_disk_usage
max_event_queue_size
```

规则：

- 超限必须 backpressure 或 reject；
- 不允许无限队列；
- 不允许 silent drop；
- 所有 reject 必须进入 record + telemetry。

---

## 39. 冻结一致性声明（补充）

v0.7 在 v0.6 基础上补齐以下关键缺口：

- 时间一致性模型
- ID体系标准化
- 异常语义化
- 配置版本控制
- 序列化协议统一
- async context isolation
- telemetry字段规范
- worker资源上限模型

---

## 40. 冻结确认状态

```text
Blueprint Status: READY FOR P0 FREEZE
```

满足条件：

- 可实现性完整
- 无运行时歧义
- 无隐式行为
- 无未定义时间模型
- 无未定义ID规则
- 无未定义异常语义
- 无未定义序列化规则
- 无未定义上下文传播规则

---

## 41. 下一阶段权限

只有在以下条件满足后才允许 P1：

- 多多确认 v0.7
- 不再修改 core runtime semantics
- 不再引入新冻结规则
- 仅允许实现，不允许再设计
