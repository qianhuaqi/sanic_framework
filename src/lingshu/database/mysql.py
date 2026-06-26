#!/usr/bin/env python
# -*- coding: utf-8 -*-
# app/database/mysql.py

import time

from lingshu.database.dependencies import require_database_package
from lingshu.helper import write_verify_log
from lingshu import logger


class MySQLDatabase:
    def __init__(self, config):
        self.config = config
        self.master_pool = None
        self.read_pools = []
        self._read_index = 0

    def _normalize_endpoint(self, endpoint):
        return {
            "host": endpoint.get("host", self.config.get("host", "localhost")),
            "port": int(endpoint.get("port", self.config.get("port", 3306))),
            "user": endpoint.get("user", self.config.get("user", "")),
            "password": endpoint.get("password", self.config.get("password", "")),
            "database": endpoint.get("database", self.config.get("database", "")),
        }

    def _pool_kwargs(self, endpoint):
        endpoint = self._normalize_endpoint(endpoint)
        return {
            "host": endpoint["host"],
            "port": endpoint["port"],
            "user": endpoint["user"],
            "password": endpoint["password"],
            "db": endpoint["database"],
            "autocommit": True,
            "minsize": 1,
            "maxsize": int(self.config.get("pool_size", 5)),
            "pool_recycle": int(self.config.get("pool_recycle", 3600)),
        }

    @staticmethod
    def _load_aiomysql():
        aiomysql = require_database_package("aiomysql", "aiomysql", "mysql")
        cursors = require_database_package("aiomysql.cursors", "aiomysql", "mysql")
        return aiomysql, cursors.DictCursor

    async def connect(self):
        aiomysql, _ = self._load_aiomysql()
        master = self.config.get("master") or self.config
        self.master_pool = await aiomysql.create_pool(**self._pool_kwargs(master))
        self.read_pools = []
        for slave in self.config.get("slaves", []):
            pool = await aiomysql.create_pool(**self._pool_kwargs(slave))
            self.read_pools.append(pool)

    async def disconnect(self):
        pools = [pool for pool in [self.master_pool, *self.read_pools] if pool]
        for pool in pools:
            pool.close()
            await pool.wait_closed()
        self.master_pool = None
        self.read_pools = []
        self._read_index = 0

    def _read_pool(self):
        if self.read_pools:
            pool = self.read_pools[self._read_index % len(self.read_pools)]
            self._read_index += 1
            return pool
        return self.master_pool

    def _write_pool(self):
        return self.master_pool or self._read_pool()

    async def _query(self, pool, query, args=None, fetch="all", request=None):
        if not pool:
            raise RuntimeError("MySQL database is not connected")
        _, dict_cursor = self._load_aiomysql()
        async with pool.acquire() as conn:
            async with conn.cursor(dict_cursor) as cursor:
                await cursor.execute(query, args or ())
                if fetch == "one":
                    result = await cursor.fetchone()
                    payload = dict(result) if result else None
                elif fetch == "all":
                    result = await cursor.fetchall()
                    payload = [dict(row) for row in result] if result else []
                elif fetch == "insert":
                    payload = cursor.lastrowid
                elif fetch == "many":
                    payload = cursor.rowcount
                else:
                    payload = None

                if request is not None:
                    verify_data = dict(
                        time=int(time.time()),
                        query=query,
                        args=args or (),
                        result=payload,
                        hint=request.ctx.request_id,
                    )
                    write_verify_log(request, **verify_data)
                    logger.info("query:{query} args:{args} result:{result}".format(**verify_data))
                return payload

    async def execute(self, query, args=None, request=None):
        return await self._query(self._read_pool(), query, args=args, fetch="all", request=request)

    async def execute_one(self, query, args=None, request=None):
        return await self._query(self._read_pool(), query, args=args, fetch="one", request=request)

    async def execute_master(self, query, args=None, request=None):
        return await self._query(self.master_pool or self._read_pool(), query, args=args, fetch="all", request=request)

    async def execute_one_master(self, query, args=None, request=None):
        return await self._query(self.master_pool or self._read_pool(), query, args=args, fetch="one", request=request)

    async def execute_insert(self, query, args=None, request=None):
        return await self._query(self._write_pool(), query, args=args, fetch="insert", request=request)

    async def execute_update(self, query, args=None, request=None):
        return await self._query(self._write_pool(), query, args=args, fetch="many", request=request)

    async def execute_many(self, query, args_list, request=None):
        pool = self._write_pool()
        if not pool:
            raise RuntimeError("MySQL database is not connected")
        _, dict_cursor = self._load_aiomysql()
        async with pool.acquire() as conn:
            async with conn.cursor(dict_cursor) as cursor:
                await cursor.executemany(query, args_list)
                payload = cursor.rowcount
                if request is not None:
                    verify_data = dict(
                        time=int(time.time()),
                        query=query,
                        args=args_list,
                        result=payload,
                        hint=request.ctx.request_id,
                    )
                    write_verify_log(request, **verify_data)
                    logger.info("query:{query} args:{args} result:{result}".format(**verify_data))
                return payload
