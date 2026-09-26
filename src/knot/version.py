from importlib.metadata import PackageNotFoundError, version

for _distribution in ("knot-ledger", "knot"):
    try:
        __version__ = version(_distribution)
        break
    except PackageNotFoundError:
        continue
else:
    __version__ = "0.7.0"
