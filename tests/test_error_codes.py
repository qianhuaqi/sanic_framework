from pathlib import Path
import asyncio
from types import SimpleNamespace

import pytest

from lingshu.app import create_app
from lingshu.error_codes import build_error_code_index, parse_error_code_catalog
from lingshu.exception import get_error_message, language_roots, module_map_paths, version_from_path
from lingshu.system import sanic_adapter


ROOT = Path(__file__).resolve().parents[1]


def _request(path="/v1/demo", language="zh-CN"):
    request = SimpleNamespace(path=path)
    request.app = SimpleNamespace(ctx=SimpleNamespace())
    sanic_adapter.set_app_config(request.app, SimpleNamespace(language=language))
    return request


def test_error_code_catalog_loads_canonical_locales_from_app_language():
    index = build_error_code_index(ROOT / "app" / "language")

    assert index["locales"] == ["zh-CN", "en-US"]
    assert index["total"] > 0
    assert index["modules"][0]["module"] == "language"
    assert index["modules"][0]["range"] == "100000-109999"
    assert index["modules"][0]["total"] == 0
    assert any(bucket["module"] == "user" and bucket["total"] == 3 for bucket in index["modules"])
    assert any(item["code"] == "991111" for item in index["codes"])


def test_error_code_catalog_rejects_duplicate_codes(tmp_path):
    zh_dir = tmp_path / "zh-CN" / "ERROR"
    zh_dir.mkdir(parents=True)
    (zh_dir / "system.ini").write_text("[System]\n990000 = system duplicate\n", encoding="utf-8")
    (zh_dir / "auth.ini").write_text("[Auth]\n990000 = auth duplicate\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate error code '990000'"):
        parse_error_code_catalog(tmp_path)


def test_error_code_catalog_uses_version_language_before_app_language(tmp_path):
    module_map = tmp_path / "app" / "language" / "modules.ini"
    module_map.parent.mkdir(parents=True)
    module_map.write_text("[Modules]\n110000-119999 = user\n", encoding="utf-8")

    version_zh_dir = tmp_path / "app" / "v1" / "language" / "zh-CN" / "ERROR"
    project_zh_dir = tmp_path / "app" / "language" / "zh-CN" / "ERROR"
    project_en_dir = tmp_path / "app" / "language" / "en-US" / "ERROR"
    version_zh_dir.mkdir(parents=True)
    project_zh_dir.mkdir(parents=True)
    project_en_dir.mkdir(parents=True)
    (version_zh_dir / "user.ini").write_text("[User]\n110000 = version user missing\n", encoding="utf-8")
    (project_zh_dir / "user.ini").write_text("[User]\n110000 = project user missing\n", encoding="utf-8")
    (project_en_dir / "user.ini").write_text("[User]\n110000 = User does not exist\n", encoding="utf-8")

    index = build_error_code_index(
        [tmp_path / "app" / "v1" / "language", tmp_path / "app" / "language"],
        module_map_path=module_map,
    )

    item = index["codes"][0]
    assert item["messages"]["zh-CN"] == "version user missing"
    assert item["messages"]["en-US"] == "User does not exist"


def test_language_roots_do_not_include_legacy_top_level_language(tmp_path, monkeypatch):
    (tmp_path / "app" / "v1" / "language").mkdir(parents=True)
    (tmp_path / "app" / "language").mkdir(parents=True)
    (tmp_path / "language").mkdir(parents=True)
    (tmp_path / "framework" / "language").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    roots = [path.as_posix() for path in language_roots("v1")]

    assert roots[0].endswith("app/v1/language")
    assert roots[1].endswith("app/language")
    assert roots[2].endswith("src/lingshu/language")


def test_module_map_paths_merge_project_and_internal_registry(tmp_path, monkeypatch):
    project_map = tmp_path / "app" / "language" / "modules.ini"
    project_map.parent.mkdir(parents=True)
    project_map.write_text("[Modules]\n110000-119999 = user\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    paths = [path.as_posix() for path in module_map_paths()]

    assert project_map.as_posix() in paths
    assert any(path.endswith("lingshu/resources/error_codes/modules.ini") for path in paths)


def test_version_from_path_supports_unified_version_names():
    assert version_from_path("/v1/demo") == "v1"
    assert version_from_path("/v1_admin/demo") == "v1_admin"
    assert version_from_path("/v2_partner/demo") == "v2_partner"
    assert version_from_path("/meta/error-codes") == ""
    assert version_from_path("/admin/demo") == ""


def test_get_error_message_uses_version_and_public_language_packages(tmp_path, monkeypatch):
    module_map = tmp_path / "app" / "language" / "modules.ini"
    module_map.parent.mkdir(parents=True)
    module_map.write_text("[Modules]\n110000-119999 = user\n", encoding="utf-8")
    public_dir = tmp_path / "app" / "language" / "zh-CN" / "ERROR"
    v1_dir = tmp_path / "app" / "v1" / "language" / "zh-CN" / "ERROR"
    admin_dir = tmp_path / "app" / "v1_admin" / "language" / "zh-CN" / "ERROR"
    public_dir.mkdir(parents=True)
    v1_dir.mkdir(parents=True)
    admin_dir.mkdir(parents=True)
    (public_dir / "user.ini").write_text("[User]\n110000 = public message\n", encoding="utf-8")
    (v1_dir / "user.ini").write_text("[User]\n110000 = v1 message\n", encoding="utf-8")
    (admin_dir / "user.ini").write_text("[User]\n110000 = admin message\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    request = _request("/v1/demo")
    assert get_error_message(request, 110000) == "v1 message"
    request.path = "/v1_admin/demo"
    assert get_error_message(request, 110000) == "admin message"
    request.path = "/meta/error-codes"
    assert get_error_message(request, 110000) == "public message"


def test_get_error_message_reads_language_package():
    assert get_error_message(_request("/v1/demo"), 991111) == "请求参数不能为空"


def test_get_error_message_falls_back_to_builtin_language_when_project_language_is_absent(tmp_path, monkeypatch):
    (tmp_path / "app" / "language").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    assert get_error_message(_request("/v1/demo"), 991111) == "请求参数不能为空"


def test_meta_error_codes_endpoint_is_available_in_testing():
    app = create_app()

    _, response = asyncio.run(app.asgi_client.get("/meta/error-codes"))

    assert response.status == 200
    assert response.json["code"] == 0
    data = response.json["data"]
    assert data["locales"] == ["zh-CN", "en-US"]
    assert data["summary"] == {"total": 36, "modules": 5, "reserved": 1}
    assert data["modules"][0]["module"] == "user"
    assert data["modules"][0]["total"] == 3
    assert all("codes" in bucket for bucket in data["modules"])
    assert data["reserved"][0]["module"] == "language"
    assert data["reserved"][0]["range"] == "100000-109999"
    assert any(item["code"] == "110000" for item in data["modules"][0]["codes"])
    assert any(item["code"] == "991111" for bucket in data["modules"] for item in bucket["codes"])


def test_meta_error_codes_validates_version_parameter():
    app = create_app()

    async def scenario():
        for value in ("", "v1", "v1_admin"):
            _, response = await app.asgi_client.get(f"/meta/error-codes?version={value}")
            assert response.status == 200
            assert response.json["code"] == 0

        for value in ("../", "../../config", "v1/../../../", "C:\\Windows", "/absolute/path", "..%2F..%2Fconfig"):
            _, response = await app.asgi_client.get(f"/meta/error-codes?version={value}")
            assert response.status == 400
            assert response.json["code"] == 991112
            assert "sanic" not in response.json["msg"].lower()
            assert ":\\" not in response.json["msg"]

    asyncio.run(scenario())
