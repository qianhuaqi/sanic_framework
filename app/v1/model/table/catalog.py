from lingshu.model.model import Model


class CatalogModel(Model):
    table_name = "catalog"
    read_source = "auto"
    cache_enabled = True
