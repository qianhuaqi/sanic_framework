from lingshu.model.model import Model


class OrderModel(Model):
    table_name = "orders"
    read_source = "master"
    cache_enabled = False
