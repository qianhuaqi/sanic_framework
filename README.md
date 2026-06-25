# Sanic Framework

Sanic Framework is a versioned MVC API framework template for Sanic. It keeps framework code stable in `framework/`, keeps business code in `app/`, and supports optional MySQL, Redis, and MongoDB integrations.

## Quick Start

```powershell
pip install sanic-framework
sanic-framework init my_api --databases mysql,redis
cd my_api
copy .env.example .env
python run.py
```

Create a version and a RESTful module:

```powershell
sanic-framework add v1
sanic-framework make module v1 demo
sanic-framework make model v1 user
sanic-framework make business-model v1 permission_assign
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
framework/              Stable framework core; business projects should not edit it
public/
  docs/                 Public docs served from /docs
tests/                  Framework and project verification
run.py                  Application entrypoint
.env.example            Safe environment example
.env                    Local environment, never commit
```

`framework/` is the reusable framework core. If a framework bug is found, fix and release the framework instead of patching generated business projects by hand.

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
request.app.ctx.logger.debug("demo.index page=%s size=%s", page, size)
request.app.ctx.logger.info("demo.create fields=%s", sorted(payload.keys()))
request.app.ctx.logger.exception("demo.create failed")
```

The generated demo controller shows normal usage:

- `debug` for query details in `index` and `info`
- `info` for create, update, and delete operations
- SQL execution logs are written by the framework model/database layer when a request is available

## MVC Development

`sanic-framework init` renders only the shared project skeleton. It does not create `app/v1`, a demo module, or versioned MVC directories. Add each version explicitly:

```powershell
sanic-framework add v1
sanic-framework add v2
sanic-framework add v1_admin
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
sanic-framework make model v1 a
sanic-framework make model v1 a_b
sanic-framework make model v1 a_b_c
```

Business models live under `app/<version>/model/business/`. They inherit `BusinessModel`, end with the `BusinessModel` suffix, and do not declare `table_name`:

```powershell
sanic-framework make business-model v1 permission_assign
```

Keep controllers thin. Shared request checks, payload parsing, and language resolution belong in framework helpers; multi-table workflows belong in business models rather than being stitched together inside controllers.

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
from framework.exception import raise_code

raise_code(request, 991111, status_code=400)
```

## Language And Error Codes

Shared language resources live in `app/language`.

Version-specific overrides live in `app/v1/language`, `app/v2/language`, and so on. Version resources have higher priority than shared resources.
Framework fallback resources live in `framework/language` when present. The legacy top-level `language/` directory is not part of the formal lookup path.

The formal lookup order is:

1. `app/<version>/language`
2. `app/language`
3. `framework/language`

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
sanic-framework check
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

## Security Notes

Do not commit `.env`.

Keep secrets in environment variables or deployment secrets:

- `AUTH_SECRET`
- `SIGNING_SECRET`
- `CRYPT_RESPONSE_SECRET`
- `CRYPT_PARAMS_SECRET`
- database passwords
