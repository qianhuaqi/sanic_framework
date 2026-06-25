#!/usr/bin/env python
# -*- coding: utf-8 -*-
# app/middleware/crypt_des.py
import base64
import json
import urllib.parse

from Crypto.Cipher import DES
from Crypto.Util.Padding import pad, unpad
from sanic.request import Request

from framework.exception import APIException
# 处理前后端交互加解密

# 加密
def encrypt_data(request: Request, plain_text, key=None):
    if not isinstance(plain_text, str):
        plain_text = json.dumps(plain_text)
    if not key:
        secret = request.app.config.CRYPT['response_secret']
        key = f"{secret}{request.app.config.APP}{secret}"
    if not isinstance(key, bytes):
        key = bytes(key[:8], 'utf-8')  # DES 需要 8 字节的密钥
    cipher = DES.new(key, DES.MODE_CBC)
    iv = cipher.iv
    padded_data = pad(plain_text.encode('utf-8'), DES.block_size)  # 对明文进行填充
    encrypted_data = cipher.encrypt(padded_data)
    return base64.b64encode(iv + encrypted_data).decode('utf-8')

# 解密
def decrypt_data(request: Request, encrypt_text, key=None):
    if not key:
        secret = request.app.config.CRYPT['response_secret']
        key = f"{secret}{request.app.config.APP}{secret}"
    if not isinstance(key, bytes):
        key = bytes(key[:8], 'utf-8')  # DES 需要 8 字节的密钥
    try:
        encrypted_data = base64.b64decode(encrypt_text)
    except:
        i18n = request.app.ctx.i18n
        code = 991102
        msg = i18n['Param'].get(str(code))
        raise APIException(code=code, msg=msg, status_code=400)
    iv = encrypted_data[:DES.block_size]
    encrypted_data = encrypted_data[DES.block_size:]
    cipher = DES.new(key, DES.MODE_CBC, iv)
    decrypted_data = unpad(cipher.decrypt(encrypted_data), DES.block_size)
    return urllib.parse.unquote(decrypted_data.decode('utf-8'))
