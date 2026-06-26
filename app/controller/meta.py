from sanic import Blueprint

from lingshu.error_codes import build_error_code_index, normalize_locale_name
from lingshu.exception import language_roots, module_map_paths, raise_code
from lingshu.response import json_response
from lingshu.router import RoutePolicy, set_blueprint_policy
from lingshu.versioning import normalize_version


bp = Blueprint("meta", url_prefix="/meta")
set_blueprint_policy(
    bp,
    RoutePolicy(
        auth_required=False,
        signing_required=False,
        maintenance_check=False,
    ),
)


@bp.get("/error-codes")
async def error_codes(request):
    version = request.args.get("version", "").strip()
    if version:
        try:
            version = normalize_version(version)
        except ValueError:
            raise_code(request, 991112, status_code=400)
    index = build_error_code_index(language_roots(version), module_map_path=module_map_paths(version))

    code_filter = request.args.get("code", "").strip()
    module_filter = request.args.get("module", "").strip().lower()
    language_filter = normalize_locale_name(request.args.get("language", "").strip()) if request.args.get("language") else ""
    query = request.args.get("q", "").strip().lower()

    codes = index["codes"]
    if code_filter:
        codes = [item for item in codes if item["code"] == code_filter]
    if module_filter:
        codes = [item for item in codes if item["module"] == module_filter]
    if language_filter:
        codes = [item for item in codes if language_filter in item["messages"]]
    if query:
        codes = [
            item
            for item in codes
            if query in item["code"].lower()
            or query in item["module"].lower()
            or query in item["section"].lower()
            or any(query in message.lower() for message in item["messages"].values())
        ]

    code_set = {item["code"] for item in codes}
    modules = []
    reserved = []
    has_filters = bool(module_filter or code_filter or language_filter or query)
    for bucket in index["modules"]:
        module_items = [item for item in bucket["items"] if item["code"] in code_set]
        payload = {
            "module": bucket["module"],
            "range": bucket["range"],
            "total": len(module_items),
            "codes": [
                {
                    "code": item["code"],
                    "default_message": item["default_message"],
                    "messages": item["messages"],
                    "sources": item["sources"],
                }
                for item in module_items
            ],
        }
        if module_items:
            modules.append(payload)
        elif not has_filters and bucket.get("reserved"):
            reserved.append(payload)

    return json_response(
        {
            "locales": index["locales"],
            "summary": {
                "total": len(codes),
                "modules": len(modules),
                "reserved": len(reserved),
            },
            "modules": modules,
            "reserved": reserved,
        }
    )
