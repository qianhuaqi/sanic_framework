from framework.model.model import Model


class OrderModel(Model):
    table_name = "orders"
    read_source = "master"
    cache_enabled = False


class CatalogModel(Model):
    table_name = "catalog"
    read_source = "auto"
    cache_enabled = True


class DemoModel(Model):
    table_name = "demo"
    read_source = "auto"
    cache_enabled = True
