from sanic import Sanic
import os


def pytest_configure():
    Sanic.test_mode = True
    os.environ["SANIC_ENV"] = "testing"
