#!/usr/bin/env python
# -*- coding: utf-8 -*-
# config/settings.py
import configparser
import glob
import importlib
import os

from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
if os.getenv("SANIC_ENV", "").lower() not in {"test", "testing"}:
    load_dotenv(dotenv_path)


class Settings:
    """Base configuration class."""
    APP = int(os.environ.get('APP', 1))
    HOST = os.environ.get('HOST', '0.0.0.0')
    PORT = int(os.environ.get('PORT', 8000))
    WORKERS = int(os.environ.get('WORKERS', 4))
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*')
    DEBUG = os.environ.get('DEBUG', False)
    PROJECT = os.environ.get('PROJECT', 'sanic')
    TESTING = os.environ.get('TESTING', False)
    KEEP_ALIVE_TIMEOUT = os.environ.get('KEEP_ALIVE_TIMEOUT', 5)  # 客户端连接保持时间 过长导致慢速攻击 导致服务器资源耗尽
    REMOTE_ADDR_HEADER = 'X-Forwarded-For'  # 指定用于确定客户端 IP 地址的 HTTP 头字段
    AUTH = {
        'app': int(os.environ.get('APP', 1)),
        'secret': os.getenv('AUTH_SECRET', 'change-me'),
        'expire': int(os.getenv('AUTH_EXPIRE', 3600))
    }
    CACHE = {
        'dir': os.environ.get('CACHE_DIR', 'runtime'),
        'expire': int(os.getenv('CACHE_EXPIRE', 3600)),
        'enabled': os.environ.get('CACHE_ENABLED', False),
        'allow_status': os.environ.get('CACHE_ALLOW_STATUS', [200, 201])
    }
    CRYPT = {
        'enabled': os.getenv('CRYPT_ENABLED', False),
        'response_secret': os.getenv('CRYPT_RESPONSE_SECRET', 'change-me'),
        'params_secret': os.environ.get('CRYPT_PARAMS_SECRET', 'change-me'),
    }
    DB_ENABLED = os.environ.get('DB_ENABLED', True)
    DB_MASTER = {
        'enabled': os.environ.get('DB_MASTER_ENABLED', True),
        'host': os.getenv('DB_MASTER_HOST', 'localhost'),
        'port': int(os.getenv('DB_MASTER_PORT', 3306)),
        'user': os.getenv('DB_MASTER_USER', 'app'),
        'password': os.getenv('DB_MASTER_PASSWORD', 'change-me'),
        'database': os.getenv('DB_MASTER_DATABASE', 'app'),
    }
    DB_SLAVE = {
        'enabled': os.environ.get('DB_SLAVE_ENABLED', True),
        'host': os.getenv('DB_SLAVE_HOST', 'localhost'),
        'port': int(os.getenv('DB_SLAVE_PORT', 3306)),
        'user': os.getenv('DB_SLAVE_USER', 'app'),
        'password': os.getenv('DB_SLAVE_PASSWORD', 'change-me'),
        'database': os.getenv('DB_SLAVE_DATABASE', 'app'),
    }
    REDIS = {
        'enabled': os.getenv('REDIS_ENABLED', True),
        'sentinel_enabled': os.getenv('REDIS_SENTINEL_ENABLED', True),
        'sentinels': [
            (os.getenv('REDIS_SENTINEL_1_HOST', 'localhost'), int(os.getenv('REDIS_SENTINEL_1_PORT', 26379))),
            (os.getenv('REDIS_SENTINEL_2_HOST', 'localhost'), int(os.getenv('REDIS_SENTINEL_2_PORT', 26379))),
            (os.getenv('REDIS_SENTINEL_3_HOST', 'localhost'), int(os.getenv('REDIS_SENTINEL_3_PORT', 26379)))
        ],
        'master_name': os.getenv('REDIS_MASTER_NAME', 'mymaster'),
        'password': os.getenv('REDIS_PASSWORD', ''),
        'db': int(os.getenv('REDIS_DB', 0)),
        'expire': int(os.getenv('REDIS_EXPIRE', 3600)),
        'prefix': os.getenv('REDIS_PREFIX', 'sanic_'),
        'idle_timeout': int(os.getenv('REDIS_IDLE_TIMEOUT', 600)),
        'host': os.getenv('REDIS_HOST', 'localhost'),
        'port': os.getenv('REDIS_PORT', 6379)
    }
    MONGODB = {
        'enabled': os.getenv('MONGODB_ENABLED', True),
        'host': os.getenv('MONGODB_HOST', 'localhost'),
        'port': int(os.getenv('MONGODB_PORT', 27017)),
        'username': os.getenv('MONGODB_USERNAME', None),
        'password': os.getenv('MONGODB_PASSWORD', None),
        'database': os.getenv('MONGODB_DB', 'my_mongodb')
    }
    LOGGER = {
        'formatter': os.getenv('LOG_FORMATTER', '%(levelname)s %(asctime)s %(name)s %(message)s'),
        'path': os.getenv('LOG_PATH', '/var/log'),
        'file': os.getenv('LOG_FILE', 'app.log'),
        'max_bytes': int(os.getenv('LOG_MAX_BYTES', 1073741824)),
        'backup_count': int(os.getenv('LOG_BACKUP_COUNT', 7)),
        'when': os.getenv('LOG_WHEN', 'MIDNIGHT'),
        'interval': int(os.getenv('LOG_INTERVAL', 1))
    }
    LANGUAGE = os.getenv('LANGUAGE', 'zh-CN')
    LOCALE_DIR = os.getenv('LOCALE_DIR', 'language')

    @staticmethod
    def load_ini_config(directory):
        config = configparser.ConfigParser()
        ini_files = glob.glob(os.path.join(directory, '*.ini'))
        for file in ini_files:
            config.read(file, encoding='utf-8')
        ini_config = {section: dict(config.items(section)) for section in config.sections()}
        return ini_config

    @staticmethod
    def load_py_config(directory):
        py_files = glob.glob(os.path.join(directory, '*.py'))
        py_config = {}
        for file in py_files:
            if os.path.basename(file) == 'settings.py':
                continue
            spec = importlib.util.spec_from_file_location("module.name", file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            for attr in dir(module):
                if attr.isupper():
                    py_config[attr] = getattr(module, attr)
        return py_config


class DevelopmentConfig(Settings):
    DEBUG = True


class TestingConfig(Settings):
    TESTING = True


class ProductionConfig(Settings):
    TESTING = True
