# Architecture

This project separates stable framework code from versioned MVC business code.

`framework` owns application creation, configuration, routing policy, middleware, lifecycle hooks, logging, errors, responses, database clients, extensions, i18n, and model base classes. Business developers should normally avoid editing this directory.

`app` is intentionally small. It contains `bootstrap.py`, `route.py`, `helper.py`, `common.py`, `event.py`, project-level controllers, shared language resources, and versioned MVC apps such as `app/v1`.

`app/helper.py` is the project-level common function entry. `app/common.py` is reserved for constants, enums, and static definitions.

`lingshu init my_api` creates only the public project skeleton. It does not create `app/v1`. Additional versions can be scaffolded with `lingshu add v1`.

`app/v1/controller`, `app/v1/model/table`, `app/v1/model/business`, and `app/v1/view` are the default versioned business development locations. RESTful modules can be created with `lingshu make module v1 demo`.

Physical table models live in `app/v1/model/table`. One physical table maps to one file and one `Model` subclass. Multi-table business models live in `app/v1/model/business` and inherit `BusinessModel`; they must not declare `table_name`.

`app/language` contains project-level shared language resources and error-code module ranges. Version-specific language resources live under `app/v1/language` and override shared resources for version-aware lookups.

`lingshu/scaffold` contains templates used by the framework CLI. It is part of the installed framework package and should not be edited inside generated business projects.

`public/docs` is the public documentation location. Runtime config, language resources, and tests remain outside `public`.

At runtime, the framework serves `public/docs` under `/docs` and the whole `public` directory under `/public`.
