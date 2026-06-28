# LingShu Framework 总体架构设计总纲（P0-RC3）

- 设计负责人：小顾
- 产品决策人：多多
- 状态：P0 候选总纲，尚未冻结
- GitHub Issue：#25
- 规范仓库：`qianhuaqi/lingshu`
- 治理基线：latest accepted `main`
- 已接受决策：ADR-001、ADR-002、ADR-003
- 决策状态表：`docs/architecture/P0_DECISION_STATUS.md`
- 历史候选稿：`docs/architecture/candidates/LINGSHU_FRAMEWORK_BLUEPRINT_V0.6_CANDIDATE.md`

> 本文件是当前唯一总体架构入口。只有已由多多确认，并在
> `P0_DECISION_STATUS.md` 中标记为 Confirmed 的内容，才能成为实施依据。
> P0 结束前不得创建生产源码、包骨架或运行时依赖。

---

## 1. 根本定位

LingShu 是从零开发、完全独立、自主可控的 Python Web/API Framework。

LingShu 不是 Sanic、FastAPI、Flask、Django、Starlette 或其他上层 Web
Framework 的封装、适配层或迁移版本，也不承担历史实现的兼容义务。

LingShu 自己定义并控制：

- Application Kernel；
- HTTP Runtime；
- Native Server；
- Request、Response、Router、Middleware 与 Streaming；
- 生命周期、并发、取消、清理、容量和背压；
- Extension Protocol；
- Request ID 与请求级 Runtime Record；
- CLI、测试支持和后续生态。

## 2. 历史实现边界

旧实现封存于：

```text
archive/legacy-sanic-20260628
```

封存提交：

```text
b869270e0ec7cbc324d17ef246e39d0873aab14f
```

旧源码、测试、依赖、脚手架、Issue、PR 和 API：

- 只可作为历史参考；
- 不作为新框架代码基线；
- 不产生兼容义务；
- 不允许直接复制到新框架；
- 有价值的思想必须重新进入 Issue、架构评审和新实现。

## 3. 已确认的最高原则

### 3.1 自主框架内核

灵枢核心运行能力由灵枢自行设计和实现，不通过安装其他上层 Web 框架获得。

Python 标准库可以作为语言运行基础。核心第三方依赖必须逐项评审并另立 ADR。

### 3.2 机制与政策分离

核心只提供通用机制，不把 JWT、Tenant、RBAC、数据库、ORM、Redis、用户、订单
等具体政策或业务模型写入核心。

### 3.3 单向依赖

依赖必须显式、无环并可由机器检查验证。下层机制不得反向依赖业务能力、具体
数据库、认证实现、项目代码、测试工具或根级公共 facade。

### 3.4 显式生命周期

禁止通过 import 副作用完成注册、建连、启动任务或修改进程级全局状态。

启动、运行、排空和关闭必须具备明确状态、有界预算、失败回滚、逆序清理、
幂等关闭和可观测结果。

### 3.5 默认隔离

App、Worker、Connection、Request、Operation 和 Extension 状态必须按作用域隔离。

请求、事务、用户或其他请求级可变状态不得保存为普通进程级全局变量。

### 3.6 默认有界

连接、队列、请求体、Header、并发、任务、重试、缓存、日志、执行器、
Runtime Record 和磁盘使用必须有明确上限、背压或拒绝策略。

### 3.7 取消与清理

Deadline 是完整调用链预算，不能在每层重新获得完整超时。

取消必须传播，不得静默吞掉。任何退出路径都必须执行确定性、有限时的清理。

### 3.8 安全优先

- 协议歧义直接拒绝；
- 敏感信息默认不记录；
- 不自造密码学算法、TLS 算法和证书验证；
- 安全、正确性和可恢复性优先于未经验证的极限性能。

## 4. 单仓库与开发并发（ADR-001，已确认）

规范仓库：

```text
qianhuaqi/lingshu
```

开发并发规则：

- 一个任务对应一个 Issue、一个分支、一个主写入者和一个 PR；
- 每个并行开发者使用独立 worktree 或 clone；
- 每个工作区使用独立虚拟环境、运行目录、缓存和端口；
- Issue 必须声明写入范围、依赖和集成顺序；
- 写入范围重叠或修改同一公共契约时禁止并行；
- 公共契约和基础能力先合并；
- 开发可以并行，进入 `main` 的集成必须串行；
- 最终合并权属于项目负责人。

## 5. 运行时并发模型（ADR-002，已确认）

### 5.1 标准语义与 Worker

- Python 标准库 `asyncio` 语义是正确性基线；
- 每个 Worker 进程拥有一个事件循环和一个 Application Runtime；
- Supervisor 管理 Worker、就绪状态、信号、有限重启和最终退出；
- Worker 之间不共享可变 Python 应用状态；
- 单 Worker 是语义基线，多 Worker 只扩展吞吐。

### 5.2 结构化所有权

```text
Supervisor
└─ Worker
   └─ Application Runtime
      ├─ Listener / Infrastructure tasks
      ├─ Application-owned background tasks
      └─ Connection
         └─ Request
            └─ Operation / child tasks
```

- 所有任务必须有明确 Scope；
- 子 Scope 默认不能超过父 Scope 生命周期；
- 未登记 fire-and-forget 任务被禁止；
- 请求中创建的任务默认归 Request 所有；
- 长期后台任务必须显式登记并声明启动、停止、失败、重启和关闭策略；
- 脱离请求的任务不得默认继承请求上下文。

### 5.3 HTTP/1.1 并发

- 一个 HTTP/1.1 连接同一时刻最多执行一个请求；
- 多连接可以并发；
- Keep-Alive 请求按顺序处理；
- 初始版本不并发执行 pipelined 请求，也不乱序输出响应；
- read-ahead、请求体和响应缓冲必须有界；
- HTTP/2 与 HTTP/3 多路复用另立决策。

### 5.4 准入、背压、Deadline 与取消

- Worker、连接、请求、路由、后台任务、执行器、依赖、Telemetry 和 Record 队列均有界；
- 所有等待队列具有容量和等待 Deadline；
- 网络、解析、请求体、业务、依赖、响应流和写入形成完整背压链；
- Deadline 使用绝对 monotonic time，子调用只能继承或缩短；
- 取消原因必须可区分并向子任务传播；
- cleanup shielding 必须有限且明确。

### 5.5 Blocking、崩溃与关闭

- Blocking I/O 进入有界线程执行器；
- CPU 密集工作进入有界进程执行器或外部任务系统；
- Worker 启动失败逆序清理；
- Worker 重启具有预算、速率限制和退避；
- 崩溃循环耗尽预算后停止自动重启；
- 正确性不得依赖 fork 继承可变状态。

运行状态：

```text
STARTING → RUNNING → DRAINING → STOPPING → STOPPED
```

关闭依次执行停止准入、排空、取消、停止后台任务、逆序关闭扩展、刷新记录、
关闭 Transport/执行器、Worker 退出和 hard-stop 强制终止。

详细规范：

- `docs/decisions/ADR-002-runtime-concurrency-model.md`；
- `docs/architecture/RUNTIME_CONCURRENCY_MODEL.md`。

## 6. Request ID 与 Runtime Record（已确认原则）

每个进入业务处理的请求必须拥有内部 Request ID，并建立独立、可审计的
Runtime Record。

记录覆盖连接、解析、路由、中间件、业务、外部调用、响应、异常、取消、准入、
队列等待、子任务和最终清理状态。

Runtime Record 必须具备：

- 捕获策略与默认脱敏；
- 大小、容量和队列限制；
- TTL 与清理；
- 原子写入；
- 权限和路径安全；
- 背压与过载策略；
- 崩溃恢复；
- 磁盘安全线；
- 写入失败和 flush timeout 处理。

## 7. 打包、源码与组件布局（ADR-003，已确认）

### 7.1 名称与物理布局

```text
Repository:          qianhuaqi/lingshu
Distribution:        lingshu
Import package:      lingshu
Packaging file:      pyproject.toml
Production source:   lingshu/
src layout:          prohibited
```

已确认：

- 初始框架只有一个 Python distribution；
- 只有一个根级 `pyproject.toml`；
- 所有内部组件共享一个版本和发布节奏；
- 不使用 `src/lingshu/`；
- 不使用初始 `packages/` monorepo；
- 不发布 `lingshu-core`、`lingshu-http`、`lingshu-server` 等独立包；
- 未来拆包必须通过新 ADR 和真实独立消费者证据。

### 7.2 目标目录

```text
.
├─ lingshu/
│  ├─ __init__.py
│  ├─ core/
│  ├─ runtime/
│  ├─ http/
│  ├─ server/
│  ├─ record/
│  ├─ extensions/
│  ├─ cli/
│  └─ testing/
├─ tests/
│  ├─ unit/
│  ├─ contract/
│  ├─ integration/
│  ├─ protocol/
│  ├─ concurrency/
│  ├─ security/
│  ├─ packaging/
│  └─ compatibility/
├─ docs/
├─ examples/
├─ tools/
├─ benchmarks/
├─ fuzz/
└─ pyproject.toml
```

该目录只是一项已确认架构。P0 不创建真实生产目录。

### 7.3 组件职责

#### `core`

Application Kernel、生命周期契约、基础异常、配置契约、标识和值对象、Extension
Protocol、Capability 和通用 Audit/Telemetry 协议。不得依赖其他 LingShu 组件。

#### `runtime`

Scope、Deadline、Cancellation、任务监督、Admission Control、背压、执行器和关闭
协调。只允许依赖 `core`。

#### `http`

Request、Response、Headers、Body/Streaming、Router、Middleware、HTTP 错误映射和
内容协商接口。允许依赖 `core` 与 `runtime`，不得依赖 `server`。

#### `server`

Listener、Transport、HTTP/1.1 Parser 集成、Connection、Worker、Supervisor、就绪、
排空、停止和 Transport Flow Control。允许依赖 `core`、`runtime` 与 `http`。

#### `record`

默认 Runtime Record 实现，包括事件、标识映射、脱敏、截断、有界队列、保留、
清理和安全本地写入机制。随默认 distribution 安装；重量级外部存储导出器保持可选。

#### `extensions`

扩展注册、依赖排序、Capability 绑定、生命周期、健康和清理机制。不得把 Auth、
Tenant、SQL、Redis 等具体政策默认放入本模块。

#### `cli`

已安装命令行入口和开发命令，只调用公开组合入口，不绕过生命周期和校验。

#### `testing`

Test Client、Fake Transport、Fake Monotonic Clock、确定性取消、资源快照和泄漏断言。
生产组件不得依赖 `testing`。

### 7.4 依赖方向

```text
runtime     → core
http        → runtime + core
server      → http + runtime + core
record      → core + stable runtime contracts
extensions  → core + runtime (+ documented HTTP contracts when required)
cli         → public composition surface
testing     → public/test-support surfaces
```

禁止：

- 依赖环；
- `core` 依赖其他 LingShu 组件；
- `runtime` 依赖上层组件；
- `http` 依赖 `server`；
- 生产代码依赖 `testing`；
- 下层组件导入根 facade；
- 未经决策的跨组件私有模块导入。

P1 必须建立机器化 import 边界检查。

### 7.5 公开 API 与可选依赖

- `lingshu/__init__.py` 是受控公共 facade；
- 只允许显式 `__all__`；
- 不允许通配符再导出链；
- 深层路径默认属于内部实现；
- `_` 开头的模块或名称是私有的；
- import 时禁止启动任务、建立连接、打开文件或修改进程级状态；
- `import lingshu` 不得要求数据库、Redis、云平台、Tracing 或认证库；
- 可选能力只在激活时加载；
- 缺失依赖只在相关能力激活时给出明确错误；
- 具体公共类名、函数名、extras 和官方扩展目录后续决定。

### 7.6 打包质量门

所有打包相关验收必须：

1. 构建 wheel 与 sdist；
2. 创建全新虚拟环境；
3. 非 editable 安装已构建 wheel；
4. 切换到仓库目录之外；
5. 不注入仓库 `PYTHONPATH`；
6. 执行 import、CLI 和 smoke test；
7. 检查安装文件和 metadata；
8. 确认 tests、tools、缓存、凭据和本地文件未被发布；
9. 验证 sdist 可重建预期 wheel；
10. 单独测试 editable 安装，但不能把它当发布证据。

详细规范：

- `docs/decisions/ADR-003-package-source-layout-and-component-boundaries.md`；
- `docs/architecture/PACKAGE_AND_COMPONENT_LAYOUT.md`。

## 8. 当前禁止事项

P0 冻结前禁止：

- 创建 `lingshu/` 生产源码目录、`tests/` 骨架或 `pyproject.toml`；
- 创建 `src/lingshu/` 或 `packages/` 结构；
- 引入运行时依赖；
- 实现 Kernel、Runtime、HTTP、Server、Record、CLI 或扩展；
- 发布安装包；
- 建立 Sanic 适配、迁移层或旧 API 兼容层；
- 多个开发者共享同一可写目录或分支；
- 两个并行任务修改重叠路径或同一公共契约；
- 启动 P1。

## 9. 尚未确认的架构决策

### 9.1 Application Kernel 与请求执行管线

下一项 P0-D4 需要决定：

- Application 创建、所有权和 composition root；
- 生命周期状态和配置 freeze 边界；
- Route 注册、编译和不可变边界；
- 请求执行阶段和精确顺序；
- Middleware 类型、作用域和排序；
- Request/Response 所有权、可变性和 commit 规则；
- Exception 映射；
- 最小公共 API 和根级导出；
- Extension 参与启动、关闭和请求处理的方式。

### 9.2 P0 Hardening 剩余项

- Request、Connection、Trace、Operation 标识标准；
- 异常分类和敏感信息处理；
- 配置版本、校验、热更新和回滚；
- 序列化规则；
- Runtime Record 存储预算和磁盘策略。

### 9.3 官方能力与扩展

- Auth；
- Tenant 与 Tenant-Auth bridge；
- RBAC；
- Data、SQL 和数据库驱动；
- Cache 与 Redis；
- i18n；
- OpenAPI；
- Observability；
- Resilience；
- Scheduler 与 Storage；
- WebSocket。

### 9.4 协议、平台和发布

- Python 与操作系统支持范围；
- build backend 与权威版本来源；
- Worker 监听 Socket 分发策略；
- HTTP/2 与 HTTP/3；
- 默认并发和超时数值；
- 可选第三方事件循环或解析器；
- P1 后实施阶段和 v0.x 映射；
- v1.0 公共 API 冻结范围；
- 首个 PyPI 发布时机；
- License、贡献、安全披露、变更日志和发布政策。

## 10. 决策确认流程

候选或提案只有同时满足以下条件才成为 Confirmed：

1. GitHub Issue 写明问题和选择；
2. Blueprint 修改或 ADR；
3. 多多明确确认；
4. PR 审查并合并；
5. `P0_DECISION_STATUS.md` 同步。

## 11. P0 退出条件

P0 只有满足以下条件才能结束：

1. 本总纲由多多确认；
2. 所有已确认 hardening 内容已经并入；
3. 不存在第二份同级总体设计；
4. distribution、源码、组件和扩展结构已确认；
5. Kernel、HTTP、Server、Runtime Record 职责边界已确认；
6. 启动、请求、响应、并发、关闭和崩溃恢复语义已确认；
7. P1 范围和验收标准可直接写入 Issue；
8. 旧实施 Issue 已关闭或历史化；
9. 多多明确授权启动 P1。

在此之前，所有开发模型只允许执行 P0 文档和治理工作。
