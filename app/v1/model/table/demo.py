from lingshu.model.model import Model


class DemoModel(Model):
    table_name = "demo"
    read_source = "auto"
    cache_enabled = True
