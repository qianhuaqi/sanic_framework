#!/usr/bin/env python
# -*- coding: utf-8 -*-
# app/middleware/crypt_params.py

import json

from sanic.request import Request

from lingshu.exception import APIException
from lingshu.middleware.crypt_des import decrypt_data
from lingshu.middleware.params import params_convert, params_filter, params_exists, over_limit, regex_validate, I
from lingshu.system import sanic_adapter


class CryptParams:
    def __init__(self, request: Request, param_name='params'):
        """
        初始化解密参数处理类，并解析加密的参数。

        :param request: Sanic请求对象
        :param param_name: 加密参数的键名，默认为 'params'
        """
        self.request = request
        self.param_name = param_name
        # 检查是否已经解密过参数
        if hasattr(self.request.ctx, 'crypt_params_dict'):
            self.params_dict = self.request.ctx.crypt_params_dict
        else:
            try:
                # 获取并解密参数
                self.params = I(request, name=param_name, type='str')
                if self.params:
                    config = sanic_adapter.get_request_config(self.request)
                    secret = config.crypt_response_secret
                    key = f"{secret}{config.app_name}{secret}"

                    params_str = decrypt_data(request, self.params, key)
                    self.params_dict = json.loads(params_str)
                else:
                    self.params_dict = {}  # 如果参数不存在，则设置为空字典

                # 将解密后的参数存储到 request.ctx 中
                self.request.ctx.crypt_params_dict = self.params_dict
            except Exception:
                code = 991104
                from lingshu.exception import get_error_message

                msg = get_error_message(self.request, code)
                raise APIException(code=code, msg=msg, status_code=400)

    def get_param(self, **kwargs):
        """
        获取指定的参数，并进行类型转换、正则验证、长度检查等。

        :param kwargs: 参数名、类型、是否必须、错误消息、默认值、正则表达式、最小长度、最大长度等。
        :return: 转换后的参数值
        """
        param_name = kwargs.get('name')
        requisite = kwargs.get('requisite', False)
        param_type = kwargs.get('type', 'str')
        default_value = kwargs.get('default', '')
        regex = kwargs.get('regex')
        min_length = kwargs.get('min_length', -1)
        max_length = kwargs.get('max_length', -1)
        msg = kwargs.get('msg', '')

        if requisite:
            params_exists(self.request, self.params_dict, param_name, msg=msg or f'{param_name}不存在')

        value = params_filter(self.params_dict.get(param_name, default_value))
        if value:
            if min_length or max_length:
                over_limit(self.request, param_name, value, min_length, max_length)
            if regex:
                regex_validate(self.request, value, regex)
            if param_type:
                value = params_convert(self.request, value, param_type)

        return value or default_value

    def get(self, **kwargs):
        """
        类似于 I 函数的用法，用于获取解密后的参数。

        :param kwargs: 参数名、类型、是否必须、错误消息、默认值等。
        :return: 转换后的参数值
        """
        if not kwargs:
            return self.params_dict  # 如果没有提供参数，则返回所有解密后的参数字典

        return self.get_param(**kwargs)


# 独立的 CI 函数
def CI(request: Request, **kwargs):
    crypt_params = CryptParams(request)
    return crypt_params.get(**kwargs)
