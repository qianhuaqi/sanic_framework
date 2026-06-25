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
```

The generated module exposes:

- `GET /v1/demo`
- `GET /v1/demo/<id>`
- `POST /v1/demo`
- `PUT /v1/demo/<id>`
- `DELETE /v1/demo/<id>`

Generated controllers keep only five methods: `index`, `info`, `create`, `update`, and `delete`.

## Directory Guide

```text
app/                    Business application code
  bootstrap.py          Project extension and blueprint bootstrap
  route.py              Project route registration
  common.py             Project-level common functions
  event.py              Project event definitions
  controller/           Project-level controllers, such as health and meta
  language/             Shared language package and error-code catalog
  v1/                   Versioned MVC app
    controller/         v1 API controllers
    model/              v1 models
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

Use `app/common.py` for small project-level common functions:

```python
def mask_mobile(mobile: str) -> str:
    if not mobile or len(mobile) < 7:
        return mobile
    return f"{mobile[:3]}****{mobile[-4:]}"
```

Use version-level files when behavior is version-specific:

```text
app/v1/controller/demo.py
app/v1/model/demo.py
app/v1/view/demo/index.html
app/v1/language/
```

If logic becomes large, place it in a service module owned by the business project rather than putting everything into a controller.

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

Inspect error codes during development:

```text
GET /meta/error-codes
GET /meta/error-codes?version=v1
GET /meta/error-codes?module=param
GET /meta/error-codes?code=991111
```

The module ranges are defined in `app/language/modules.ini`.

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
