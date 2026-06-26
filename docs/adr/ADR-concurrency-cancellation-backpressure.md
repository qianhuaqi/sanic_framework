# ADR：结构化并发、取消传播与背压

- 状态：Draft
- 阶段：Phase C0 研究
- 范围：LingShu API 请求内并发、内部队列与后台任务

## 背景

异步框架很容易产生以下问题：

- 裸任务脱离请求继续执行；
- 一个子任务失败，其他任务仍继续产生副作用；
- 客户端断开后数据库和外部调用仍在运行；
- 取消异常被捕获后吞掉；
- 无界队列导致内存持续增长；
- 并发只追求吞吐，没有租户公平性和资源隔离；
- 服务关闭时只发 cancel，不等待任务真正退出。

## 决策

LingShu 采用结构化并发作为默认模型：

> 每个任务必须有 owner、作用域、deadline、取消路径和完成等待。

普通业务代码不得创建无监管后台任务。

## 请求任务树

```text
RequestExecution
├── handler task
├── child TaskGroup
│   ├── database task
│   ├── external HTTP task
│   └── independent computation task
└── finalization
```

请求结束条件：

- 所有受管子任务完成；
- 或全部收到取消并完成清理；
- 不允许请求对象销毁后任务继续使用 request/transaction context。

## TaskGroup 默认语义

候选：

```python
async with concurrency.task_group(
    failure_mode="cancel_siblings",
    deadline=request.deadline,
) as group:
    group.start_soon(load_profile)
    group.start_soon(load_permissions)
```

默认：

- 任一非取消异常触发同组其他任务取消；
- 退出时等待全部子任务；
- 多异常结构化汇总；
- 子任务继承 request context 的安全副本；
- 数据库事务资源不得被多个并发子任务共享。

可选 failure mode：

```text
cancel_siblings
collect_all
best_effort
```

`best_effort` 只能用于明确允许部分失败的读取或遥测场景。

## 后台任务

禁止：

```python
asyncio.create_task(do_business_side_effect())
```

候选替代：

```python
app.tasks.spawn(
    name="audit-flush",
    coro=flush_audit(),
    owner="application",
    shutdown="wait",
)
```

或耐久业务任务进入 Operation/Worker 系统。

任务元数据：

```text
name
owner
created_at
deadline
cancel_reason
shutdown_policy
trace_id
operation_id
state
```

## 取消传播

取消来源：

```text
client disconnect
request deadline
parent task failure
application drain
manual operation cancel
dependency timeout
```

传播目标：

```text
child tasks
HTTP calls
DB waits/queries when driver supports
lock acquisition
queue waits
resource pool acquisition
```

规则：

- cleanup 使用 try/finally；
- 捕获取消异常后必须重新抛出；
- cleanup 需要 await 时，允许短暂 shield；
- shield 必须带独立 deadline；
- 取消不代表外部副作用一定未执行，结果不确定时进入 operation `unknown`。

## Deadline

请求入口生成绝对 deadline：

```text
deadline = monotonic_now + route_timeout
```

下游只读取剩余预算：

```text
remaining = deadline - monotonic_now
```

禁止每层重新获得完整 timeout。

所有资源等待不得超过剩余预算。

## CapacityLimiter

候选：

```python
async with limiter.acquire(
    key="tenant:1001:export",
    weight=1,
    wait_timeout=0.2,
):
    ...
```

支持层级：

```text
global
route
tenant
project
external provider
resource pool
```

同一操作可同时占用多个 limiter，但获取顺序必须固定以防死锁。

## Partitioned Concurrency

候选：

```text
same partition_key -> serialized or limited
different key      -> parallel within global limit
```

例如：

```text
order:1001 串行
order:1002 可并行
```

要求：

- key 数量有上限和空闲回收；
- 不为任意攻击者输入永久创建 limiter；
- 支持公平排队；
- 防止热门 key 饿死其他 key。

## Bounded Queue

所有内部队列必须显式：

```text
capacity
full_mode
put_timeout
item_ttl
consumer_concurrency
```

满载模式：

```text
block
reject
drop_newest
drop_oldest
coalesce_by_key
```

默认：

- 业务命令：`block` + 短超时，随后 reject；
- 不可丢任务：禁止 drop；
- 遥测/进度：可配置 coalesce/drop；
- 丢弃必须有指标和日志采样。

## Load Shedding

以下任一条件可进入过载：

- 队列满；
- 连接池等待者超阈值；
- event loop 延迟超阈值；
- 内存压力；
- 依赖 bulkhead 饱和；
- 应用处于 draining。

过载响应：

```text
HTTP 503 / 429（按语义）
Retry-After
stable error code
request_id
```

不能无限排队等待。

## CPU 密集任务

CPU 密集任务不得直接运行在 API event loop。

候选路径：

```text
small bounded work -> controlled process pool
long/durable work  -> future lingshu-ms / task system
```

线程池只适合阻塞 I/O 或释放 GIL 的库，不能把所有 CPU 任务默认扔线程池。

## 关闭流程

TaskRegistry：

```text
stop accepting new tasks
cancel noncritical tasks
wait critical tasks
force cancel on deadline
await cancellation completion
report leftovers
```

只调用 `cancel()` 而不 await 退出，不算关闭完成。

## 被拒绝方案

- 无 owner 裸任务；
- 无界队列；
- 吞掉取消；
- cancel 后不等待退出；
- 请求超时后继续无监管执行；
- 跨并发 task 共享事务 Session；
- 用单个全局 Semaphore 处理所有资源；
- 队列满时无限等待；
- CPU 工作堵塞 event loop。

## 验收条件

1. 请求完成后无遗留子任务；
2. 子任务失败取消同组任务；
3. 取消清理后异常继续传播；
4. deadline 向下递减；
5. shield cleanup 超时有效；
6. 多请求 ContextVar 不串线；
7. 事务不能并发共享；
8. bounded queue 五种策略可测；
9. partition key 串行与跨 key 并行；
10. limiter 公平性和防饿死；
11. 过载快速拒绝；
12. shutdown 返回时 Registry 清空或报告残留；
13. CPU 工作不阻塞 event loop 心跳。