from __future__ import annotations

import argparse
import re
import subprocess

SIGN_OFF = re.compile(r"^Signed-off-by: .+ <[^<>]+>$", re.MULTILINE)


def _git(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base")
    parser.add_argument("head")
    arguments = parser.parse_args()

    commits = [
        commit
        for commit in _git(
            "rev-list", "--no-merges", f"{arguments.base}..{arguments.head}"
        ).splitlines()
        if commit
    ]
    unsigned: list[str] = []
    for commit in commits:
        message = _git("show", "-s", "--format=%B", commit)
        if SIGN_OFF.search(message) is None:
            unsigned.append(commit)

    if unsigned:
        formatted = "\n".join(unsigned)
        raise SystemExit(f"Commits missing DCO sign-off:\n{formatted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
