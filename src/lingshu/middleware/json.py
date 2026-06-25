#!/usr/bin/env python
# -*- coding: utf-8 -*-
# app/middleware/json.py

import json
from decimal import Decimal


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)  # 或者返回 float(obj)
        return super().default(obj)
