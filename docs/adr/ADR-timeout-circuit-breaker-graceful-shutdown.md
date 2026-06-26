# ADR：超时预算、熔断、隔舱与优雅关闭

- 状态：Draft
- 阶段：Phase C0 研究
- 范围：LingShu API 外部依赖、资源隔离和进程关闭

## 背景

常见错误包括：

- 每层都设置 5 秒 timeout，实际总耗时远超请求预算；
- timeout 只停止等待，底层任务继续运行；
- Retry、CircuitBreaker、Bulkhead 混成一个策略；
- 一个慢依赖耗尽所有连接和协程；
- 熔断器打开后仍有大量排队请求；
- shutdown 时仍接新请求；
- 容器 grace period 到期后任务被强杀，状态无法恢复。

## 决策

LingShu 将以下机制分开建模并组合：

```text
Deadline / TimeLimiter
Retry
CircuitBreaker
Bulkhead / ConcurrencyLimiter
QueuePolicy
Fallback
ShutdownCoordinator
```

任何组合都必须服从请求或 operation 的总 deadline。

## Deadline Budget

入口设置绝对 deadline：

```text
request_deadline = monotonic_now + route_timeout
```

调用下游时计算剩余预算：

```text
remaining = request_deadline - monotonic_now
```

子操作预算不得超过 remaining，并可进一步分配：

```text
pool acquire
connection establish
write
first byte
read body
cleanup
```

候选：

```python
await client.call(
    ..., 
    timeout=TimeoutBudget(
        total=request.remaining,
        acquire=0.2,
        connect=0.5,
        read=1.0,
    ),
)
```

## Timeout 语义

必须区分：

```text
wait timeout       等待资源超时
operation timeout  操作执行超时
deadline exceeded  总预算耗尽
client disconnect  调用方取消
shutdown cancel    服务关闭取消
```

不同原因进入不同错误码、指标和 operation finalization。

Timeout 后：

- 向可取消下游发送取消；
- 等待短暂 cleanup；
- 不保证外部系统没有完成副作用；
- 非幂等调用结果不确定时进入 `unknown`；
- 不自动盲目 Retry。

## Retry

重试仅适用于已分类安全的操作：

```text
safe read
idempotent write with stable operation key
connection establishment before request sent
explicitly classified transient failure
```

禁止自动重试：

```text
unknown outcome
non-idempotent write
business validation error
permission/authentication failure
capacity rejection without policy
```

Retry 约束：

- max attempts；
- total retry budget；
- exponential backoff；
- jitter；
- respect Retry-After；
- 每次尝试共享总 deadline；
- retry reason 进入 metrics；
- 防止多层重试相乘。

默认只允许一个层负责重试。

## CircuitBreaker

状态：

```text
CLOSED
OPEN
HALF_OPEN
```

统计：

- failure rate；
- slow call rate；
- minimum calls；
- count/time sliding window；
- open wait duration；
- half-open probe limit。

错误分类：

```text
record failure:
  timeout
  connection error
  configured 5xx
  malformed dependency response

ignore:
  business 4xx
  authentication/authorization from local policy
  client cancellation
  local capacity rejection
```

CircuitBreaker 不限制并发，必须和 Bulkhead 组合。

分区策略：

```text
provider
endpoint
region
credential/account
optional tenant partition
```

避免过细造成状态碎片，也避免某个租户故障污染全部服务。

## Bulkhead

候选类型：

### Async Semaphore Bulkhead

用于异步外部调用：

```text
max_concurrency
max_wait
queue_limit
```

### Thread/Process Pool Bulkhead

用于阻塞库或 CPU 工作：

```text
pool_size
queue_capacity
recycle policy
```

每类关键依赖独立隔舱：

```text
mysql
redis
mongo
email provider
AI provider
file conversion
```

禁止所有依赖共享一个无边界全局池。

## Queue 与 Load Shed

当 bulkhead 饱和：

```text
queue within bounded capacity
or reject immediately
```

不可无限等待。

候选错误：

```text
DependencyOverloaded
ApplicationOverloaded
AcquireTimeout
CircuitOpen
```

接口层按策略返回 503/429，并带 Retry-After。

## Fallback

Fallback 只能返回语义正确的降级结果：

- 读缓存；
- 返回 stale 但标注 stale；
- 跳过非关键遥测；
- 延迟非关键通知。

禁止：

- 写请求失败后返回伪成功；
- 权限服务不可用时默认放行；
- 核心数据源不可用时返回空列表掩盖错误；
- 熔断时默默吞掉业务操作。

## Readiness 与 Liveness

```text
liveness 进程是否仍可运行
readiness 是否应该接收业务流量
```

Readiness 变 false 的场景：

- 正在 drain；
- 路由策略未编译；
- 必需扩展未 ready；
- 核心数据源不可用且无安全降级；
- event loop/资源严重过载。

非关键依赖故障不一定让整个应用不 ready，由依赖等级决定。

## ShutdownCoordinator

状态：

```text
starting
ready
draining
stopping
stopped
```

关闭顺序：

1. 标记 readiness=false；
2. 停止接收新业务请求；
3. 保留健康检查与必要运维端点；
4. 等待在途请求至 drain deadline；
5. 取消非关键背景任务；
6. 停止消费者获取新任务；
7. 完成/归还正在处理任务或记录 checkpoint；
8. flush 审计、日志和指标；
9. 按资源依赖逆序关闭；
10. 在外部 grace period 前退出。

## 资源关闭逆序

示例启动：

```text
config
-> telemetry
-> database pools
-> cache
-> services
-> routes
-> consumers/background tasks
```

关闭：

```text
consumers/background tasks
-> routes/drain
-> services
-> cache
-> database pools
-> telemetry
```

具体顺序由依赖图计算，而不是仅靠文件导入顺序。

## Sanic 集成

- 利用 listener startup 正序、teardown 逆序；
- Worker ready 只有资源和策略完成后 ack；
- 自定义进程必须响应 SIGINT/SIGTERM；
- 零停机重启先启动并确认新 worker ready，再 teardown 旧 worker；
- `app.shared_ctx` 不能当跨机器或通用对象共享方案。

## 外部编排预算

应用配置：

```text
shutdown_total = 25s
drain_requests = 15s
cleanup_resources = 8s
final_buffer = 2s
```

外部 Kubernetes/systemd/Docker grace period 必须更长，例如 30 秒。

应用不得使用完整外部 grace period，必须预留强杀缓冲。

## 未完成操作

到达 shutdown deadline 后：

- 记录 task_id/operation_id；
- 尽力保存 checkpoint；
- 数据库事务 rollback；
- 已提交但响应未知的操作标记 unknown；
- 不把未完成操作静默标记 failed；
- 退出后由幂等/operation reconciliation 恢复。

## 被拒绝方案

- 每层重新设置完整 timeout；
- 无限 Retry；
- Retry 套 Retry；
- CircuitBreaker 代替 Bulkhead；
- 熔断器统计业务错误；
- 依赖失败时写操作伪成功；
- 所有依赖共享一个池；
- readiness 永远返回 true；
- SIGTERM 后仍接受新业务；
- shutdown 无限等待；
- 外部强杀后把结果默认视为失败。

## 验收条件

1. 嵌套调用总耗时不超过总 deadline；
2. timeout 原因可区分；
3. 非幂等 unknown 不重试；
4. Retry 有 jitter、总预算和最大次数；
5. 多层 Retry 检测；
6. CircuitBreaker 状态机与慢调用率；
7. 业务错误不打开熔断器；
8. 半开探测并发受限；
9. Bulkhead 饱和后有界等待或拒绝；
10. 一个依赖饱和不拖死其他依赖；
11. readiness 在 drain 开始时变 false；
12. drain 后不接新业务请求；
13. 在途请求按预算完成；
14. 资源按依赖逆序关闭；
15. shutdown 总时长小于外部 grace period；
16. 强制终止前未完成 operation 有恢复记录。