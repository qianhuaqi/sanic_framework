#!/usr/bin/env python
# -*- coding: utf-8 -*-
# app/middleware/api_exception.py

from sanic.exceptions import SanicException


class APIException(SanicException):
    def __init__(self, errcode, errmsg, data=None, status_code=400):
        super().__init__(message=errmsg, status_code=status_code)
        self.errcode = errcode
        self.errmsg = errmsg
        self.data = data or {}
        self.status_code = status_code
