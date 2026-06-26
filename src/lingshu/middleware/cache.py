#!/usr/bin/env python
# -*- coding: utf-8 -*-
# app/middleware/cache.py

import hashlib
import json
import os
import time
import urllib.parse

from filelock import FileLock
from sanic.request import Request

from lingshu.middleware.params import I


class Cache:
    def __init__(self, config):
        self.config = config
        self.cache_dir, self.cache_expire, self.cache_enabled, self.allow_status = self.get_config()

    def get_config(self):
        cache_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            self.config.get('dir', 'runtime')
        )
        cache_expire = self.config.get('expire', 3600)  # Default 1 hour
        cache_enabled = True if str(self.config.get('enabled', False)).lower() == 'true' else False
        try:
            allow_status = json.loads(str(self.config.get('allow_status', [200, 201])))
        except KeyError:
            allow_status = [200, 201]
        return cache_dir, cache_expire, cache_enabled, allow_status

    def generate_cache_key(self, request: Request) -> str:
        url = urllib.parse.quote(request.url, safe='')
        params = urllib.parse.urlencode(I(request), doseq=True)
        key = hashlib.md5(f"{url}{params}".encode('utf-8')).hexdigest()
        return key

    def get_cache_file_path(self, cache_key: str, request: Request) -> str:
        url_path = urllib.parse.quote(request.path, safe='')
        cache_file_dir = os.path.join(self.cache_dir, url_path)
        os.makedirs(cache_file_dir, exist_ok=True)
        return os.path.join(cache_file_dir, f"{cache_key}.log")

    def is_cache_valid(self, cache_file_path: str) -> bool:
        if not os.path.exists(cache_file_path):
            return False
        file_mtime = os.path.getmtime(cache_file_path)
        return (time.time() - file_mtime) < self.cache_expire

    def delete_cache_file(self, cache_file_path: str):
        if os.path.exists(cache_file_path):
            os.remove(cache_file_path)
        return True

    async def save_to_cache(self, request: Request, response):
        if not self.cache_enabled:
            return None
        cache_key = self.generate_cache_key(request)
        cache_file_path = self.get_cache_file_path(cache_key, request)

        lock_file_path = cache_file_path + '.lock'
        lock = FileLock(lock_file_path)

        with lock:
            # Remove existing cache file if it exists
            self.delete_cache_file(cache_file_path)
            if response.status in self.allow_status:
                cache_data = {
                    "headers": dict(request.headers),
                    "params": urllib.parse.urlencode(request.args, doseq=True),
                    "response_body": response.body.decode('utf-8') if response.body else "",
                    "status": response.status,
                    "request_id": request.ctx.request_id
                }
                with open(cache_file_path, 'w') as cache_file:
                    json.dump(cache_data, cache_file)

    def load_from_cache(self, cache_file_path: str) -> dict:
        with open(cache_file_path, 'r') as cache_file:
            return json.load(cache_file)

    async def clean_expired_cache(self):
        for root, dirs, files in os.walk(self.cache_dir):
            for file in files:
                if file.endswith('.log'):
                    file_path = os.path.join(root, file)
                    if not self.is_cache_valid(file_path):
                        # Remove existing cache file if it exists
                        self.delete_cache_file(file_path)

    async def cache_middleware(self, request: Request):
        if not self.cache_enabled:
            return None

        cache_key = self.generate_cache_key(request)
        cache_file_path = self.get_cache_file_path(cache_key, request)

        lock_file_path = cache_file_path + '.lock'
        lock = FileLock(lock_file_path)
        with lock:
            if self.is_cache_valid(cache_file_path):
                cache_data = self.load_from_cache(cache_file_path)
                return {
                    "data": json.loads(cache_data["response_body"]),
                    "status": int(cache_data["status"])
                }
            else:
                # Remove existing cache file if it exists
                self.delete_cache_file(cache_file_path)

        return None
