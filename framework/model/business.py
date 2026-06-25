from __future__ import annotations


class BusinessModel:
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if "table_name" in cls.__dict__:
            raise TypeError("BusinessModel must not declare table_name")

    def __init__(self, request):
        self.request = request
        self.app = request.app
        self.db = getattr(request.app.ctx, "mysql", None)
        self.redis = getattr(request.app.ctx, "redis", None)
        self.logger = getattr(request.app.ctx, "logger", None)
