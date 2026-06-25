from pathlib import Path
import asyncio

import pytest

from framework.app import create_app
from framework.error_codes import build_error_code_index, parse_error_code_catalog
from framework.exception import get_error_message, language_roots, version_from_path


ROOT = Path(__file__).resolve().parents[1]


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
    (zh_dir / "system.ini").write_text("[System]\n990000 = 系统错误\n", encoding="utf-8")
    (zh_dir / "auth.ini").write_text("[Auth]\n990000 = 签名错误\n", encoding="utf-8")

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
    (version_zh_dir / "user.ini").write_text("[User]\n110000 = 版本用户不存在\n", encoding="utf-8")
    (project_zh_dir / "user.ini").write_text("[User]\n110000 = 项目用户不存在\n", encoding="utf-8")
    (project_en_dir / "user.ini").write_text("[User]\n110000 = User does not exist\n", encoding="utf-8")

    index = build_error_code_index(
        [tmp_path / "app" / "v1" / "language", tmp_path / "app" / "language"],
        module_map_path=module_map,
    )

    item = index["codes"][0]
    assert item["messages"]["zh-CN"] == "版本用户不存在"
    assert item["messages"]["en-US"] == "User does not exist"


def test_language_roots_do_not_include_legacy_top_level_language(tmp_path, monkeypatch):
    (tmp_path / "app" / "v1" / "language").mkdir(parents=True)
    (tmp_path / "app" / "language").mkdir(parents=True)
    (tmp_path / "language").mkdir(parents=True)
    (tmp_path / "framework" / "language").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    roots = [path.relative_to(tmp_path).as_posix() for path in language_roots("v1")]

    assert roots == ["app/v1/language", "app/language", "framework/language"]


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

    class Request:
        pass

    class App:
        pass

    class Ctx:
        pass

    class Config:
        language = "zh-CN"

    request = Request()
    request.app = App()
    request.app.ctx = Ctx()
    request.app.ctx.config = Config()

    request.path = "/v1/demo"
    assert get_error_message(request, 110000) == "v1 message"
    request.path = "/v1_admin/demo"
    assert get_error_message(request, 110000) == "admin message"
    request.path = "/meta/error-codes"
    assert get_error_message(request, 110000) == "public message"


def test_get_error_message_reads_language_package():
    class Request:
        path = "/v1/demo"

    class App:
        pass

    class Ctx:
        pass

    class Config:
        language = "zh-CN"

    request = Request()
    request.app = App()
    request.app.ctx = Ctx()
    request.app.ctx.config = Config()

    assert get_error_message(request, 991111) == "请求参数不能为空"


def test_meta_error_codes_endpoint_is_available_in_testing():
    app = create_app()

    _, response = asyncio.run(app.asgi_client.get("/meta/error-codes"))

    assert response.status == 200
    assert response.json["code"] == 0
    data = response.json["data"]
    assert data["locales"] == ["zh-CN", "en-US"]
    assert data["summary"] == {"total": 24, "modules": 5, "reserved": 1}
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
