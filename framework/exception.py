class APIException(Exception):
    def __init__(self, errcode=500000, errmsg="internal error", status_code=500, data=None):
        super().__init__(errmsg)
        self.errcode = errcode
        self.errmsg = errmsg
        self.status_code = status_code
        self.data = data or {}
