from importlib import metadata

__title__ = "curl_cffi"

# The import package is "curl_cffi", but this fork is distributed on PyPI as
# "curl-cffi-fingerprints"; fall back to the upstream name for source installs.
for _dist_name in ("curl-cffi-fingerprints", "curl_cffi"):
    try:
        __description__ = metadata.metadata(_dist_name)["Summary"]
        __version__ = metadata.version(_dist_name)
        break
    except metadata.PackageNotFoundError:
        continue
else:
    raise metadata.PackageNotFoundError("curl-cffi-fingerprints")


def _resolve_curl_version() -> str:
    """Read libcurl version without creating a curl easy handle at import time."""
    from ._wrapper import ffi, lib

    return ffi.string(lib.curl_version()).decode()


__curl_version__ = _resolve_curl_version()
