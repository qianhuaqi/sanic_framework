#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import os

from framework.exception import APIException, get_error_message
from framework.middleware.json import CustomJSONEncoder


def get_error(request, error_type, errcode, status_code=200):
    raise APIException(code=errcode, msg=get_error_message(request, errcode), status_code=status_code)


def Error(request, error_type, errcode, data=None, status_code=200):
    return APIException(code=errcode, msg=get_error_message(request, errcode), data=data, status_code=status_code)


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
