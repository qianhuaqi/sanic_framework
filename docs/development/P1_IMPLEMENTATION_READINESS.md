# P1 Implementation Readiness Gate

- Blueprint：`docs/architecture/LINGSHU_FRAMEWORK_BLUEPRINT.md` v0.6
- ADR：`docs/decisions/ADR-006-independent-kernel-runtime-layout.md`
- 状态：Draft，等待多多确认 P0 后生效

## P1 目标

建立 LingShu 单仓多包骨架和强制质量门，不实现 HTTP 业务行为、Native Server、Auth、Database 或兼容层。

## 允许范围

```text
repo pyproject/tooling
packages/lingshu-core skeleton
packages/lingshu-http skeleton
packages/lingshu-record skeleton
packages/lingshu-server skeleton
packages/lingshu-cli skeleton
packages/lingshu-framework skeleton
CI/build/install tests
architecture import rules
Docstring/type/comment quality gates
```

## 禁止范围

```text
HTTP parser implementation
Router implementation
Request processing
Extension runtime implementation
Auth/Tenant/RBAC
Database/Cache
旧代码迁移或兼容
性能优化
发布 PyPI
```

## 交付

1. 每个基础 Package 有独立 `pyproject.toml`、README、`src/`、tests；
2. 仓库级工具和测试入口；
3. Package 依赖方向的静态合同测试；
4. 公共 API Docstring 和类型标注检查；
5. TODO 格式检查；
6. Wheel/Sdist Build 和 Clean Install Smoke Test；
7. Python 3.10～3.14 CI 计划；
8. Windows/Linux 基础矩阵；
9. 所有包只有最小占位公共类型，不实现业务功能。

## 验收条件

- Blueprint 与 ADR 已由多多确认；
- 所有包能独立构建和安装；
- Core 无第三方 Runtime 依赖；
- `core -> http/server/record/extensions` 被测试禁止；
- 公共占位 API 具备完整 Docstring 和类型标注；
- 全量测试、构建和安装验证通过；
- 没有生产行为迁移；
- 没有 PR 自动合并；
- 完成后等待小顾独立验收和多多最终合并。
