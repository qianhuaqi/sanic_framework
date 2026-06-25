#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import os

from framework.middleware.json import CustomJSONEncoder


def exists_path(path):
    folder = os.path.exists(path)
    if not folder:
        os.makedirs(path, mode=0o777)
    return True


def write_verify_log(request, **kwargs):
    from datetime import datetime
    now = datetime.now()
    log_path = request.app.config['App']['log_path']
    app = request.app.config['App']['app']
    log_dir = f"{log_path}/{app}/{now:%Y%m%d}/{now:%H}"
    exists_path(log_dir)
    with open(f"{log_dir}/{now:%M}.log", "a", encoding="utf-8") as f:
        f.write(json.dumps(kwargs, cls=CustomJSONEncoder) + "\n")
        f.flush()
