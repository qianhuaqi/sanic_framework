#!/usr/bin/env python
# -*- coding: utf-8 -*-
# app/middleware/params.py

import re
from sanic.request import Request
from framework.middleware.api_exception import APIException


class Params:
    @staticmethod
    def get_params(request: Request):
        content_type = request.headers.get('Content-Type', "")

        params = {}

        if content_type.startswith('application/json'):
            params.update(request.json if request.json else {})
        elif content_type.startswith('application/x-www-form-urlencoded'):
            params.update({k: v[0] for k, v in request.form.items()})
        elif content_type.startswith('multipart/form-data'):
            params.update({k: v[0] for k, v in request.form.items()})
        elif content_type.startswith('application/octet-stream'):
            params['binary_data'] = request.body

        if request.args:
            params.update({k: v[0] for k, v in request.args.items()})
        return params


def params_exists(request: Request, params, name, msg=None):
    if name not in params or (params[name] != 0 and not params[name]):
        i18n = request.app.ctx.i18n
        code = 991109 if msg else 991103
        msg = msg if msg else i18n['Param'].get(str(code))
        raise APIException(errcode=code, errmsg=msg, status_code=400)
    return True


def params_convert(request: Request, param, t):
    try:
        if t == 'int':
            return int(param)
        elif t == 'str':
            return str(param)
        elif t == 'list' and not isinstance(param, list):
            raise ValueError
        elif t == 'dict' and not isinstance(param, dict):
            raise ValueError
    except (ValueError, TypeError):
        i18n = request.app.ctx.i18n
        code = 991102
        msg = i18n['Param'].get(str(code))
        raise APIException(errcode=code, errmsg=msg, status_code=400)
    return param


def params_filter(param):
    if isinstance(param, str):
        return param.strip()
    return param


def over_limit(request: Request, param_name, param, min_length=-1, max_length=100):
    length = len(param)
    i18n = request.app.ctx.i18n
    if length >= min_length and (max_length == -1 or length <= max_length):
        return
    if max_length == -1:
        code = 991108
        msg = i18n['Param'].get(str(code)).format(param_name, min_length)
        raise APIException(errcode=code, errmsg=msg, status_code=400)
    elif min_length == -1:
        code = 991107
        msg = i18n['Param'].get(str(code)).format(param_name, max_length)
        raise APIException(errcode=code, errmsg=msg, status_code=400)
    elif min_length == max_length:
        code = 991106
        msg = i18n['Param'].get(str(code)).format(param_name, max_length)
        raise APIException(errcode=code, errmsg=msg, status_code=400)
    else:
        code = 991105
        msg = i18n['Param'].get(str(code)).format(param_name, min_length, max_length)
        raise APIException(errcode=code, errmsg=msg, status_code=400)

def regex_validate(request: Request, param, pattern):
    if not re.match(pattern, param):
        i18n = request.app.ctx.i18n
        code = 991102
        msg = i18n['Param'].get(str(code))
        raise APIException(errcode=code, errmsg=msg, status_code=400)


def I(request: Request, **kwargs):
    params = Params.get_params(request)

    if not kwargs:
        return params

    param_name = kwargs.get('name')
    msg = kwargs.get('msg', '')
    requisite = kwargs.get('requisite', False)
    param_type = kwargs.get('type')
    default_value = kwargs.get('default', None)
    regex = kwargs.get('regex')  # 正则表达式
    min_length = kwargs.get('min_length', -1)  # 最小长度
    max_length = kwargs.get('max_length', -1)  # 最大长度

    if requisite:
        params_exists(request, params, param_name, msg=msg)

    value = params_filter(params.get(param_name, default_value))

    if value:
        if min_length != -1 or max_length != -1:
            over_limit(request, param_name, value, min_length, max_length)
        if regex:
            regex_validate(request, value, regex)
        if param_type:
            value = params_convert(request, value, param_type)
    return value or default_value
