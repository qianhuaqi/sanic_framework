from sanic import response


def json_response(data=None, code=0, msg="ok", status=200):
    return response.json(
        {
            "code": code,
            "msg": msg,
            "data": data if data is not None else {},
        },
        status=status,
    )
