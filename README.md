# curl-cffi-fingerprints

[![PyPI version](https://img.shields.io/pypi/v/curl-cffi-fingerprints)](https://pypi.org/project/curl-cffi-fingerprints/)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/curl-cffi-fingerprints)
![Preset](https://img.shields.io/badge/Preset_Fingerprints-44-blue)

A drop-in fork of [curl_cffi](https://github.com/lexiforest/curl_cffi) whose one
job is keeping browser fingerprints fresh: every new Chrome and Safari release
gets its impersonation profile harvested, verified, and shipped automatically.

`curl_cffi` is a Python binding for
[curl-impersonate](https://github.com/aleixrodriala/curl-impersonate) via
[cffi](https://cffi.readthedocs.io/en/latest/). Unlike pure-Python HTTP clients
such as `httpx` or `requests`, it can impersonate browsers' TLS/JA3 and HTTP/2
fingerprints, so requests look like they come from a real browser.

This fork changes nothing about the API. It exists because upstream only adds
impersonation targets when there is a protocol-level change worth supporting,
while scraping in practice often needs the *current* browser version. Here, new
versions land as soon as they are released.

## How it works

The fingerprints are harvested and shipped by an automated pipeline across two
repositories:

1. [aleixrodriala/curl-impersonate](https://github.com/aleixrodriala/curl-impersonate)
   captures profiles from real browsers for each new release — Chrome on
   Windows, macOS, Linux and Android, and Safari on macOS and iOS — as
   declarative JSON profiles, and publishes a `libcurl-impersonate` build. Each
   profile carries the browser's full header set for that OS (User-Agent,
   client hints and header order), so an impersonated request matches a real
   browser beyond just the TLS/HTTP2 fingerprint.
2. That release triggers a sync workflow in this repository, which adds the new
   targets, bumps the version, builds wheels for all supported platforms, and
   publishes them to PyPI and GitHub Releases.

No manual step in between: a new browser release becomes a new installable
version of this package.

## Versioning

Versions follow `<upstream-base>.<chrome-major>.<revision>`. For example,
`0.16.0.151.2` is upstream `curl_cffi` 0.16.0 plus the fingerprint drop for
Chrome 151, revision 2. Upgrading within the same upstream base only adds
fingerprints; API changes come from tracking upstream releases.

## Install

    pip install curl-cffi-fingerprints --upgrade

This works on Linux, macOS and Windows out of the box.

The import name is still `curl_cffi` — existing code keeps working unchanged.
Because it provides the same import package, uninstall the upstream package
first if you have it:

    pip uninstall -y curl-cffi
    pip install curl-cffi-fingerprints --upgrade

Wheels are also attached to
[GitHub Releases](https://github.com/aleixrodriala/curl_cffi/releases) if you
prefer pinning an exact fingerprint drop.

## Usage

The API is identical to upstream `curl_cffi`: a requests-like high-level API, a
low-level `curl` API, asyncio, WebSockets, and the `curl-cffi` CLI. Full
documentation lives at [curl-cffi.readthedocs.io](https://curl-cffi.readthedocs.io).

```python
import curl_cffi

# Notice the impersonate parameter: "chrome" always resolves to the newest
# harvested Chrome fingerprint, so you stay current just by upgrading.
r = curl_cffi.get("https://tls.browserleaks.com/json", impersonate="chrome")
print(r.json())

# Per-OS rolling aliases: the profile carries the full header set of a real
# browser on that OS — User-Agent, sec-ch-ua, sec-ch-ua-platform, sec-fetch-*,
# accept-language and header order all match, not just the TLS fingerprint.
r = curl_cffi.get("https://tls.browserleaks.com/json", impersonate="chrome_windows")
# also: "chrome_macos", "chrome_linux", "chrome_android"

# Other rolling aliases: "safari", "safari_ios"
r = curl_cffi.get("https://tls.browserleaks.com/json", impersonate="safari_ios")

# Or pin a specific version
r = curl_cffi.get("https://tls.browserleaks.com/json", impersonate="chrome151")

# http/3 with impersonation
r = curl_cffi.get("https://example.com", http_version="v3", impersonate="chrome")

# Bring your own fingerprints for non-browser targets
r = curl_cffi.get("https://tls.browserleaks.com/json", ja3=..., akamai=...)
```

Sessions and asyncio:

```python
s = curl_cffi.Session()
s.get("https://httpbin.org/cookies/set/foo/bar")
print(s.cookies)

from curl_cffi import AsyncSession

async with AsyncSession() as s:
    r = await s.get("https://example.com")
```

CLI:

```sh
# Debug a URL with impersonation
curl-cffi get tls.browserleaks.com/json --impersonate chrome

# List the fingerprints available on your install
curl-cffi list
```

## Supported targets

All upstream targets are included, plus the fork's harvested profiles for new
Chrome (desktop and Android) and Safari (macOS and iOS) releases. To see
exactly what your installed version supports, run `curl-cffi list`; the profile
sources live in the
[curl-impersonate fork](https://github.com/aleixrodriala/curl-impersonate).

## Relationship to upstream

This fork stays intentionally thin: all library development happens in
[lexiforest/curl_cffi](https://github.com/lexiforest/curl_cffi), which this
fork tracks and merges regularly. Only the fingerprint pipeline and the
harvested profiles are added here.

- Library bugs or feature requests → report them
  [upstream](https://github.com/lexiforest/curl_cffi/issues).
- Fingerprint issues (wrong/missing profile for a browser version) → report
  them at the
  [curl-impersonate fork](https://github.com/aleixrodriala/curl-impersonate/issues).

If you need commercial support or fingerprints beyond Chrome/Safari, check the
upstream ecosystem at [impersonate.pro](https://impersonate.pro).

## Acknowledgement

- Forked from [lexiforest/curl_cffi](https://github.com/lexiforest/curl_cffi)
  by @lexiforest, which was originally forked from
  [multippt/python_curl_cffi](https://github.com/multippt/python_curl_cffi).
  Both are under the MIT license.
- Built on [curl-impersonate](https://github.com/lwthiker/curl-impersonate) by
  @lwthiker and the [lexiforest fork](https://github.com/lexiforest/curl-impersonate).
- Headers/Cookies files are copied from
  [httpx](https://github.com/encode/httpx/blob/master/httpx/_models.py), which
  is under the BSD license.

MIT licensed.
