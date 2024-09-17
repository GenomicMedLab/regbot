"""Fetch regulatory approval data for drug terms"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("regbot")
except PackageNotFoundError:
    __version__ = "unknown"
finally:
    del version, PackageNotFoundError
