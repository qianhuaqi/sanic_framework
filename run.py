#!/usr/bin/env python
# -*- coding: utf-8 -*-

try:
    from lingshu.app import create_app
    from lingshu.runtime import run_app
except ModuleNotFoundError as exc:
    if exc.name == "lingshu":
        raise SystemExit('LingShu is not installed. Run: python -m pip install -e ".[dev]"') from exc
    raise


app = create_app()


if __name__ == "__main__":
    run_app(app)
