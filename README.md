# LingShu Framework / 灵枢框架

LingShu Framework is a versioned MVC API framework template for Sanic. It keeps framework code in the `lingshu` Python package, keeps business code in `app/`, and supports optional MySQL, Redis, and MongoDB integrations.

## Quick Start

```powershell
pip install lingshu-framework
lingshu init my_api --databases mysql,redis
cd my_api
copy .env.example .env
python run.py
```

Create a version and a RESTful module:

```powershell
lingshu add v1
lingshu make module v1 demo
lingshu make model v1 user
lingshu make business-model v1 permission_assign
```

The generated module exposes:

- `GET /v1/demo`
- `GET /v1/demo/<id>`
- `POST /v1/demo`
- `PUT /v1/demo/<id>`
- `PATCH /v1/demo/<id>`
- `DELETE /v1/demo/<id>`

Generated controllers keep only five methods: `index`, `info`, `create`, `update`, and `delete`.
`PUT` and `PATCH` share the same `update` handler; generated code never creates `partial_update`.

## Directory Guide

```text
app/                    Business application code
  bootstrap.py          Project extension and blueprint bootstrap
  route.py              Project route registration
  helper.py             Project-level common functions
  common.py             Project-level constants, enums, and static definitions
  event.py              Project event definitions
  controller/           Project-level controllers, such as health and meta
  language/             Shared language package and error-code catalog
  v1/                   Versioned MVC app
    controller/         v1 API controllers
    model/table/        v1 physical table models
    model/business/     v1 multi-table business models
    view/               v1 views or lightweight API pages
    language/           v1 language overrides
config/
  defaults.py           Project defaults used before .env overrides
src/lingshu/          Stable framework core; business projects should not edit it
public/
  docs/                 Public docs served from /docs
tests/                  Framework and project verification
run.py                  Application entrypoint
.env.example            Safe environment example
.env                    Local environment, never commit
```

`src/lingshu/` is the reusable framework core. If a framework bug is found, fix and release the framework instead of patching generated business projects by hand.

## Configuration

Copy `.env.example` to `.env`, then change only the values needed by the project.

Database integrations are controlled by independent switches:

```env
MYSQL_ENABLED=false
REDIS_ENABLED=false
MONGO_ENABLED=false
SQLITE_ENABLED=false
```

MySQL supports single master or master/slave reads:

```env
MYSQL_ENABLED=true
MYSQL_MASTER_HOST=localhost
MYSQL_MASTER_PORT=3306
MYSQL_MASTER_USER=app
MYSQL_MASTER_PASSWORD=change-me
MYSQL_MASTER_DATABASE=app
MYSQL_SLAVES=10.0.0.2:3306,10.0.0.3:3306
```

Redis supports single-node or sentinel mode:

```env
REDIS_ENABLED=true
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_SENTINEL_ENABLED=false
REDIS_SENTINELS=
REDIS_MASTER_NAME=mymaster
```

## Logging

Runtime logging is configured in `.env`:

```env
LOG_TO_FILE=true
LOG_LEVEL=INFO
LOG_PATH=runtime/logs
LOG_FILE=app.log
LOG_FORMATTER=%(asctime)s [%(levelname)s] [%(name)s] %(message)s
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=7
```

`LOG_PATH` is created automatically. `runtime/` is ignored by git, so local log files will not be committed.

Use the project logger in controllers, models, and services:

```python
from lingshu import logger

logger.debug("demo.index page=%s size=%s", page, size)
logger.info("demo.create fields=%s", sorted(payload.keys()))
logger.exception("demo.create failed")
```

The generated demo controller shows normal usage:

- `debug` for query details in `index` and `info`
- `info` for create, update, and delete operations
- SQL execution logs are written by the framework model/database layer when a request is available

## MVC Development

`lingshu init` renders only the shared project skeleton. It does not create `app/v1`, a demo module, or versioned MVC directories. Add each version explicitly:

```powershell
lingshu add v1
lingshu add v2
lingshu add v1_admin
```

Use `app/helper.py` for small project-level common functions:

```python
def mask_mobile(mobile: str) -> str:
    if not mobile or len(mobile) < 7:
        return mobile
    return f"{mobile[:3]}****{mobile[-4:]}"
```

Use version-level files when behavior is version-specific:

```text
app/v1/controller/demo.py
app/v1/model/table/demo.py
app/v1/model/business/
app/v1/view/demo/index.html
app/v1/language/
```

Physical table models live under `app/<version>/model/table/`. One physical table maps to one file, and underscores are part of the table name rather than a multi-table convention:

```powershell
lingshu make model v1 a
lingshu make model v1 a_b
lingshu make model v1 a_b_c
```

Business models live under `app/<version>/model/business/`. They inherit `BusinessModel`, end with the `BusinessModel` suffix, and do not declare `table_name`:

```powershell
lingshu make business-model v1 permission_assign
```

Keep controllers thin. Shared request checks, payload parsing, and language resolution belong in framework helpers; multi-table workflows belong in business models rather than being stitched together inside controllers.
## Public Facade

Business code should use the stable top-level facade:

```python
from lingshu import logger, config, app, request, db, language, abort

logger.info("started")
debug = config.debug
raw_request = request.raw
message = language.get(991111)
abort(991111, status=400)
```

Direct Sanic context access such as `request.app.ctx.*` is reserved for LingShu internals under `lingshu.system`.

## Breaking Migration

Phase B is a hard migration:

- `framework` became `lingshu`
- `sanic-framework` became `lingshu`
- `request.app.ctx.*` examples became the `lingshu` top-level facade
- `Model(request)` became `Model()`
- `BusinessModel(request)` became `BusinessModel()`
- no compatibility `framework` package or dual CLI is provided

## Response Format

All API responses use:

```json
{
  "code": 0,
  "msg": "ok",
  "data": {}
}
```

Raise business errors by code so messages come from the language package:

```python
from lingshu.exception import raise_code

raise_code(request, 991111, status_code=400)
```

## Language And Error Codes

Shared language resources live in `app/language`.

Version-specific overrides live in `app/v1/language`, `app/v2/language`, and so on. Version resources have higher priority than shared resources.
Framework fallback resources live in `lingshu/language` when present. The legacy top-level `language/` directory is not part of the formal lookup path.

The formal lookup order is:

1. `app/<version>/language`
2. `app/language`
3. `lingshu/language`

Raise errors by code only. Business code and generated controllers should not pass hard-coded error-message keyword strings.

Inspect error codes during development:

```text
GET /meta/error-codes
GET /meta/error-codes?version=v1
GET /meta/error-codes?module=param
GET /meta/error-codes?code=991111
```

The module ranges are defined in `app/language/modules.ini`.

## Contract Check

Run the project contract checker before committing generated or business code:

```powershell
lingshu check
```

The checker validates required project files, versioned controller handlers, shared `PUT`/`PATCH` update routing, forbidden `partial_update`, hard-coded error messages, table model contracts, and business model contracts. Errors include the file path and reason.

## Public Docs

Files under `public/docs` are served from `/docs`.

Example:

```text
public/docs/index.md  ->  /docs/index.md
```

This can be used for heartbeat pages, API documents, or generated static documentation.

## Tests

Run all tests:

```powershell
python -m pytest tests -q
```

The test suite checks project initialization, RESTful module generation, language packages, response format, database configuration, logging, CORS, and framework boundary rules.

## 双机开发交接

同一阶段分支同一时间只允许一台电脑写入。开始修改前先确认 GitHub PR 最新评论中没有未结束的 `[WORKING]` 锁；只有最新评论为 `[HANDOFF]` 且远程分支已更新后，另一台电脑才可以接手。

工作地点只使用 `office` 或 `home`，不要在文档、提交信息或 PR 评论中写入真实地点、账号、网络地址、凭据或本地绝对路径。

### 离开当前电脑前

```powershell
git status
# 运行本次相关测试
git add -A
git commit -m "chore: checkpoint current work"
git push github <当前分支>
# 更新并再次提交 HANDOFF 后重新 push
.\scripts\verify-handoff.ps1 -Branch <当前分支>
```

为避免 `HANDOFF.md` 记录自身提交 SHA 造成循环追写，交接采用两步提交：

1. 提交并推送实际功能或治理代码。
2. 获取已推送的工作基线 SHA。
3. 更新 `docs/codex/HANDOFF.md`。
4. 单独创建 handoff 提交并推送。
5. 在 `HANDOFF.md` 中用 `Work commit`、`Handoff commit`、`Remote HEAD` 明确区分本次工作成果、交接文档提交和最终远程 HEAD。

### 到另一台电脑后

```powershell
git status
.\scripts\resume-work.ps1 -Branch <当前分支>
```

然后按顺序确认：

1. 阅读 `AGENTS.md`。
2. 阅读 `docs/codex/CURRENT_PHASE.md`。
3. 阅读 `docs/codex/HANDOFF.md`。
4. 阅读当前 PR 最新评论。
5. 核对本地 HEAD 与远程 HEAD。
6. 再开始修改代码。

### PR 工作锁协议

开始工作时，在当前 PR 评论：

```text
[WORKING]
Location: office
Branch: codex/phase-b-lingshu-context
Start SHA: <完整SHA>
Tasks:
- ...
```

结束或换电脑前，在当前 PR 评论：

```text
[HANDOFF]
Location: office
Branch: codex/phase-b-lingshu-context
Work commit: <完整SHA>
Remote HEAD: <完整SHA>
Worktree: clean
Tests:
- ...
Completed:
- ...
Remaining:
- ...
Next action:
- ...
```

`[WORKING]` 和 `[HANDOFF]` 评论只记录通用开发状态，不记录凭据、本地用户名、网络地址或真实地点名称。

## Local Development Setup

PowerShell recommended flow:

```powershell
.\scripts\setup-dev.ps1
.\.venv\Scripts\python.exe run.py
```

Manual flow:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe run.py
```

PyCharm setup:

- Interpreter: choose this repository's `.venv`.
- Working directory: use the repository root.
- Script path: use `run.py` from the repository root.

This repository uses `src` layout. Do not use `sys.path.insert()` to bypass editable install. If `run.py` says LingShu is not installed, run:

```powershell
python -m pip install -e ".[dev]"
```

## Cross-Device Handoff

Only one computer may write to a phase branch at a time. Before editing, confirm the latest GitHub PR comments do not contain an open `[WORKING]` lock. Another computer may continue only after the latest status is `[HANDOFF]` and the remote branch is up to date.

Use only `office` or `home` for location labels. Do not record real locations, accounts, network addresses, credentials, or local absolute paths.

### Before Leaving

```powershell
git status
# Run relevant tests for this change
git add -A
git commit -m "chore: checkpoint current work"
git push github <current-branch>
.\scripts\verify-handoff.ps1 -Branch <current-branch>
```

`HANDOFF.md` must not require `Local HEAD` or `Remote HEAD` to equal the commit that contains the file. That is a SHA self-reference loop. The file records `Work commit` as the work baseline; `verify-handoff.ps1` prints the final remote HEAD, and the final remote HEAD is recorded in the PR `[HANDOFF]` comment.

### On The Other Computer

```powershell
git status
.\scripts\resume-work.ps1 -Branch <current-branch>
```

Then confirm:

1. Read `AGENTS.md`.
2. Read `docs/codex/CURRENT_PHASE.md`.
3. Read `docs/codex/HANDOFF.md`.
4. Read the latest PR comments.
5. Verify local HEAD equals remote HEAD.
6. Start editing only after those checks pass.

### PR Work Lock

Start work with a PR comment:

```text
[WORKING]
Location: office
Branch: codex/phase-b-lingshu-context
Start SHA: <full-sha>
Tasks:
- ...
```

End or transfer work with a PR comment:

```text
[HANDOFF]
Location: office
Branch: codex/phase-b-lingshu-context
Work commit: <full-sha>
Remote HEAD: <full-sha>
Worktree: clean
Tests:
- ...
Completed:
- ...
Remaining:
- ...
Next action:
- ...
```

`[WORKING]` and `[HANDOFF]` comments record generic development state only. Do not include credentials, local usernames, network addresses, or real location names.

## Security Notes

Do not commit `.env`.

Keep secrets in environment variables or deployment secrets:

- `AUTH_SECRET`
- `SIGNING_SECRET`
- `CRYPT_RESPONSE_SECRET`
- `CRYPT_PARAMS_SECRET`
- database passwords
