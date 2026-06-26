# 请求生命周期、结构化并发与韧性机制对比

> 状态：Phase C0 研究稿，不是最终运行时实现。
>
> 样本：Python asyncio、AnyIO、Go context/errgroup、Tokio JoinSet、Tower、Resilience4j、.NET Channels、Sanic 生命周期与 Worker Manager、Kubernetes Pod termination。

## 研究目标

LingShu API 必须解决：

1. 请求取消、客户端断连和超时能否传递到下游；
2. 请求内部并发任务是否有明确父子关系；
3. 一个子任务失败时其他任务如何处理；
4. 连接池、外部 API、CPU 任务如何隔舱；
5. 队列满时是等待、拒绝、丢弃还是降级；
6. 熔断、限流、重试和并发限制如何分开；
7. 服务停止时如何停止接流量、等待在途请求、清理资源；
8. 后台任务如何拥有明确 owner，避免脱离生命周期继续运行。

---

# 一、Python asyncio TaskGroup

## 值得吸收

`asyncio.TaskGroup` 提供结构化并发：所有子任务由一个明确作用域管理，退出上下文时等待子任务结束；任一子任务发生非取消异常时，会取消其余子任务，最终以 ExceptionGroup 汇总错误。

Python 官方还明确要求：

- 取消通过 `CancelledError` 在下一个可取消点抛出；
- 清理使用 `try/finally`；
- 捕获取消后通常必须重新抛出；
- 吞掉取消会破坏 TaskGroup 和 timeout 等结构化并发组件；
- 裸 `create_task()` 必须保留强引用，否则任务可能在执行中失去引用。

## LingShu 裁决

`adopt/adapt`

- 请求内部并发默认使用受控 TaskGroup；
- 相关子任务必须在请求结束前完成或取消；
- 一个关键子任务失败时默认取消同组其他任务；
- 支持显式 `collect_errors` 模式，但不能用 `gather(return_exceptions=True)` 隐藏错误；
- 普通业务禁止无 owner 的裸 `create_task()`；
- 背景任务必须注册到 ApplicationTaskRegistry 或 Operation/Worker 系统；
- 捕获取消异常后必须重新抛出，框架测试检测吞取消行为。

---

# 二、AnyIO TaskGroup / CancelScope

## 值得吸收

AnyIO 在 TaskGroup 中包含 cancel scope，可以整体取消整个任务树。`TaskGroup.start()` 提供 readiness handshake：父任务会等待子任务明确调用 `started()`，避免“任务已创建但服务尚未就绪”的竞态。

AnyIO timeout 基于嵌套 deadline/cancel scope；实际有效 deadline 取父子作用域中最早者。它也明确提出，资源关闭等 finalization 场景可以短暂 shield，但 shield 必须有超时，不能无限屏蔽取消。

## LingShu 裁决

`adopt/adapt`

- LingShu 暴露 `TaskGroup` 和 `CancellationScope` 抽象，底层可以先基于 asyncio/AnyIO；
- 长期子服务、连接消费者等启动必须有 ready handshake；
- timeout 使用绝对 deadline 传播，不让每层重新获得完整时长；
- cleanup shield 仅用于 rollback、release、close、ack 等必要收尾；
- shield 必须有独立短超时；
- 取消原因进入日志、Trace 和指标；
- ContextVar 复制边界必须有测试，数据库事务不能因 task context copy 被并发共享。

---

# 三、Go context / errgroup

## 值得吸收

Go `context.Context` 将 deadline、cancellation 和 request-scoped values 显式沿调用链传递；官方建议 Context 作为第一个参数传入函数，不存入长期结构体，也不用于普通可选参数。

`errgroup` 将一组属于同一总体任务的 goroutine 组织起来，结合 Context 在某个子任务失败时取消其他任务，并统一等待结果。

## LingShu 裁决

`adapt`

Python 不需要把 context 当每个函数首参数强制传递，但应吸收其显式语义：

```text
RequestExecutionContext
├── deadline
├── cancellation reason
├── request_id / trace_id
├── principal / tenant
├── operation_id
└── resource budgets
```

- ContextVar 只承载请求级上下文，不承载普通业务参数；
- 需要跨线程/进程时显式序列化允许字段；
- 取消、deadline 必须向数据库、HTTP 客户端、锁和子任务传播；
- 不把 request context 保存在全局单例或长期 Model 对象中。

---

# 四、Tokio JoinSet

## 值得吸收

Tokio `JoinSet` 维护一组异步任务，可以逐个等待结果、整体 abort，并提供 `shutdown()`：先中止全部任务，再等待它们完成退出。`detach_all()` 会让任务脱离集合继续后台运行，这种能力很危险，必须显式使用。

## LingShu 裁决

`adapt`

- TaskRegistry 必须支持 `cancel_all()` 与 `shutdown_and_wait()`；
- 取消任务后仍要 await 其退出，不能只调用 cancel 就释放资源；
- “detach” 默认禁止；
- 允许 detached background task 时必须绑定 application owner、状态、异常处理和 shutdown hook；
- shutdown 返回时 Registry 必须为空或明确记录无法终止的任务。

---

# 五、Tower：ConcurrencyLimit、LoadShed、Timeout

## 值得吸收

Tower 将韧性能力做成可组合 Layer：

- ConcurrencyLimit 限制底层服务同时处理的请求数；
- LoadShed 在内部服务尚未 ready 时拒绝新负载；
- Timeout 在请求超时后中止 response future。

重要经验是：并发限制、过载拒绝和超时是三个不同机制，不应合并为一个“限流”。

## LingShu 裁决

`adopt/adapt`

- `ConcurrencyLimiter`：控制在途任务数量；
- `QueuePolicy`：控制是否等待及等待队列上限；
- `LoadShedPolicy`：资源不可用或队列已满时快速拒绝；
- `TimeoutPolicy`：控制 deadline；
- Layer 顺序在 RoutePolicy 编译期固定；
- 不允许无界等待队列；
- 被拒绝请求返回明确 `Overloaded`/503 或策略指定错误，不伪装成业务失败。

---

# 六、.NET Channels：有界队列和满载策略

## 值得吸收

.NET Channel 明确区分有界和无界队列。有界队列满时可选择：

```text
Wait
DropNewest
DropOldest
DropWrite
```

默认 Wait 会对生产者施加背压；其他丢弃策略适合允许损失的遥测或最新状态数据。

## LingShu 裁决

`adopt`

LingShu 内部队列必须显式配置：

```text
capacity
full_mode
put_timeout
consumer_concurrency
item_ttl
```

可选满载策略：

```text
block
reject
drop_newest
drop_oldest
coalesce_by_key
```

- 普通业务任务默认 `block-with-timeout` 或 `reject`；
- 不可丢失任务禁止 drop；
- 遥测、进度、设备最新状态可按业务选择 coalesce/drop；
- 每次丢弃必须记录指标；
- 禁止无界队列作为生产默认值。

---

# 七、Resilience4j：CircuitBreaker、Bulkhead、TimeLimiter

## 值得吸收

CircuitBreaker 使用 CLOSED/OPEN/HALF_OPEN 状态机，通过计数或时间滑动窗口统计失败率和慢调用率；达到阈值后打开，经过等待期允许有限探测请求。官方特别强调：CircuitBreaker 不限制并发，请使用 Bulkhead。

Bulkhead 提供信号量并发隔离和固定线程池+有界队列两种模型。TimeLimiter 独立管理超时，并决定是否取消运行中的 Future。

## LingShu 裁决

`adopt/adapt`

四类机制严格分开：

```text
Retry             重新尝试安全操作
CircuitBreaker    依赖持续异常时快速失败
Bulkhead          限制并发、隔离资源
TimeLimiter       限制等待时间
```

候选依赖策略：

```python
ExternalServicePolicy(
    timeout=2.0,
    concurrency=20,
    queue=10,
    circuit_breaker="provider-default",
    retry="safe-read",
)
```

要求：

- CircuitBreaker 统计只包含配置的系统异常和慢调用；
- 业务校验错误不能计入依赖故障；
- 半开探测请求数量受限；
- 熔断器按依赖/端点/租户适当分区，避免一个租户污染全局；
- 重试必须位于总 deadline 内；
- Retry 与 CircuitBreaker 的装饰顺序固定并有测试；
- 所有状态转换进入 Metrics 和审计。

---

# 八、Sanic 生命周期与 Worker Manager

## 值得吸收

Sanic listener 在启动阶段按声明顺序执行，在 teardown 阶段反向执行。这与资源依赖栈一致：先创建的基础资源最后关闭。

Sanic Worker Manager 支持 worker ack、零停机重启、受管自定义进程、进程状态跟踪和可重启进程。长期自定义进程必须处理 SIGINT/SIGTERM。

## LingShu 裁决

`adopt/adapt`

LingShu Extension 生命周期：

```text
configure
setup
start
ready
drain
stop
close
```

- 依赖按拓扑顺序启动、逆序关闭；
- readiness 只有在数据库、Redis、路由策略和关键扩展全部 ready 后才为真；
- drain 后停止接新业务请求，但保留健康检查和收尾接口；
- worker ack 之前不得宣告实例 ready；
- 框架自带后台任务必须由受管 Registry/Process 管理；
- 长任务不能塞进 API event loop；
- 零停机重启必须先新 worker ready，再关闭旧 worker。

---

# 九、Kubernetes Pod termination

## 值得吸收

Kubernetes 终止 Pod 时先进入 terminating，ready 状态变为 false，停止接收常规流量，然后发送 TERM 并给予 grace period；超时后发送 KILL。`preStop` 也消耗同一 grace period。

## LingShu 裁决

`adopt`

LingShu 优雅关闭顺序候选：

```text
mark not ready
-> stop accepting new business requests
-> drain keep-alive / in-flight requests
-> cancel noncritical background tasks
-> wait critical operations within budget
-> flush audit/metrics
-> close queues/consumers
-> close Redis/Mongo/SQL pools in reverse dependency order
-> exit before external grace period
```

- 应用内部 shutdown budget 必须小于 Kubernetes/systemd/Docker 外部 grace period；
- shutdown 不能无限等待；
- 超时后记录未完成任务和 operation_id；
- 已提交业务但响应未发送的请求按 operation 状态恢复，不能在重启后重复执行。

---

# 十、LingShu 初步公共合同

## RequestExecutionContext

```text
request_id
trace_id
operation_id
deadline
cancel_reason
principal
tenant
route_policy
resource_budget
```

## TaskGroup

```python
async with lingshu.concurrency.task_group(
    failure_mode="cancel_siblings",
) as group:
    group.start_soon(...)
```

## CapacityLimiter

```python
async with limiter.acquire(
    key="provider:openai",
    weight=1,
    wait_timeout=0.2,
):
    ...
```

## QueuePolicy

```text
capacity
full_mode
wait_timeout
item_ttl
partition_key
```

## DependencyPolicy

```text
timeout_budget
retry_policy
circuit_breaker
bulkhead
fallback
```

## ShutdownCoordinator

```text
ready -> draining -> stopping -> stopped
```

---

# 十一、核心与扩展边界

## 核心

- deadline/cancellation 传播；
- TaskGroup/TaskRegistry 合同；
- CapacityLimiter；
- bounded queue/reference implementation；
- load shedding；
- lifecycle/drain/shutdown coordinator；
- metrics hooks；
- in-memory circuit breaker reference or protocol。

## 扩展

- Redis distributed limiter；
- external gateway limiter；
- Celery/Temporal/Ray；
- Kubernetes operator；
- distributed circuit state；
- process supervisor；
- durable task queue。

---

# 十二、明确拒绝

- 裸 `create_task()` 后不保存引用；
- 请求结束后子任务继续产生副作用；
- 吞掉 CancelledError；
- 每层 timeout 都重新计满时间；
- 无界队列；
- CircuitBreaker 代替并发限制；
- Retry 代替幂等；
- timeout 之后任务仍无监管运行；
- shutdown 只关闭 socket，不等待资源清理；
- 在 API event loop 直接执行 CPU 密集任务；
- detached task 没有 owner、状态和停止协议。

---

# 十三、必须验证的测试

1. TaskGroup 子任务失败会取消同组任务；
2. 多异常以结构化方式汇总；
3. 取消异常不被吞掉；
4. 父 deadline 早于子 timeout 时按父 deadline 结束；
5. cleanup shield 有独立上限；
6. 请求取消传播到 HTTP、DB、锁和子任务；
7. 不同并发 task 的 ContextVar/事务不串线；
8. bounded queue 的 block/reject/drop/coalesce；
9. queue 满时不会无限占内存；
10. ConcurrencyLimiter 与 RateLimiter 独立；
11. CircuitBreaker CLOSED/OPEN/HALF_OPEN 状态转换；
12. 业务错误不计入依赖失败率；
13. Retry 总耗时不超过 deadline；
14. drain 后拒绝新业务请求；
15. 在途请求在预算内完成；
16. shutdown 超时后记录未完成任务；
17. 扩展按拓扑启动、逆序关闭；
18. worker ready handshake；
19. 零停机重启先 ready 新 worker；
20. CPU 任务被转移到受控进程池。

## 官方资料

- Python asyncio Tasks: https://docs.python.org/3/library/asyncio-task.html
- AnyIO Tasks: https://anyio.readthedocs.io/en/stable/tasks.html
- AnyIO Cancellation: https://anyio.readthedocs.io/en/stable/cancellation.html
- Go context: https://pkg.go.dev/context
- Go errgroup: https://pkg.go.dev/golang.org/x/sync/errgroup
- Tokio JoinSet: https://docs.rs/tokio/latest/tokio/task/struct.JoinSet.html
- Tower Concurrency: https://docs.rs/tower/latest/tower/limit/concurrency/
- Tower Load Shed: https://docs.rs/tower/latest/tower/load_shed/
- Tower Timeout: https://docs.rs/tower/latest/tower/timeout/
- Resilience4j CircuitBreaker: https://resilience4j.readme.io/docs/circuitbreaker
- Resilience4j Bulkhead: https://resilience4j.readme.io/docs/bulkhead
- Resilience4j TimeLimiter: https://resilience4j.readme.io/docs/timeout
- .NET Channels: https://learn.microsoft.com/en-us/dotnet/core/extensions/channels
- Sanic Listeners: https://sanic.dev/en/guide/basics/listeners.html
- Sanic Worker Manager: https://sanic.dev/en/guide/running/manager.html
- Kubernetes Pod Lifecycle: https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/
