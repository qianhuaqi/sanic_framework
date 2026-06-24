#!/usr/bin/env python
# -*- coding: utf-8 -*-
# app/middleware/maintenance.py
import json

from sanic import response

from framework.middleware.crypt_des import encrypt_data


def maintenance_required(handler):
    async def wrapper(request, *args, **kwargs):
        redis = request.app.ctx.redis
        service_switch_key = '{}_{}_service_switch'.format(request.app.config.APP, request.app.config.PROJECT)
        # await redis.set(service_switch_key, 1)
        service_switch = await redis.get(service_switch_key)

        if service_switch and service_switch.decode() == '1':
            # 服务正在维护
            maintenance_content_key = '{}_{}_service_content'.format(
                request.app.config.APP,
                request.app.config.PROJECT
            )
            maintenance_content = await redis.get(maintenance_content_key)
            allow_encryption = True if str(request.app.config.CRYPT.get('enabled', False)).lower() == 'true' else False

            if maintenance_content:
                maintenance_info = json.loads(maintenance_content.decode())
                data = {
                    'category': maintenance_info.get('category', 1),
                    'start_time': maintenance_info.get('start_time', '2024-07-14 21:00:00'),
                    'end_time': maintenance_info.get('end_time', '2024-07-16 21:00:00'),
                    'content': maintenance_info.get('content', '')
                }

            else:
                data = {
                    'category': 1,
                    'start_time': '',
                    'end_time': '',
                    'content': ''
                }

            if allow_encryption:
                if data:
                    data = encrypt_data(request, data)
                else:
                    data = {}

            return response.json({
                'errcode': 0,
                'errmsg': '系统维护中，请稍后再试',
                'data': data
            }, status=208)
        else:
            # 服务正常，继续处理请求
            return await handler(request, *args, **kwargs)

    return wrapper
