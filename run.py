#!/usr/bin/env python
# -*- coding: utf-8 -*-

from lingshu.app import create_app
from lingshu.runtime import run_app


app = create_app()


if __name__ == "__main__":
    run_app(app)
