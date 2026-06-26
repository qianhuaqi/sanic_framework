#!/usr/bin/env python
# -*- coding: utf-8 -*-
# app/database/mongodb.py

from lingshu.database.dependencies import require_database_package


class MongoDB:
    def __init__(self, config):
        self.config = config
        self.client = None
        self.db = None

    @staticmethod
    def _load_motor():
        return require_database_package("motor.motor_asyncio", "motor", "mongo")

    async def connect(self):
        motor_asyncio = self._load_motor()
        if 'username' in self.config and 'password' in self.config:
            uri = (f"mongodb://{self.config['username']}:{self.config['password']}@{self.config['host']}:"
                   f"{self.config['port']}/{self.config['database']}?authSource=admin")
            self.client = motor_asyncio.AsyncIOMotorClient(uri)
        else:
            self.client = motor_asyncio.AsyncIOMotorClient(
                host=self.config['host'],
                port=self.config['port']
            )
        self.db = self.client[self.config['database']]

    async def disconnect(self):
        if self.client:
            self.client.close()

    def switch_db(self, database_name):
        """切换 MongoDB 数据库"""
        self.db = self.client[database_name]

    def get_collection(self, collection_name):
        return self.db.get_collection(collection_name)

    async def insert_one(self, collection_name, document):
        collection = self.get_collection(collection_name)
        result = await collection.insert_one(document)
        return result.inserted_id

    async def find_one(self, collection_name, query):
        collection = self.get_collection(collection_name)
        document = await collection.find_one(query)
        return document

    async def find_all(self, collection_name, query=None, skip=0, limit=0):
        collection = self.get_collection(collection_name)
        cursor = collection.find(query).skip(skip).limit(limit)
        documents = await cursor.to_list(length=limit)
        return documents

    async def update_one(self, collection_name, query, update):
        collection = self.get_collection(collection_name)
        result = await collection.update_one(query, {'$set': update})
        return result.modified_count

    async def update_many(self, collection_name, query, update):
        collection = self.get_collection(collection_name)
        result = await collection.update_many(query, {'$set': update})
        return result.modified_count

    async def delete_one(self, collection_name, query):
        collection = self.get_collection(collection_name)
        result = await collection.delete_one(query)
        return result.deleted_count

    async def delete_many(self, collection_name, query):
        collection = self.get_collection(collection_name)
        result = await collection.delete_many(query)
        return result.deleted_count

    async def count_documents(self, collection_name, query):
        collection = self.get_collection(collection_name)
        count = await collection.count_documents(query)
        return count
