#!/usr/bin/env python
# -*- coding: utf-8 -*-
# app/middleware/sign.py
import time
from functools import wraps

from framework.exception import APIException, get_error_message
from framework.middleware.params import I
from framework.middleware.utils import md5


async def create_sign(request, kwargs):
    sign = ''
    for item in sorted(kwargs):
        sign = '{}&{}={}'.format(sign, item.lower(), kwargs[item])
    sign = sign.strip('&')
    request.app.ctx.logger.info('加密前字符串：{}'.format(sign))
    return md5(sign)


async def check_expire(request, timestamp):
    # 验证时间戳是否过期(5分钟)
    now = int(time.time())
    if (now - int(timestamp)) > 5 * 60:
        raise APIException(code=90402, msg=get_error_message(request, 90402), status_code=400)
    return True


async def get_secret(request, key):
    config = getattr(request.app.ctx, "config", None)
    if config and getattr(config, "signing_secret", None):
        return config.signing_secret
    return request.app.config.get("SIGNING_SECRET", "change-me")

async def check_sign(request, sign, key):
    params = I(request)
    params.pop('sign', None)

    # 获取应用密钥
    params['secret'] = await get_secret(request, key)

    # 验证签名
    local_sign = await create_sign(request, params)
    request.app.ctx.logger.info('param_sign：{}'.format(sign))
    request.app.ctx.logger.info('local_sign：{}'.format(local_sign))
    if local_sign != sign:
        raise APIException(code=90401, msg=get_error_message(request, 90401), status_code=400)
    return True


def sign_required(func):
    @wraps(func)
    async def wrapper(request, *args, **kwargs):
        # 获取请求参数
        key = I(request, name='key', type='str', requisite=True, msg='账户不存在')
        sign = I(request, name='sign', type='str', requisite=True, msg='签名不存在')
        timestamp = I(request, name='timestamp', type='int', requisite=True, msg='时间戳不存在')

        # 验证时间戳是否过期
        await check_expire(request, timestamp)

        # 验证签名
        await check_sign(request, sign, key)

        return await func(request, *args, **kwargs)

    return wrapper
