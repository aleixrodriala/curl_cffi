from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


ROOT = Path(__file__).parents[2]
SPEC = spec_from_file_location(
    "sync_fork_profiles", ROOT / "scripts" / "sync_fork_profiles.py"
)
assert SPEC is not None and SPEC.loader is not None
SYNC = module_from_spec(SPEC)
SPEC.loader.exec_module(SYNC)


def profiles_with_future_targets():
    return [
        {
            "browser": "chrome",
            "h3": True,
            "os": "mac",
            "target": "chrome152",
            "version": "152.0.1.2",
        },
        {
            "browser": "chrome",
            "h3": True,
            "os": "android",
            "target": "chrome152_android",
            "version": "152.0.1.3",
        },
        {
            "browser": "safari",
            "h3": False,
            "os": "macos",
            "target": "safari270",
            "version": "27.0",
        },
        {
            "browser": "safari",
            "h3": False,
            "os": "ios",
            "target": "safari270_ios",
            "version": "27.0",
        },
    ]


def test_compute_package_version_appends_fingerprint_segments():
    assert SYNC.compute_package_version("0.16.0.151.2", "152", "1") == "0.16.0.152.1"
    # Pre-release and local markers from older schemes are stripped.
    assert SYNC.compute_package_version("0.16.0b2+chrome151.2", "151", "3") == (
        "0.16.0.151.3"
    )


def test_sync_impersonate_adds_targets_and_updates_aliases():
    original = (ROOT / "curl_cffi" / "requests" / "impersonate.py").read_text()

    updated = SYNC.sync_impersonate(original, profiles_with_future_targets())

    assert '    "chrome152",' in updated
    assert '    "chrome152_android",' in updated
    assert '    chrome152 = "chrome152"' in updated
    assert '    safari270_ios = "safari270_ios"' in updated
    assert 'DEFAULT_CHROME = "chrome152"' in updated
    assert 'DEFAULT_CHROME_ANDROID = "chrome152_android"' in updated
    assert 'DEFAULT_SAFARI = "safari270"' in updated
    assert '    "safari_ios": "safari270_ios",' in updated


def test_sync_fingerprints_adds_native_metadata_once():
    original = (ROOT / "curl_cffi" / "fingerprints.py").read_text()

    updated, count = SYNC.sync_fingerprints(original, profiles_with_future_targets())
    repeated, repeated_count = SYNC.sync_fingerprints(
        updated, profiles_with_future_targets()
    )

    assert '"target_name": "chrome152_android"' in updated
    assert '"target_name": "safari270_ios"' in updated
    assert count == repeated_count
    assert repeated == updated
