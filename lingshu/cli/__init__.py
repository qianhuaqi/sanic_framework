"""Minimal LingShu command-line foundation.

P1-00 exposes installed-version reporting only. Application discovery, ``check``, and ``run``
are implemented by P1-09.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from lingshu._version import get_version


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lingshu")
    parser.add_argument(
        "--version",
        action="store_true",
        dest="show_version",
        help="show the installed LingShu version and exit",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=("version",),
        help="available in P1-00: version",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the P1-00 CLI and return a process exit code."""

    parser = _build_parser()
    namespace = parser.parse_args(argv)

    if namespace.show_version or namespace.command == "version":
        print(f"lingshu {get_version()}")
        return 0

    parser.print_help()
    return 0


__all__ = ["main"]
