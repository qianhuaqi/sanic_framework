from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from lingshu.middleware.json import CustomJSONEncoder


@dataclass(frozen=True)
class QueryPlan:
    sql: str
    args: list[Any]


class BaseModel:
    table_name: str = ""
    primary_key: str = "id"
    fillable: tuple[str, ...] = ()
    readonly_fields: tuple[str, ...] = ("id",)
    default_order_by: tuple[str, ...] = ()
    read_source: str = "auto"
    cache_enabled: bool = False
    cache_ttl: int = 300
    cache_namespace: str = "model"

    @classmethod
    def _require_table(cls):
        if not cls.table_name:
            raise ValueError(f"{cls.__name__} must define table_name")

    @classmethod
    def _db(cls, db):
        if db is None:
            raise ValueError("Database instance is required")
        return db

    @classmethod
    def _resolve_read_source(cls, read_from=None):
        return read_from or cls.read_source or "auto"

    @classmethod
    def _execute_read(cls, db, query, args=None, request=None, read_from=None, one=False):
        db = cls._db(db)
        source = cls._resolve_read_source(read_from)
        if source == "master":
            method = getattr(db, "execute_one_master" if one else "execute_master", None)
            if method is not None:
                return method(query, args=args, request=request)
        method = getattr(db, "execute_one" if one else "execute", None)
        if method is None:
            raise AttributeError("Database instance does not support read execution")
        return method(query, args=args, request=request)

    @classmethod
    def _execute_write(cls, db, query, args=None, request=None):
        db = cls._db(db)
        method = getattr(db, "execute_update", None)
        if method is None:
            method = getattr(db, "execute", None)
        if method is None:
            raise AttributeError("Database instance does not support write execution")
        return method(query, args=args, request=request)

    @classmethod
    def _normalize_redis(cls, redis=None, request=None):
        if redis is not None:
            return redis
        if request is None:
            return None
        app = getattr(request, "app", None)
        if app is None:
            return None
        ctx = getattr(app, "ctx", None)
        if ctx is None:
            return None
        return getattr(ctx, "redis", None)

    @classmethod
    def _is_full_row_request(cls, columns) -> bool:
        return columns is None or columns == "*" or columns == ("*",)

    @classmethod
    def _cache_key(cls, pk) -> str:
        cls._require_table()
        return f"{cls.cache_namespace}:{cls.table_name}:{pk}"

    @staticmethod
    def _cache_dump(value) -> str:
        return json.dumps(value, cls=CustomJSONEncoder, ensure_ascii=False)

    @staticmethod
    def _cache_load(value):
        if value is None:
            return None
        if isinstance(value, (bytes, bytearray)):
            value = value.decode()
        if isinstance(value, str):
            return json.loads(value)
        return value

    @classmethod
    async def cache_get(cls, redis, pk):
        if redis is None:
            return None
        cached = await redis.get(cls._cache_key(pk))
        return cls._cache_load(cached)

    @classmethod
    async def cache_set(cls, redis, pk, value, ttl: int | None = None):
        if redis is None:
            return None
        expire = cls.cache_ttl if ttl is None else ttl
        payload = cls._cache_dump(value)
        if expire:
            return await redis.setex(cls._cache_key(pk), expire, payload)
        return await redis.set(cls._cache_key(pk), payload)

    @classmethod
    async def cache_delete(cls, redis, pk):
        if redis is None:
            return None
        return await redis.delete(cls._cache_key(pk))

    @classmethod
    def _filter_columns(cls, data: dict[str, Any]) -> dict[str, Any]:
        if not data:
            return {}
        if not cls.fillable:
            return {key: value for key, value in data.items() if key not in cls.readonly_fields}
        return {
            key: value
            for key, value in data.items()
            if key in cls.fillable and key not in cls.readonly_fields
        }

    @classmethod
    def _normalize_columns(cls, columns):
        if columns is None:
            return "*"
        if isinstance(columns, str):
            return columns
        return ", ".join(columns)

    @classmethod
    def _normalize_order_by(cls, order_by):
        items = order_by or cls.default_order_by
        if not items:
            return ""
        if isinstance(items, str):
            items = [items]
        return " ORDER BY " + ", ".join(items)

    @classmethod
    def _build_conditions(cls, filters: dict[str, Any] | None):
        if not filters:
            return "", []
        clauses = []
        args: list[Any] = []
        operator_map = {
            "eq": "=",
            "ne": "!=",
            "gt": ">",
            "gte": ">=",
            "lt": "<",
            "lte": "<=",
            "like": "LIKE",
        }
        for key, value in filters.items():
            if "__" in key:
                field, op_key = key.split("__", 1)
                operator = operator_map.get(op_key, "=")
            else:
                field, operator = key, "="

            if value is None:
                clauses.append(f"`{field}` IS NULL")
                continue
            if operator == "LIKE":
                clauses.append(f"`{field}` LIKE %s")
                args.append(value)
                continue
            if isinstance(value, (list, tuple, set, frozenset)):
                values = list(value)
                if not values:
                    clauses.append("1 = 0")
                    continue
                placeholders = ", ".join(["%s"] * len(values))
                clauses.append(f"`{field}` IN ({placeholders})")
                args.extend(values)
                continue
            clauses.append(f"`{field}` {operator} %s")
            args.append(value)
        if not clauses:
            return "", args
        return " WHERE " + " AND ".join(clauses), args

    @classmethod
    def _build_select_plan(
        cls,
        columns=None,
        filters: dict[str, Any] | None = None,
        order_by=None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> QueryPlan:
        cls._require_table()
        sql = f"SELECT {cls._normalize_columns(columns)} FROM `{cls.table_name}`"
        where_sql, args = cls._build_conditions(filters)
        sql += where_sql
        sql += cls._normalize_order_by(order_by)
        if limit is not None:
            sql += " LIMIT %s"
            args.append(limit)
            if offset is not None:
                sql += " OFFSET %s"
                args.append(offset)
        return QueryPlan(sql=sql, args=args)

    @classmethod
    async def raw(cls, db, query, args=None, request=None):
        return await cls._db(db).execute(query, args=args, request=request)

    @classmethod
    async def find_by_pk(
        cls,
        db,
        pk,
        columns=None,
        request=None,
        redis=None,
        use_cache: bool | None = None,
        cache_ttl: int | None = None,
        read_from=None,
    ):
        cls._require_table()
        cache_allowed = cls.cache_enabled if use_cache is None else use_cache
        redis_client = cls._normalize_redis(redis=redis, request=request)
        if cache_allowed and redis_client is not None and cls._is_full_row_request(columns):
            cached = await cls.cache_get(redis_client, pk)
            if cached is not None:
                return cached
        plan = cls._build_select_plan(columns=columns, filters={cls.primary_key: pk}, limit=1)
        row = await cls._execute_read(db, plan.sql, plan.args, request=request, read_from=read_from, one=True)
        if row is not None and cache_allowed and redis_client is not None and cls._is_full_row_request(columns):
            await cls.cache_set(redis_client, pk, row, ttl=cache_ttl)
        return row

    @classmethod
    async def find_one(
        cls,
        db,
        filters: dict[str, Any] | None = None,
        columns=None,
        order_by=None,
        request=None,
        read_from=None,
    ):
        plan = cls._build_select_plan(columns=columns, filters=filters, order_by=order_by, limit=1)
        return await cls._execute_read(db, plan.sql, plan.args, request=request, read_from=read_from, one=True)

    @classmethod
    async def find_all(
        cls,
        db,
        filters: dict[str, Any] | None = None,
        columns=None,
        order_by=None,
        limit: int | None = None,
        offset: int | None = None,
        request=None,
        read_from=None,
    ):
        plan = cls._build_select_plan(
            columns=columns,
            filters=filters,
            order_by=order_by,
            limit=limit,
            offset=offset,
        )
        return await cls._execute_read(db, plan.sql, plan.args, request=request, read_from=read_from)

    @classmethod
    async def count(cls, db, filters: dict[str, Any] | None = None, request=None, read_from=None) -> int:
        cls._require_table()
        sql = f"SELECT COUNT(*) AS count FROM `{cls.table_name}`"
        where_sql, args = cls._build_conditions(filters)
        sql += where_sql
        result = await cls._execute_read(db, sql, args, request=request, read_from=read_from, one=True)
        if not result:
            return 0
        return int(result.get("count", 0))

    @classmethod
    async def exists(cls, db, filters: dict[str, Any] | None = None, request=None) -> bool:
        return await cls.count(db, filters=filters, request=request) > 0

    @classmethod
    async def insert(cls, db, data: dict[str, Any], request=None):
        cls._require_table()
        payload = cls._filter_columns(dict(data))
        if not payload:
            raise ValueError("No writable columns supplied")
        columns = list(payload.keys())
        placeholders = ", ".join(["%s"] * len(columns))
        sql = f"INSERT INTO `{cls.table_name}` ({', '.join(f'`{column}`' for column in columns)}) VALUES ({placeholders})"
        return await cls._db(db).execute_insert(sql, list(payload.values()), request=request)

    @classmethod
    async def insert_many(cls, db, rows: list[dict[str, Any]], request=None):
        cls._require_table()
        if not rows:
            return 0
        cleaned_rows = [cls._filter_columns(dict(row)) for row in rows]
        columns = list(cleaned_rows[0].keys())
        if not columns:
            raise ValueError("No writable columns supplied")
        values = [tuple(row[column] for column in columns) for row in cleaned_rows]
        sql = f"INSERT INTO `{cls.table_name}` ({', '.join(f'`{column}`' for column in columns)}) VALUES ({', '.join(['%s'] * len(columns))})"
        return await cls._db(db).execute_many(sql, values, request=request)

    @classmethod
    async def update(
        cls,
        db,
        data: dict[str, Any],
        filters: dict[str, Any] | None = None,
        pk=None,
        request=None,
        redis=None,
    ):
        cls._require_table()
        payload = cls._filter_columns(dict(data))
        if not payload:
            raise ValueError("No writable columns supplied")
        clauses = ", ".join(f"`{column}` = %s" for column in payload.keys())
        sql = f"UPDATE `{cls.table_name}` SET {clauses}"
        where_filters = filters or ({cls.primary_key: pk} if pk is not None else None)
        where_sql, args = cls._build_conditions(where_filters)
        if not where_sql:
            raise ValueError("Update requires filters or pk")
        result = await cls._execute_write(db, sql + where_sql, list(payload.values()) + args, request=request)
        cache_pk = pk
        if cache_pk is None and filters and len(filters) == 1 and cls.primary_key in filters:
            cache_pk = filters[cls.primary_key]
        if cache_pk is not None:
            await cls.cache_delete(cls._normalize_redis(redis=redis, request=request), cache_pk)
        return result

    @classmethod
    async def delete(cls, db, filters: dict[str, Any] | None = None, pk=None, request=None, redis=None):
        cls._require_table()
        where_filters = filters or ({cls.primary_key: pk} if pk is not None else None)
        where_sql, args = cls._build_conditions(where_filters)
        if not where_sql:
            raise ValueError("Delete requires filters or pk")
        sql = f"DELETE FROM `{cls.table_name}`{where_sql}"
        result = await cls._execute_write(db, sql, args, request=request)
        cache_pk = pk
        if cache_pk is None and filters and len(filters) == 1 and cls.primary_key in filters:
            cache_pk = filters[cls.primary_key]
        if cache_pk is not None:
            await cls.cache_delete(cls._normalize_redis(redis=redis, request=request), cache_pk)
        return result

    @classmethod
    async def save(cls, db, data: dict[str, Any], request=None, redis=None, use_cache: bool | None = None, cache_ttl: int | None = None):
        payload = dict(data)
        pk_value = payload.get(cls.primary_key)
        if pk_value is None:
            return await cls.insert(db, payload, request=request)
        existing = await cls.find_by_pk(
            db,
            pk_value,
            request=request,
            redis=redis,
            use_cache=use_cache,
            cache_ttl=cache_ttl,
        )
        if existing:
            await cls.update(db, payload, pk=pk_value, request=request, redis=redis)
            return pk_value
        return await cls.insert(db, payload, request=request)

    @classmethod
    async def paginate(
        cls,
        db,
        page: int = 1,
        per_page: int = 20,
        filters: dict[str, Any] | None = None,
        columns=None,
        order_by=None,
        request=None,
    ):
        page = max(int(page), 1)
        per_page = max(int(per_page), 1)
        offset = (page - 1) * per_page
        items = await cls.find_all(
            db,
            filters=filters,
            columns=columns,
            order_by=order_by,
            limit=per_page,
            offset=offset,
            request=request,
        )
        total = await cls.count(db, filters=filters, request=request)
        return {
            "items": items,
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page if total else 0,
        }
