# ADR：扩展注册、依赖容器与生命周期

- 状态：Draft
- 阶段：Phase C0 研究
- 范围：LingShu API 核心、扩展、Provider 与资源生命周期

## 背景

LingShu 需要支持数据库、缓存、安全、Schema、OpenAPI、任务、可观测性等大量可选能力。如果没有统一扩展协议，容易出现：

- 通过 import 副作用注册；
- 启动顺序依赖文件导入顺序；
- 一个扩展失败后留下连接、任务和路由残留；
- 所有服务被塞进全局 `app.ctx`；
- request scope 被 singleton 长期持有；
- 测试无法替换依赖；
- 新扩展只能修改框架核心。

## 决策

采用：

```text
Extension Manifest
+ Provider Registry
+ Scope-aware Container
+ Dependency DAG
+ Managed Lifecycle
```

核心只提供协议、容器、生命周期和合同测试；具体能力通过内置或第三方扩展注册。

## Extension Manifest

候选：

```python
ExtensionManifest(
    name="lingshu.mysql",
    version="1.0.0",
    framework_version=">=0.3,<1.0",
    requires=("lingshu.telemetry",),
    optional_requires=("lingshu.redis",),
    provides=("data.mysql",),
    conflicts=(),
    priority=0,
)
```

字段要求：

- `name` 全局唯一；
- `version` 遵循语义版本；
- `framework_version` 启动时检查；
- `requires` 参与拓扑排序；
- `optional_requires` 缺失时只关闭可选功能；
- `provides` 声明 capability；
- `conflicts` 启动时拒绝；
- `priority` 只在同一明确扩展点排序，不替代依赖图。

## Provider Registry

Provider 注册类型：

```text
class
instance
factory
alias
```

候选：

```python
providers.register(
    token=UserRepository,
    factory=create_user_repository,
    scope="request",
)
```

Provider Token 可为：

- Protocol/class；
- 稳定 symbol/token；
- capability 名称。

禁止用任意字符串到处拼接。公共 Token 集中声明并进入合同检查。

## Scope

内置 scope：

```text
application
worker
request
operation
transient
```

### application

- 每个 app 实例一份；
- 可并发访问；
- 不得捕获 request/operation provider；
- app 关闭时 dispose。

### worker

- 每个 Sanic worker 一份；
- 数据库连接池、HTTP client、telemetry exporter 等通常属于此 scope；
- worker 重启时重新建立。

### request

- 每个 HTTP 请求一份；
- 依赖 request context；
- 响应结束或异常时逆序 dispose；
- 不允许被后台任务长期保存。

### operation

- 耐久操作、消费者或后台任务独立 scope；
- 不依赖原 HTTP request 生命周期；
- 可带 principal/tenant/trace 的受控快照；
- operation 完成后 dispose。

### transient

- 每次解析创建；
- 若可释放，由创建它的上层 scope 跟踪并关闭；
- 禁止在 root container 无界创建 disposable transient。

## Scope Validation

启动与测试默认检查：

```text
application -> request       禁止
application -> operation     禁止
worker      -> request       禁止
request     -> application   允许
operation   -> worker        允许
```

更短生命周期 Provider 可以依赖更长生命周期 Provider；反向捕获禁止。

Provider 本身的并发安全不由 Container 自动保证。

## 依赖解析

规则：

- 构造函数或显式 factory 参数声明依赖；
- 启动时编译依赖图；
- 循环依赖立即报错；
- 可选依赖必须显式 Optional；
- 多实现需要 qualifier/name 或明确 default；
- 不允许运行时因“最后注册者覆盖”产生不确定结果。

## Service Locator 边界

普通业务禁止：

```python
service = container.get("service_name")
```

允许动态解析的位置：

- 框架 Router/Controller factory；
- Extension setup；
- Provider factory；
- 测试 harness；
- 受控 plugin adapter。

业务 Service 使用声明式依赖，便于测试和审计。

## Lifecycle

```text
configure
setup
start
ready
drain
stop
close
```

### configure

- 读取和校验配置；
- 不连接网络；
- 不创建长期任务；
- 生成 configuration fingerprint。

### setup

- 注册 Provider、Route、Schema、Policy、Subscriber；
- 不宣告 ready；
- 注册结果可撤销。

### start

- 创建连接池；
- 启动受管任务；
- 执行 migration check 等运行准备；
- 每一步登记 rollback action。

### ready

- 健康检查通过；
- 关键依赖可用；
- 返回 ExtensionHealth；
- 失败则应用不 ready 或按扩展等级降级。

### drain

- 不接受新工作；
- 停止消费者拉取；
- 保留在途工作。

### stop

- 取消或等待任务；
- 停止活动组件。

### close

- 逆序释放连接、文件和 exporter；
- 幂等，多次调用安全；
- close 失败记录但继续关闭其他资源。

## 初始化失败回滚

示例：

```text
telemetry start OK
mysql start OK
redis start FAIL
```

必须执行：

```text
redis partial cleanup
mysql close
telemetry close
```

只回滚已成功进入的步骤，顺序与建立顺序相反。原始异常保留，清理异常汇总附加。

## Health

ExtensionHealth：

```text
status: starting|ready|degraded|unhealthy|draining|stopped
required: bool
message_code
details_safe
checked_at
```

- required extension unhealthy 可让 app readiness=false；
- optional extension 可 degraded；
- health details 不暴露 credential、内部主机列表或完整 exception。

## 配置更新

第一阶段不承诺所有扩展热更新。

每个配置字段声明：

```text
static
reloadable
restart_required
secret
```

热更新必须支持 validate -> prepare -> swap -> rollback，不允许直接修改正在运行对象的内部字段。

## 第三方扩展

后续可通过 Python package entry points 发现，但：

- 发现不等于自动启用；
- 必须在项目配置显式启用；
- 安装包代码仍具有进程权限，不宣传安全沙箱；
- 扩展签名/来源治理属于发布阶段；
- 每个扩展必须通过 Extension Contract Test Suite。

## Contract Test

第三方扩展必须验证：

1. Manifest 合法；
2. framework version 兼容；
3. setup 不产生未登记副作用；
4. start 失败可回滚；
5. ready/health 语义正确；
6. drain/stop/close 幂等；
7. Provider scope 合法；
8. 无 ContextVar 和任务泄漏；
9. 日志和错误脱敏；
10. 未启用时不影响核心启动。

## 被拒绝方案

- 所有资源放 `app.ctx`；
- import 即注册并产生副作用；
- 一个巨型全局 Container；
- 业务随处 Service Locator；
- 所有 Provider Singleton；
- async constructor；
- dependency cycle 运行时再发现；
- start 失败不逆序清理；
- optional extension 失败时静默改变安全语义；
- 自动启用系统中所有已安装插件。

## 验收条件

1. DAG 拓扑稳定；
2. 循环依赖启动失败并定位路径；
3. Scope captive dependency 被发现；
4. request/operation scope 正确释放；
5. Provider override 在测试中可用、生产需显式；
6. Extension start 任一步失败全部回滚；
7. 生命周期 close 幂等；
8. required/optional health 影响 readiness 正确；
9. 第三方 extension 不改核心代码即可注册；
10. disabled extension 不加载重型可选依赖。