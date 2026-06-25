from sanic import response


def json_response(data=None, code=0, msg="ok", status=200, errcode=None, errmsg=None):
    if errcode is not None:
        code = errcode
    if errmsg is not None:
        msg = errmsg
    return response.json(
        {
            "code": code,
            "msg": msg,
            "data": data if data is not None else {},
        },
        status=status,
    )
