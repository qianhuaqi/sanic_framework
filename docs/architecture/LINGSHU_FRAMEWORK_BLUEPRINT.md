# LingShu Framework 总体架构设计总纲（P0-RC0）

- 设计负责人：小顾
- 产品决策人：多多
- 状态：P0 候选总纲，尚未冻结
- GitHub Issue：#25
- 当前决策 Issue：#31
- 规范仓库：`qianhuaqi/lingshu`
- 治理基线：latest accepted `main`
- 决策状态表：`docs/architecture/P0_DECISION_STATUS.md`
- 历史详细候选稿：`docs/architecture/candidates/LINGSHU_FRAMEWORK_BLUEPRINT_V0.6_CANDIDATE.md`

> 本文件是当前唯一总体架构入口。只有已被多多确认，并在
> `P0_DECISION_STATUS.md` 中标记为 Confirmed 的内容，才可以成为后续
> 实施 Issue 的依据。历史候选稿中的目录、分包、`src/`、扩展包和版本
> 规划均不得直接执行。

---

## 1. 根本定位

LingShu 是一个从零开发、完全独立、自主可控的 Python Web/API Framework。

LingShu 不是 Sanic、FastAPI、Flask、Django、Starlette 或其他上层 Web
Framework 的二次封装、适配层或迁移版本，也不承担历史实现的兼容义务。

LingShu 自己定义并控制：

- Application Kernel；
- HTTP Runtime；
- Native Server；
- Request、Response、Router、Middleware 与 Streaming；
- 生命周期、取消、清理、容量和背压；
- Extension Protocol；
- Request ID 与请求级 Runtime Record；
- CLI、测试支持和后续生态。

这些职责已经确认，但它们最终采用一个 distribution、多个 distribution、
内部模块还是独立安装单元，以及具体目录如何组织，尚未确认。

## 2. 历史实现边界

旧实现完整封存于：

```text
archive/legacy-sanic-20260628
```

封存提交：

```text
b869270e0ec7cbc324d17ef246e39d0873aab14f
```

旧源码、测试、脚手架、依赖、Issue、PR 和 API 只可作为历史参考：

- 不作为新框架代码基线；
- 不产生兼容义务；
- 不允许直接复制到新框架；
- 任何仍有价值的思想都必须重新进入 Issue、架构评审和新实现。

## 3. 已确认的最高原则

### 3.1 自主框架内核

灵枢核心运行能力由灵枢自行设计和实现，不通过安装其他上层 Web 框架获得。

Python 标准库可以作为语言运行基础。是否采用底层解析器、事件循环加速库、
密码学库或其他第三方基础组件，必须逐项评审；核心第三方依赖必须另立 ADR。

### 3.2 机制与政策分离

核心只提供通用机制，不把 JWT、Tenant、RBAC、数据库、ORM、Redis、用户、
订单等具体政策或业务模型写入核心。

哪些能力属于默认安装、官方可选能力或第三方生态，仍需 P0 决策。

### 3.3 依赖单向

当前确认的是概念依赖方向，而不是物理包结构：

```text
Project Application
        ↓
Optional Capabilities / Extensions
        ↓
LingShu HTTP Runtime
        ↓
LingShu Application Kernel
        ↕
LingShu Native Server / Transport
```

Core 不得反向依赖具体业务能力、数据库驱动、认证实现或项目代码。

### 3.4 显式生命周期

禁止通过 import 副作用完成注册、建连、启动任务或修改进程级全局状态。

启动、运行、排空和关闭必须具备：

- 明确状态；
- 有界时间预算；
- 失败回滚；
- 逆序清理；
- 幂等关闭；
- 可观测结果。

### 3.5 默认隔离

App、Worker、Request、Operation 和 Extension 状态必须按作用域隔离。

禁止把当前请求、当前事务、当前用户或其他请求级可变状态保存为进程级普通
全局变量。

### 3.6 默认有界

连接、队列、请求体、Header、并发、任务、重试、缓存、日志、Runtime Record
和磁盘使用都必须有明确上限、背压或拒绝策略。

### 3.7 取消与清理

Deadline 是完整调用链预算，不能在每层重新获得完整超时。

取消必须传播，不得静默吞掉；客户端断开、超时、应用排空和人工取消必须能
区分。任何退出路径都必须执行确定性清理。

### 3.8 安全优先

- 协议歧义直接拒绝，不猜测；
- 敏感信息默认不记录；
- 不自造密码学算法、TLS 算法和证书验证；
- 安全、正确性和可恢复性优先于未经验证的极限性能。

### 3.9 单仓库治理

LingShu 采用一个规范 GitHub 仓库：

```text
qianhuaqi/lingshu
```

框架核心、官方能力、测试、文档、示例、构建工具、协议测试、安全测试和发布
元数据原则上在该仓库统一治理。除非未来 ADR 证明必须拆分，否则不为 Core、
HTTP、Server、Record 或官方扩展另建仓库。

单仓库不等于所有开发者共用一条分支或一个工作目录。并行开发必须遵循
ADR-001 和 `docs/development/CONCURRENT_DEVELOPMENT.md`：

- 一个任务对应一个 Issue、一个分支、一个主写入者和一个 PR；
- 每个并行开发者使用独立 worktree 或独立 clone；
- 每个工作区使用独立虚拟环境、运行目录、缓存和端口；
- Issue 必须声明写入范围、依赖关系和集成顺序；
- 写入范围重叠或修改同一公共契约时禁止并行；
- 公共契约和基础能力先合并，依赖任务再同步；
- 开发可以并行，进入 `main` 的集成必须串行；
- 最终合并权属于项目负责人。

该决策只确认一个仓库，不确认一个还是多个 Python distribution，也不确认
`packages/`、`src/` 或最终源码目录。

### 3.10 并发安全总原则

开发并发和框架运行时并发是两个独立问题。

开发并发按照 ADR-001 通过任务隔离、路径所有权和串行集成解决。

框架运行时并发的具体实现尚未冻结，但必须满足以下不可退让的要求：

- 并发数量、队列、任务和资源必须有界；
- 任务必须有明确所有者和生命周期；
- Request、Context、Operation 和 Extension 状态必须隔离；
- Blocking 工作不得无控制地阻塞事件循环；
- Deadline 和取消必须沿调用链传播；
- Shutdown 必须排空、取消或终止剩余任务，并给出可观测结果；
- 超载必须背压或拒绝，不能无限排队；
- 必须测试竞态、死锁、任务泄漏、连接泄漏、取消风暴和慢客户端。

事件循环、Worker、多进程、线程池、Task Group 和 Admission Control 的具体模型
仍属于 P0 后续决策。

## 4. Request ID 与 Runtime Record

每个进入业务处理的请求必须拥有内部 Request ID，并建立独立、可审计的
Runtime Record。

记录范围应覆盖：

- 连接接入与协议解析；
- 路由和中间件；
- 参数提取与验证；
- 业务处理；
- 数据库、缓存、外部 HTTP、消息和扩展调用；
- 响应提交与流式发送；
- 异常、取消、清理和最终状态。

Runtime Record 必须具备：

- 捕获策略；
- 默认脱敏；
- 大小和容量限制；
- TTL 与清理；
- 原子写入；
- 权限和路径安全；
- 队列背压；
- 崩溃恢复；
- 磁盘安全线；
- 写入失败处理。

具体目录、存储格式、独立 distribution 还是内部模块仍待确认。

## 5. 当前禁止事项

P0 冻结前禁止：

- 创建生产源码；
- 创建暗示最终架构的包或目录骨架；
- 引入运行时依赖；
- 实现 Kernel、HTTP Runtime、Native Server、Router、Middleware 或扩展；
- 发布安装包；
- 建立 Sanic 适配或迁移层；
- 建立旧 API 兼容层；
- 按历史 v0.6 候选稿直接创建 `packages/` 或任何 `src/` 目录；
- 多个开发者共享同一可写工作目录；
- 多个主写入者同时写同一分支；
- 两个并行任务修改重叠路径或同一公共契约；
- 启动 P1。

## 6. 尚未确认的架构决策

以下内容必须由多多逐项确认后才能进入本文件的冻结部分：

### 6.1 已确认单仓库后的打包与源码布局

已经确认：只有一个规范仓库 `qianhuaqi/lingshu`。

仍未确认：

- 一个 Python distribution 还是在同一仓库发布多个 distribution；
- 是否使用 `packages/`；
- 是否使用任何 `src/` layout；
- 是否直接采用根级 `lingshu/`；
- tests、examples、tools、templates、benchmarks、fuzz 等目录位置；
- 一个还是多个 `pyproject.toml`。

### 6.2 组件边界

- Core、HTTP、Server、Record、CLI 是内部模块还是独立 distribution；
- 它们之间的最终依赖方向；
- Request Record 是否默认内置；
- WebSocket、OpenAPI、Observability 等能力的归属。

### 6.3 官方能力与扩展

- Auth；
- Tenant 与 Tenant-Auth bridge；
- RBAC；
- Data、SQL 和各数据库驱动；
- Cache 与 Redis；
- i18n；
- OpenAPI；
- Observability；
- Resilience；
- Scheduler、Storage 等能力。

这里列出的是能力候选，不代表已经批准独立 distribution。

### 6.4 运行时并发实现

- 默认事件循环与替代实现；
- 结构化 Task Group API；
- Worker 与多进程模型；
- 线程和 Blocking 工作隔离；
- App、Worker、Request、Operation 的并发所有权；
- 并发限额、Admission Control 与背压接口；
- Deadline 与取消 API；
- 优雅关闭和任务排空顺序；
- 竞态、死锁、泄漏与超载测试矩阵。

### 6.5 发布与支持

- P1 之后的实施阶段；
- v0.x 版本映射；
- Python 支持范围；
- Linux 与 Windows 支持范围；
- 首个公开安装包的发布时机；
- v1.0 公共 API 冻结范围；
- License、贡献、安全披露和发布政策。

## 7. P0 Hardening 合并要求

`P0_HARDENING_CHECKLIST.md` 是临时收敛清单，不是第二份总体架构。

冻结前必须把确认内容并入本文件，包括：

- system time 与 monotonic time；
- Request、Connection、Trace、Operation 等标识；
- 异常分类和敏感信息处理；
- 配置版本、校验、热更新和回滚；
- 序列化规则；
- Async Context 隔离；
- Telemetry 标准字段；
- Worker、连接、队列、Runtime Record 和磁盘资源预算。

并入完成后，清单必须归档或改为验收记录，避免形成双重事实源。

## 8. 决策确认流程

候选决策只有同时满足以下条件才成为 Confirmed：

1. GitHub Issue 中写明问题和选项；
2. Blueprint 修改或 ADR 记录最终选择；
3. 多多明确确认；
4. PR 经过审查并合并；
5. `P0_DECISION_STATUS.md` 同步状态。

聊天中的临时讨论不能直接覆盖仓库事实源。

## 9. P0 退出条件

P0 只有满足以下条件才能结束：

1. 本总纲由多多确认；
2. 所有已确认 hardening 内容已并入本文件；
3. 不存在第二份具有相同权威级别的总体设计；
4. 单仓库内的 distribution、源码和扩展结构已经确认；
5. Kernel、HTTP、Server、Request Record 的职责边界已经确认；
6. 运行时并发、启动、请求、响应、关闭和崩溃恢复语义已经确认；
7. P1 范围和验收标准可直接写入 Issue；
8. 旧实施 Issue 已关闭或历史化；
9. 多多明确授权启动 P1。

在此之前，所有开发模型只允许执行 P0 文档和治理工作。
