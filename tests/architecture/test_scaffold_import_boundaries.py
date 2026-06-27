"""Verify scaffold templates do not generate forbidden imports."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAFFOLD_DIR = ROOT / "src" / "lingshu" / "scaffold"


def _read_contract():
    raw = (ROOT / "docs" / "architecture" / "architecture-contract.json").read_text(
        encoding="utf-8"
    )
    return json.loads(raw)


def test_scaffold_templates_exist():
    """Scaffold template files must exist as .j2 files."""
    j2_files = list(SCAFFOLD_DIR.glob("*.j2"))
    assert len(j2_files) > 0, "No scaffold .j2 templates found"


def test_scaffold_templates_do_not_generate_system_imports():
    """Scaffold templates must not generate code importing lingshu.system.*"""
    contract = _read_contract()
    forbidden_prefixes = contract["scaffold_forbidden_imports"]

    j2_files = list(SCAFFOLD_DIR.glob("*.j2"))
    violations = []

    for template in j2_files:
        content = template.read_text(encoding="utf-8")
        for prefix in forbidden_prefixes:
            # Check if template generates this import (as Jinja text, not rendered)
            # We look for the import statement pattern in the template source
            if prefix in content:
                # Only flag if it looks like an import statement, not a comment
                for line in content.splitlines():
                    stripped = line.strip()
                    if prefix in stripped and not stripped.startswith("#"):
                        if "import" in stripped or "from" in stripped:
                            violations.append(
                                f"{template.name}: {stripped}"
                            )

    assert not violations, (
        "Scaffold templates generate forbidden imports:\n"
        + "\n".join(violations)
    )


def test_scaffold_contract_in_json():
    """The architecture contract must define scaffold_forbidden_imports."""
    contract = _read_contract()
    assert "lingshu.system" in contract["scaffold_forbidden_imports"]
    assert "lingshu.middleware" in contract["scaffold_forbidden_imports"]
