# Sanic Framework

Versioned MVC Sanic framework template with optional MySQL, Redis, and MongoDB integrations.

## Create a Project

```powershell
pip install sanic-framework
sanic-framework init my_api --databases mysql,redis
sanic-framework add v1
sanic-framework make module v1 demo
```

The framework keeps stable infrastructure in `framework/`. Business code lives under `app/v1`, `app/v2`, and later version folders.

## Run Locally

```powershell
copy .env.example .env
python run.py
```

No-database mode starts without external services and exposes health-check endpoints.

## Run Tests

```powershell
python -m pytest tests -q
```

## Structure

- `framework`: stable framework code, normally not edited by business developers.
- `app/route.py`: project route registration.
- `app/controller`: project-level controllers such as health and meta endpoints.
- `app/v1/controller`: versioned API controllers.
- `app/v1/model`: versioned models.
- `app/v1/view`: versioned views or lightweight API pages.
- `language`: project-level language and error-code resources.
- `app/v1/language`: version-specific language overrides, higher priority than project `language`.
- `public/docs`: public API documentation or generated static docs.
- `tests`: framework and project verification.

## Databases

Database integrations are built in but optional. Select MySQL, Redis, MongoDB, any combination of them, or none during project initialization.

When no database is selected, the generated project should still start and serve `/health`.

MySQL supports single-master and master-slave read/write separation. Redis supports single-node and sentinel modes.

## Module Generation

Generated modules are RESTful only. For example `sanic-framework make module v1 demo` creates:

- `GET /v1/demo`
- `GET /v1/demo/<id>`
- `POST /v1/demo`
- `PUT /v1/demo/<id>`
- `PATCH /v1/demo/<id>`
- `DELETE /v1/demo/<id>`

Legacy route names such as `/add`, `/edit`, and `/del` are not generated. Projects can add custom aliases in their own controller decorators when needed.

## Route Policy

Controllers can declare route policy near their routes. Health and meta endpoints are public by default. Protected APIs can opt into auth, signing, and maintenance checks explicitly.

## Error Codes

Use `/meta/error-codes` to inspect configured codes. Use `/meta/error-codes?version=v1` to include version-specific language overrides.

## Secrets

Do not commit `.env`. Use `.env.example` for safe sample values only.
