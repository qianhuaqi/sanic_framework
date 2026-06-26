from __future__ import annotations

import json
import time
from typing import Any

from lingshu.middleware.json import CustomJSONEncoder
from lingshu.model.base import BaseModel
from lingshu import db, request
from lingshu.system.context import get_current_app
from lingshu.system.errors import NoRequestContextError


def return_fields(row, fields=None):
    if row is None or fields is None:
        return row
    if isinstance(fields, str):
        fields = [field.strip() for field in fields.split(",") if field.strip()]
    if not isinstance(row, dict):
        return row
    return {field: row.get(field) for field in fields}


def format_where(filters: dict[str, Any] | None):
    return BaseModel._build_conditions(filters)


class Model(BaseModel):
    """
    Compatibility layer that preserves the old instance-based model style.

    Subclasses can keep using:
      - table / table_name
      - pk / primary_key
      - read_source = "master" | "auto"
      - cache_enabled / cache_ttl
    """

    read_source = "auto"

    def __init__(self):
        self.table = getattr(self, "table_name", "") or getattr(self.__class__, "table", "")
        self.pk = getattr(self, "primary_key", "id") or getattr(self.__class__, "pk", "id")

    @property
    def request(self):
        get_current_app()
        try:
            return request.raw
        except NoRequestContextError:
            return None

    @property
    def db(self):
        return db.mysql

    @property
    def redis(self):
        return db.optional("redis")

    def _read_mode(self, use_master=None):
        if use_master is True:
            return "master"
        if use_master is False:
            return "auto"
        return self.read_source or "auto"

    def _cache_key_for(self, data_id):
        return f"{self.cache_namespace}:{self.table}:{data_id}"

    async def _cache_get(self, data_id):
        if not self.cache_enabled or self.redis is None:
            return None
        cached = await self.redis.get(self._cache_key_for(data_id))
        if cached is None:
            return None
        if isinstance(cached, (bytes, bytearray)):
            cached = cached.decode()
        if isinstance(cached, str):
            return json.loads(cached)
        return cached

    async def _cache_set(self, data_id, value):
        if not self.cache_enabled or self.redis is None:
            return None
        payload = json.dumps(value, cls=CustomJSONEncoder, ensure_ascii=False)
        if self.cache_ttl:
            return await self.redis.setex(self._cache_key_for(data_id), self.cache_ttl, payload)
        return await self.redis.set(self._cache_key_for(data_id), payload)

    async def _cache_delete(self, data_id):
        if not self.cache_enabled or self.redis is None:
            return None
        return await self.redis.delete(self._cache_key_for(data_id))

    def _read_db_kwargs(self, read_mode):
        if read_mode == "master":
            return {"read_from": "master"}
        return {"read_from": "auto"}

    def _base_call(self, name, *args, **kwargs):
        method = getattr(BaseModel, name)
        return method.__func__(type(self), *args, **kwargs)

    async def get_one(self, data_id, fields=None, use_master=None, use_cache=True):
        read_mode = self._read_mode(use_master)
        cache_active = bool(use_cache and self.cache_enabled)
        model = type(self)
        if cache_active and fields is None:
            cached = await self._cache_get(data_id)
            if cached is not None:
                return return_fields(cached, fields)

        result = await self._base_call(
            "find_by_pk",
            self.db,
            data_id,
            request=self.request,
            redis=self.redis,
            use_cache=cache_active,
            read_from=read_mode,
        )
        return return_fields(result, fields)

    async def find(self, fields=None, use_master=None, use_cache=True, **kwargs):
        kwargs = self._apply_default_state(kwargs)
        where_clause, params = format_where(kwargs)
        query = f"SELECT * FROM `{self.table}`"
        if where_clause:
            query += f" WHERE {where_clause[7:]}"
        query += " LIMIT 1"
        read_mode = self._read_mode(use_master)
        executor = self.db.execute_one_master if read_mode == "master" and hasattr(self.db, "execute_one_master") else self.db.execute_one
        result = await executor(query, params, request=self.request)
        return return_fields(result, fields)

    async def get_all(self, fields=None, order_by=None, use_master=None, use_cache=False, **kwargs):
        kwargs = self._apply_default_state(kwargs)
        read_mode = self._read_mode(use_master)
        order_by = order_by or f"{self.pk} DESC"
        model = type(self)
        result = await self._base_call(
            "find_all",
            self.db,
            filters=kwargs,
            request=self.request,
            read_from=read_mode,
            order_by=order_by,
        )
        return [return_fields(item, fields) for item in result] if result else []

    async def find_all(self, fields=None, order_by=None, use_master=None, **kwargs):
        return await self.get_all(fields=fields, order_by=order_by, use_master=use_master, **kwargs)

    async def get_count(self, use_master=None, **kwargs):
        kwargs = self._apply_default_state(kwargs)
        read_mode = self._read_mode(use_master)
        return await self._base_call("count", self.db, filters=kwargs, request=self.request, read_from=read_mode)

    async def get_pagination(self, page=1, size=10, data_id=0, order_by=None, use_master=None, **kwargs):
        kwargs = self._apply_default_state(kwargs)
        if data_id > 0:
            kwargs[f"{self.pk}__gt"] = data_id
        order_by = order_by or f"{self.pk} DESC"
        read_mode = self._read_mode(use_master)
        page = max(int(page), 1)
        size = max(int(size), 1)
        model = type(self)
        total_count = await self._base_call("count", self.db, filters=kwargs, request=self.request, read_from=read_mode)
        if total_count == 0:
            return {"total_count": 0, "total_pages": 0, "page_size": size, "current_page": page, "data": []}
        results = await self._base_call(
            "find_all",
            self.db,
            filters=kwargs,
            request=self.request,
            read_from=read_mode,
            order_by=order_by,
            limit=size,
            offset=(page - 1) * size,
        )
        total_pages = (total_count + size - 1) // size
        return {
            "total_count": total_count,
            "total_pages": total_pages,
            "page_size": size,
            "current_page": page,
            "data": [return_fields(item, None) for item in results] if results else [],
        }

    def _apply_default_state(self, kwargs):
        if "data_state" not in kwargs:
            kwargs["data_state"] = 1
        return kwargs

    async def insert(self, **kwargs):
        now = int(time.time())
        kwargs["created_time"] = kwargs.get("created_time", now)
        kwargs["updated_time"] = kwargs.get("updated_time", now)
        if "data_state" not in kwargs:
            kwargs["data_state"] = 1
        return await self._base_call("insert", self.db, kwargs, request=self.request)

    async def update(self, data_id, **kwargs):
        kwargs["updated_time"] = int(time.time())
        result = await self._base_call("update", self.db, kwargs, pk=data_id, request=self.request, redis=self.redis)
        return result

    async def delete(self, data_id, physical=False):
        if physical:
            result = await self._base_call("delete", self.db, pk=data_id, request=self.request, redis=self.redis)
        else:
            result = await self.update(data_id, data_state=0)
        return result
