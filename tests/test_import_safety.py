from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_imports_have_no_process_side_effects(tmp_path: Path) -> None:
    code = r"""
import importlib
import json
import os
import sys
import threading

before_environment = dict(os.environ)
before_threads = {thread.ident for thread in threading.enumerate()}
modules = (
    "lingshu",
    "lingshu.cli",
    "lingshu.core",
    "lingshu.extensions",
    "lingshu.http",
    "lingshu.record",
    "lingshu.runtime",
    "lingshu.server",
    "lingshu.testing",
)
for name in modules:
    importlib.import_module(name)

forbidden = ("django", "fastapi", "flask", "sanic", "starlette")
print(json.dumps({
    "environment_changed": before_environment != dict(os.environ),
    "forbidden_imports": [name for name in forbidden if name in sys.modules],
    "thread_count_changed": before_threads != {thread.ident for thread in threading.enumerate()},
}))
"""
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence == {
        "environment_changed": False,
        "forbidden_imports": [],
        "thread_count_changed": False,
    }
