# Architecture

This project separates stable framework code from versioned MVC business code.

`framework` owns application creation, configuration, routing policy, middleware, lifecycle hooks, logging, errors, responses, database clients, extensions, i18n, and model base classes. Business developers should normally avoid editing this directory.

`app` is intentionally small. It contains `bootstrap.py`, `route.py`, `common.py`, `event.py`, project-level controllers, and versioned MVC apps such as `app/v1`.

`app/v1/controller`, `app/v1/model`, and `app/v1/view` are the default business development locations. New projects can be initialized with `sanic-framework init my_api`, additional versions can be scaffolded with `sanic-framework add v2`, and RESTful modules can be created with `sanic-framework make module v1 demo`.

`language` contains project-level language resources and error-code module ranges. Version-specific language resources live under `app/v1/language` and override project-level resources for version-aware lookups.

`framework/scaffold` contains templates used by the framework CLI. It is part of the installed framework package and should not be edited inside generated business projects.

`public/docs` is the public documentation location. Runtime config, language resources, and tests remain outside `public`.
