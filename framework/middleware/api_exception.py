#!/usr/bin/env python
# -*- coding: utf-8 -*-

from framework.exception import APIException as FrameworkAPIException


class APIException(FrameworkAPIException):
    def __init__(self, errcode, errmsg=None, data=None, status_code=400, request=None):
        super().__init__(errcode=errcode, errmsg=errmsg, data=data, status_code=status_code, request=request)
