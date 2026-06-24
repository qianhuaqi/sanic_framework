#!/usr/bin/env python
# -*- coding: utf-8 -*-
# app/middleware/utils.py
import hashlib
import os
import socket
import uuid

from sanic.request import Request
from sanic.response import json

from framework.middleware.crypt_des import encrypt_data


def json_response(request: Request, data=None, errcode=0, errmsg="ok", **kwargs):
    if data:
        allow_encryption = True if str(request.app.config.CRYPT.get('enabled', False)).lower() == 'true' else False
        if allow_encryption:
            # 加密数据
            secret = request.app.config.CRYPT['response_secret']
            key = f"{secret}{request.app.config.APP}{secret}"
            encrypted_data = encrypt_data(request, data, key)
        else:
            encrypted_data = data
    else:
        encrypted_data = {}

    body = {
        'errcode': errcode,
        'errmsg': errmsg,
        'data': encrypted_data
    }
    return json(body, **kwargs)


# 处理证件号
def filter_zjh(zjh):
    origin = ['(', ')', 'x']
    target = ['（', '）', 'X']
    for i in range(len(origin)):
        zjh = zjh.replace(origin[i], target[i])
    return zjh


# 生成md5
def md5(keyword=''):
    m = hashlib.md5()
    m.update(keyword.encode("utf8"))
    return m.hexdigest()


# 生成md5大写
def md5_upper(keyword=''):
    m = hashlib.md5()
    m.update(keyword.encode("utf8"))
    return m.hexdigest().upper()


def get_nonce_str():
    return str(uuid.uuid4()).replace('-', '')


def get_server_ip():
    # 获取服务器 IP 地址
    return socket.gethostbyname(socket.gethostname())


def get_ip():
    """获取ip"""
    ip = 'ip'
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass
    return ip


def get_client_ip(request: Request):
    x_forwarded_ip = ''
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for and ',' in x_forwarded_for:
        x_forwarded_list = x_forwarded_for.split(',')
        if len(x_forwarded_list) == 2:
            x_forwarded_ip = x_forwarded_list[0]
        elif len(x_forwarded_list) > 2:
            x_forwarded_ip = x_forwarded_list[1]
    ip = x_forwarded_ip or request.headers.get('X-Real-IP') or request.remote_addr
    return ip


def exists_path(path):
    folder = os.path.exists(path)
    if not folder:
        os.makedirs(path, mode=0o777)
    return True
