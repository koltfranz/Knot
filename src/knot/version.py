from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("knot")
except PackageNotFoundError:
    __version__ = "0.5.0"
