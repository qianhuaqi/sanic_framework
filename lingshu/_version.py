"""Installed distribution version access."""

from importlib.metadata import PackageNotFoundError, version

_DISTRIBUTION_NAME = "lingshu"


def get_version() -> str:
    """Return the installed LingShu distribution version.

    Raises:
        RuntimeError: If distribution metadata is unavailable.
    """

    try:
        return version(_DISTRIBUTION_NAME)
    except PackageNotFoundError as exc:
        message = "LingShu distribution metadata is unavailable; install the project first."
        raise RuntimeError(message) from exc


__all__ = ["get_version"]
