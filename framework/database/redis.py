#!/usr/bin/env python
# -*- coding: utf-8 -*-
# app/database/redis_manager.py
import asyncio
import time


class RedisManager:
    def __init__(self, config):
        self.config = config
        self.sentinel = None
        self.redis = None
        self.master = None
        self.slave = None
        self.lock = asyncio.Lock()
        self.idle_timeout = self.config.get('idle_timeout', 300)  # Default to 5 minutes
        self.last_used = time.time()

        # 根据集群开关验证是否开启集群
        if self.config.get('sentinel_enabled'):
            self.sentinel = True

    @staticmethod
    def _load_redis_classes():
        from redis.asyncio import Redis
        from redis.asyncio.sentinel import Sentinel

        return Redis, Sentinel

    async def connect(self):
        async with self.lock:
            if self.sentinel:
                # Sentinel Mode
                _, sentinel_cls = self._load_redis_classes()
                if self.sentinel is True:
                    self.sentinel = sentinel_cls(
                        self.config['sentinels'],
                        password=self.config['password'],
                        socket_timeout=1.0
                    )
                if not self.master:
                    self.master = self.sentinel.master_for(self.config['master_name'], db=self.config['db'])
                if not self.slave:
                    self.slave = self.sentinel.slave_for(self.config['master_name'], db=self.config['db'])
            else:
                # Direct Redis Mode
                if not self.redis:
                    redis_cls, _ = self._load_redis_classes()
                    self.redis = redis_cls(
                        host=self.config['host'],
                        port=self.config['port'],
                        password=self.config['password'],
                        db=self.config['db']
                    )
            self.last_used = time.time()

    async def close(self):
        async with self.lock:
            if self.master:
                await self.master.connection_pool.disconnect()
                self.master = None
            if self.slave:
                await self.slave.connection_pool.disconnect()
                self.slave = None
            if self.redis:
                await self.redis.connection_pool.disconnect()
                self.redis = None

    async def ensure_connection(self):
        if self.sentinel:
            # Sentinel Mode
            if not self.master or not self.slave:
                await self.connect()
            elif time.time() - self.last_used > self.idle_timeout:
                await self.close()
                await self.connect()
        else:
            # Direct Redis Mode
            if not self.redis:
                await self.connect()
            elif time.time() - self.last_used > self.idle_timeout:
                await self.close()
                await self.connect()
        self.last_used = time.time()

    async def repair_key(self, cache_key):
        return "{}:{}".format(self.config['prefix'], cache_key)

    async def get(self, cache_key):
        await self.ensure_connection()
        key = await self.repair_key(cache_key)
        if self.slave:
            return await self.slave.get(key)
        return await self.redis.get(key)

    async def mget(self, *cache_keys):
        await self.ensure_connection()
        keys = [await self.repair_key(key) for key in cache_keys]
        if self.slave:
            return await self.slave.mget(*keys)
        return await self.redis.mget(*keys)

    async def set(self, cache_key, value, expire=None):
        await self.ensure_connection()
        key = await self.repair_key(cache_key)
        if self.master:
            await self.master.set(key, value)
        else:
            await self.redis.set(key, value)
        if expire:
            if self.master:
                await self.master.expire(key, expire)
            else:
                await self.redis.expire(key, expire)

    async def mset(self, data_dict, expire=None):
        await self.ensure_connection()
        data = {await self.repair_key(key): value for key, value in data_dict.items()}
        if self.redis:
            await self.redis.mset(data)
        else:
            await self.master.mset(data)
        if expire:
            for key in data.keys():
                if self.master:
                    await self.master.expire(key, expire)
                else:
                    await self.redis.expire(key, expire)

    async def delete(self, cache_key):
        await self.ensure_connection()
        key = await self.repair_key(cache_key)
        if self.master:
            await self.master.delete(key)
        else:
            await self.redis.delete(key)

    async def hget(self, cache_key, field):
        await self.ensure_connection()
        key = await self.repair_key(cache_key)
        if self.slave:
            return await self.slave.hget(key, field)
        return await self.redis.hget(key, field)

    async def hset(self, cache_key, field, value):
        await self.ensure_connection()
        key = await self.repair_key(cache_key)
        if self.master:
            await self.master.hset(key, field, value)
        else:
            await self.redis.hset(key, field, value)

    async def hmget(self, cache_key, *fields):
        await self.ensure_connection()
        key = await self.repair_key(cache_key)
        if self.slave:
            return await self.slave.hmget(key, *fields)
        else:
            return await self.redis.hmget(key, *fields)

    async def hmset(self, cache_key, data_dict):
        await self.ensure_connection()
        key = await self.repair_key(cache_key)
        if self.master:
            await self.master.hset(key, mapping=data_dict)
        else:
            await self.redis.hset(key, mapping=data_dict)

    async def hgetall(self, cache_key):
        await self.ensure_connection()
        key = await self.repair_key(cache_key)
        if self.slave:
            return await self.slave.hgetall(key)
        return await self.redis.hgetall(key)

    async def hdel(self, cache_key, *fields):
        await self.ensure_connection()
        key = await self.repair_key(cache_key)
        if self.master:
            await self.master.hdel(key, *fields)
        else:
            await self.redis.hdel(key, *fields)

    async def lrange(self, cache_key, start, end):
        await self.ensure_connection()
        key = await self.repair_key(cache_key)
        if self.slave:
            return await self.slave.lrange(key, start, end)
        return await self.redis.lrange(key, start, end)

    async def llen(self, cache_key):
        await self.ensure_connection()
        key = await self.repair_key(cache_key)
        if self.slave:
            return await self.slave.llen(key)
        return await self.redis.llen(key)

    async def sadd(self, cache_key, *values):
        await self.ensure_connection()
        key = await self.repair_key(cache_key)
        if self.master:
            return await self.master.sadd(key, *values)
        return await self.redis.sadd(key, *values)

    async def sismember(self, cache_key, value):
        await self.ensure_connection()
        key = await self.repair_key(cache_key)
        if self.slave:
            return await self.slave.sismember(key, value)
        return await self.redis.sismember(key, value)

    async def smembers(self, cache_key):
        await self.ensure_connection()
        key = await self.repair_key(cache_key)
        if self.slave:
            return await self.slave.smembers(key)
        return await self.redis.smembers(key)

    async def srem(self, cache_key, *values):
        await self.ensure_connection()
        key = await self.repair_key(cache_key)
        if self.master:
            return await self.master.srem(key, *values)
        return await self.redis.srem(key, *values)

    async def zadd(self, cache_key, *score_member_pairs):
        await self.ensure_connection()
        key = await self.repair_key(cache_key)
        if self.master:
            return await self.master.zadd(key, *score_member_pairs)
        return await self.redis.zadd(key, *score_member_pairs)

    async def zcard(self, cache_key):
        await self.ensure_connection()
        key = await self.repair_key(cache_key)
        if self.slave:
            return await self.slave.zcard(key)
        return await self.redis.zcard(key)

    async def publish(self, channel, message):
        await self.ensure_connection()
        if self.master:
            return await self.master.publish(channel, message)
        return await self.redis.publish(channel, message)

    async def pubsub(self, channels):
        await self.ensure_connection()
        if self.master:
            return await self.master.subscribe(*channels)
        return await self.redis.subscribe(*channels)

    async def setex(self, cache_key, seconds, value):
        await self.ensure_connection()
        key = await self.repair_key(cache_key)
        if self.master:
            return await self.master.setex(key, seconds, value)
        return await self.redis.setex(key, seconds, value)

    async def ttl(self, cache_key):
        await self.ensure_connection()
        key = await self.repair_key(cache_key)
        if self.slave:
            return await self.slave.ttl(key)
        return await self.redis.ttl(key)

    async def exists(self, cache_key):
        await self.ensure_connection()
        key = await self.repair_key(cache_key)
        if self.slave:
            return await self.slave.exists(key)
        return await self.redis.exists(key)

    async def expire(self, cache_key, seconds):
        await self.ensure_connection()
        key = await self.repair_key(cache_key)
        if self.master:
            return await self.master.expire(key, seconds)
        return await self.redis.expire(key, seconds)

    async def incr(self, cache_key, amount=1):
        await self.ensure_connection()
        key = await self.repair_key(cache_key)
        if self.master:
            return await self.master.incrby(key, amount)
        return await self.redis.incrby(key, amount)

    async def decr(self, cache_key, amount=1):
        await self.ensure_connection()
        key = await self.repair_key(cache_key)
        if self.master:
            return await self.master.decrby(key, amount)
        return await self.redis.decrby(key, amount)

    async def lpush(self, cache_key, *values):
        await self.ensure_connection()
        key = await self.repair_key(cache_key)
        if self.master:
            return await self.master.lpush(key, *values)
        return await self.redis.lpush(key, *values)

    async def lpop(self, cache_key):
        await self.ensure_connection()
        key = await self.repair_key(cache_key)
        if self.master:
            return await self.master.lpop(key)
        return await self.redis.lpop(key)

    async def rpush(self, cache_key, *values):
        await self.ensure_connection()
        key = await self.repair_key(cache_key)
        if self.master:
            return await self.master.rpush(key, *values)
        return await self.redis.rpush(key, *values)

    async def rpop(self, cache_key):
        await self.ensure_connection()
        key = await self.repair_key(cache_key)
        if self.master:
            return await self.master.rpop(key)
        return await self.redis.rpop(key)
