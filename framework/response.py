from sanic import response


def json_response(data=None, errcode=0, errmsg="ok", status=200):
    return response.json(
        {
            "errcode": errcode,
            "errmsg": errmsg,
            "data": data if data is not None else {},
        },
        status=status,
    )
