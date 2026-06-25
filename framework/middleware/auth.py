#!/usr/bin/env python
# -*- coding: utf-8 -*-
# app/middleware/auth.py
import time
from functools import wraps

import jwt
from sanic import Request

from framework.exception import raise_code
from framework.middleware.crypt_des import encrypt_data, decrypt_data
from framework.middleware.utils import md5_upper, get_client_ip

class Auth:
    def __init__(self, request: Request):
        self.request = request
        self.config = self.request.app.config['AUTH']

    async def generate_jwt(self, subject, user_id=None, name=None, grant_type=None, expire_in=7200):
        secret = self.config['secret']
        payload = {
            'exp': int(time.time()) + expire_in,
            'user': encrypt_data(self.request, user_id),
            'sub': subject,
            'name': name,
            'sole': self.get_sole()
        }
        if grant_type:
            payload['grant_type'] = grant_type
        headers = {
            'typ': 'JWT',
            'alg': 'HS256'
        }
        jwt_token = jwt.encode(
            payload,
            secret,
            headers=headers
        )
        return jwt_token

    async def decode_jwt(self, token):
        secret = self.config['secret']
        try:
            data = jwt.decode(token, secret, algorithms=['HS256'])
            if data.get('user'):
                try:
                    decrypt_user = decrypt_data(self.request, data["user"])
                except TypeError:
                    pass
                else:
                    data["user"] = int(decrypt_user)
        except Exception:
            logger = getattr(getattr(self.request.app, "ctx", None), "logger", None)
            if logger is not None:
                logger.exception("JWT decode failed")
            raise_code(self.request, 990100, status_code=401)
        else:
            if data.get('grant_type', ''):
                return None
        return data

    async def decode_refresh_token(self, token):
        """
        解密刷新token信息
        :param token: token
        :return: 返回解密信息
        """
        secret = self.config['secret']
        try:
            # 需要解析的 jwt 密钥 使用和加密时相同的算法
            data = jwt.decode(token, secret, algorithms=['HS256'])
            if data.get('user'):
                try:
                    decrypt_user = decrypt_data(self.request, data["user"])
                except TypeError:
                    pass
                else:
                    data["user"] = int(decrypt_user)
        except Exception:
            # 如果 jwt 被篡改过；或者算法不正确；如果设置有效时间，过了有效期；或者密钥不相同；都会抛出相应的异常
            logger = getattr(getattr(self.request.app, "ctx", None), "logger", None)
            if logger is not None:
                logger.exception("JWT refresh decode failed")
            raise_code(self.request, 990100, status_code=401)
        else:
            if data.get('grant_type', '') != 'refresh':
                return None
        return data

    async def get_token(self, **kwargs):
        if not kwargs.get("app"):
            kwargs["app"] = int(self.config['app'])
        expire_in = self.config['expire']
        if 'expire_in' in kwargs:
            expire_in = kwargs['expire_in']
        refresh_expire_in = expire_in * 12 * 30
        if 'refresh_expire_in' in kwargs:
            refresh_expire_in = kwargs['refresh_expire_in']
        token = await self.generate_jwt(
            subject=kwargs['app'],
            user_id=kwargs['user'],
            name=kwargs["name"],
            expire_in=expire_in
        )

        refresh_token = await self.generate_jwt(
            subject=kwargs['app'],
            user_id=kwargs['user'],
            name=kwargs["name"],
            grant_type='refresh',
            expire_in=refresh_expire_in
        )

        return {
            'token': token,
            'refresh_token': refresh_token,
            'expire_in': expire_in
        }

    async def get_sole(self):
        request_headers = self.request.headers
        version = request_headers.get('version', '')
        device = request_headers.get('device', '')
        system = request_headers.get('system', '')
        scene = request_headers.get('scene', '')
        ip = get_client_ip(self.request)
        return md5_upper(
            ','.join([version, device, system, scene, ip])
        )

    async def check_token(self):
        auth_header_value = self.request.headers.get('Authorization', '')
        if not auth_header_value:
            raise_code(self.request, 990101, status_code=401)

        parts = auth_header_value.split()
        if parts[0].lower() != "bearer" or len(parts) != 2:
            raise_code(self.request, 990102, status_code=401)

        token = parts[1]
        payload = await self.decode_jwt(token)
        request_sole = self.get_sole()

        token_sole = payload.get('sole')
        white_ip_list = getattr(self.request.app.ctx.config, "auth_white_ip_list", [])
        if token_sole and request_sole not in white_ip_list:
            if token_sole != request_sole:
                raise_code(self.request, 990103, status_code=401)
        return payload


def token_required(func):
    @wraps(func)
    async def decorated_function(request, *args, **kwargs):
        auth = Auth(request)
        payload = await auth.check_token()
        request.ctx.g = payload
        return await func(request, *args, **kwargs)

    return decorated_function
