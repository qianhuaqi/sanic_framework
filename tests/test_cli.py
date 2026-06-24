from framework.cli.main import add_version
from framework.cli.main import make_module
from framework.cli.main import normalize_module_name
from framework.cli.main import normalize_version


def test_cli_add_version_scaffolds_mvc_layout(tmp_path):
    created = add_version("v2", root=tmp_path)

    assert tmp_path / "app" / "v2" in created
    assert (tmp_path / "app" / "v2" / "controller").exists()
    assert (tmp_path / "app" / "v2" / "model").exists()
    assert (tmp_path / "app" / "v2" / "view").exists()
    assert not (tmp_path / "app" / "v2" / "controller" / "index.py").exists()
    assert (tmp_path / "app" / "v2" / "language" / "zh-CN" / "ERROR" / "__init__.py").exists()
    assert (tmp_path / "app" / "v2" / "language" / "en-US" / "ERROR" / "__init__.py").exists()


def test_cli_add_version_rejects_invalid_names():
    try:
        normalize_version("../v1")
    except ValueError as exc:
        assert "Version name" in str(exc)
    else:
        raise AssertionError("invalid version name should fail")


def test_cli_make_module_scaffolds_restful_module(tmp_path):
    created = make_module("v1", "demo", root=tmp_path)

    controller = tmp_path / "app" / "v1" / "controller" / "demo.py"
    model = tmp_path / "app" / "v1" / "model" / "demo.py"
    view = tmp_path / "app" / "v1" / "view" / "demo" / "index.html"
    docs = tmp_path / "public" / "docs" / "v1" / "demo.md"

    assert controller in created
    assert model.exists()
    assert view.exists()
    assert docs.exists()

    controller_text = controller.read_text(encoding="utf-8")
    assert '@bp.get("/")' in controller_text
    assert '@bp.get("/<data_id>")' in controller_text
    assert '@bp.post("/")' in controller_text
    assert '@bp.put("/<data_id>")' in controller_text
    assert '@bp.patch("/<data_id>")' in controller_text
    assert '@bp.delete("/<data_id>")' in controller_text
    assert '"/add"' not in controller_text
    assert '"/edit"' not in controller_text
    assert '"/del"' not in controller_text


def test_cli_make_module_rejects_invalid_module_names():
    try:
        normalize_module_name("../demo")
    except ValueError as exc:
        assert "Module name" in str(exc)
    else:
        raise AssertionError("invalid module name should fail")
