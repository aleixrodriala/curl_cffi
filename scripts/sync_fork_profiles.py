#!/usr/bin/env python3

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path


PROFILE_FAMILIES = ("chrome", "safari")
OS_NAMES = {
    "android": "Android",
    "ios": "iOS",
    "linux": "Linux",
    "mac": "macOS",
    "macos": "macOS",
    "win64": "Windows",
    "windows": "Windows",
}
CURL_VERSION_PATTERN = re.compile(r"^2\.0\.0-os(?P<major>\d+)\.(?P<revision>\d+)$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync declarative fork profiles and release pins into curl_cffi."
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--curl-version", required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).parent.parent)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def version_key(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


def load_profiles(source: Path) -> list[dict[str, object]]:
    profiles: list[dict[str, object]] = []
    for family in PROFILE_FAMILIES:
        for path in sorted((source / "profiles" / family).glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            target = payload.get("target")
            browser = payload.get("browser")
            options = payload.get("options")
            if not isinstance(target, str) or not re.fullmatch(r"[a-z0-9_]+", target):
                raise ValueError(f"Invalid profile target in {path}: {target!r}")
            if not isinstance(browser, dict) or not isinstance(options, dict):
                raise ValueError(f"Invalid declarative profile in {path}")
            name = browser.get("name")
            os_name = browser.get("os")
            version = browser.get("version")
            if (
                name != family
                or not isinstance(os_name, str)
                or not isinstance(version, str)
            ):
                raise ValueError(f"Invalid browser identity in {path}")
            profiles.append(
                {
                    "browser": name,
                    "h3": any(key.startswith("http3_") for key in options),
                    "os": os_name,
                    "target": target,
                    "version": version,
                }
            )
    if not profiles:
        raise ValueError(f"No declarative profiles found under {source}")
    return profiles


def latest_target(
    profiles: list[dict[str, object]], browser: str, os_names: set[str]
) -> str:
    candidates = [
        profile
        for profile in profiles
        if profile["browser"] == browser and profile["os"] in os_names
    ]
    if browser == "chrome" and "android" not in os_names:
        candidates = [
            profile
            for profile in candidates
            if re.fullmatch(r"chrome\d+", str(profile["target"]))
        ]
    if not candidates:
        raise ValueError(f"No {browser} profile found for {sorted(os_names)}")
    latest = max(candidates, key=lambda item: version_key(str(item["version"])))
    return str(latest["target"])


def insert_lines(text: str, start: str, anchor: str, lines: list[str]) -> str:
    if not lines:
        return text
    start_index = text.index(start)
    anchor_index = text.index(anchor, start_index)
    return text[:anchor_index] + "".join(lines) + text[anchor_index:]


def replace_assignment(text: str, name: str, value: str) -> str:
    pattern = re.compile(rf'^{name} = "[^"]+"$', re.MULTILINE)
    updated, count = pattern.subn(f'{name} = "{value}"', text)
    if count != 1:
        raise ValueError(f"Expected one assignment for {name}, found {count}")
    return updated


def replace_alias(text: str, alias: str, value: str) -> str:
    pattern = re.compile(rf'^    "{alias}": "[^"]+",$', re.MULTILINE)
    updated, count = pattern.subn(f'    "{alias}": "{value}",', text)
    if count != 1:
        raise ValueError(f"Expected one REAL_TARGET_MAP entry for {alias}")
    return updated


def sync_impersonate(text: str, profiles: list[dict[str, object]]) -> str:
    tree = ast.parse(text)
    literal_targets: set[str] = set()
    enum_targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            literal_targets.add(node.value)
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            enum_targets.add(node.value.value)

    chrome_targets = sorted(
        str(profile["target"]) for profile in profiles if profile["browser"] == "chrome"
    )
    safari_targets = sorted(
        str(profile["target"]) for profile in profiles if profile["browser"] == "safari"
    )
    text = insert_lines(
        text,
        "BrowserTypeLiteral = Literal[",
        "    # Safari\n",
        [
            f'    "{target}",\n'
            for target in chrome_targets
            if target not in literal_targets
        ],
    )
    text = insert_lines(
        text,
        "BrowserTypeLiteral = Literal[",
        "    # Firefox\n",
        [
            f'    "{target}",\n'
            for target in safari_targets
            if target not in literal_targets
        ],
    )
    text = insert_lines(
        text,
        "class BrowserType(str, Enum):",
        '    safari153 = "safari153"\n',
        [
            f'    {target} = "{target}"\n'
            for target in chrome_targets
            if target not in enum_targets
        ],
    )
    text = insert_lines(
        text,
        "class BrowserType(str, Enum):",
        '    firefox133 = "firefox133"\n',
        [
            f'    {target} = "{target}"\n'
            for target in safari_targets
            if target not in enum_targets
        ],
    )

    defaults = {
        "chrome": latest_target(profiles, "chrome", {"mac", "macos"}),
        "chrome_android": latest_target(profiles, "chrome", {"android"}),
        "safari": latest_target(profiles, "safari", {"mac", "macos"}),
        "safari_ios": latest_target(profiles, "safari", {"ios"}),
    }
    constants = {
        "DEFAULT_CHROME": defaults["chrome"],
        "DEFAULT_CHROME_ANDROID": defaults["chrome_android"],
        "DEFAULT_SAFARI": defaults["safari"],
        "DEFAULT_SAFARI_BETA": defaults["safari"],
        "DEFAULT_SAFARI_IOS": defaults["safari_ios"],
        "DEFAULT_SAFARI_IOS_BETA": defaults["safari_ios"],
    }
    for name, value in constants.items():
        text = replace_assignment(text, name, value)
    aliases = {
        **defaults,
        "safari_beta": defaults["safari"],
        "safari_ios_beta": defaults["safari_ios"],
    }
    for alias, value in aliases.items():
        text = replace_alias(text, alias, value)
    return text


def native_entry(profile: dict[str, object]) -> str:
    browser = str(profile["browser"]).title()
    os_name = OS_NAMES.get(str(profile["os"]), str(profile["os"]).title())
    h3 = "True" if profile["h3"] else "False"
    return (
        "    {\n"
        f'        "browser": "{browser}",\n'
        f'        "version": "{profile["version"]}",\n'
        f'        "os": "{os_name}",\n'
        '        "os_version": "",\n'
        f'        "target_name": "{profile["target"]}",\n'
        f'        "h3_fingerprints": {h3},\n'
        "    },\n"
    )


def sync_fingerprints(text: str, profiles: list[dict[str, object]]) -> tuple[str, int]:
    tree = ast.parse(text)
    assignment = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "NATIVE_IMPERSONATE_TARGETS"
            for target in node.targets
        )
    )
    existing = ast.literal_eval(assignment.value)
    existing_names = {entry["target_name"] for entry in existing}
    additions = [
        profile for profile in profiles if profile["target"] not in existing_names
    ]
    if additions:
        lines = text.splitlines(keepends=True)
        insertion = "".join(native_entry(profile) for profile in additions)
        lines.insert(assignment.end_lineno - 1, insertion)
        text = "".join(lines)
    return text, len(existing_names | {str(profile["target"]) for profile in profiles})


def sync_docs(text: str, profiles: list[dict[str, object]]) -> str:
    existing = set(re.findall(r"^- ([a-z0-9_]+)(?:\s|$)", text, re.MULTILINE))
    additions = sorted(
        str(profile["target"])
        for profile in profiles
        if profile["target"] not in existing
    )
    if additions:
        anchor = "\nNotes:\n"
        text = text.replace(
            anchor,
            "\n" + "".join(f"- {target}\n" for target in additions) + anchor,
            1,
        )
    chrome = latest_target(profiles, "chrome", {"mac", "macos"})
    safari = latest_target(profiles, "safari", {"mac", "macos"})
    safari_ios = latest_target(profiles, "safari", {"ios"})
    pattern = re.compile(r"Currently, they're\n``[^`]+``, ``[^`]+`` and ``[^`]+``\.")
    return pattern.sub(
        f"Currently, they're\n``{chrome}``, ``{safari}`` and ``{safari_ios}``.",
        text,
    )


def sync_changelog(
    text: str, package_version: str, curl_version: str, targets: list[str]
) -> str:
    heading = f"- v{package_version}"
    if heading in text:
        return text
    first_release = text.index("- v")
    target_text = ", ".join(f"``{target}``" for target in targets)
    entry = (
        f"- v{package_version}\n"
        f"    - Bundle the fork's ``libcurl-impersonate`` v{curl_version} release.\n"
        f"    - Synchronize verified fork profiles: {target_text}.\n\n"
    )
    return text[:first_release] + entry + text[first_release:]


def update_file(path: Path, content: str, check: bool) -> bool:
    current = path.read_text(encoding="utf-8")
    if current == content:
        return False
    if not check:
        path.write_text(content, encoding="utf-8")
    return True


def main() -> int:
    args = parse_args()
    match = CURL_VERSION_PATTERN.fullmatch(args.curl_version)
    if match is None:
        raise ValueError(f"Unsupported curl-impersonate version: {args.curl_version}")
    source = args.source.resolve()
    root = args.root.resolve()
    profiles = load_profiles(source)
    profile_targets = sorted(str(profile["target"]) for profile in profiles)

    pyproject_path = root / "pyproject.toml"
    pyproject = pyproject_path.read_text(encoding="utf-8")
    current_match = re.search(r'^version = "([^"]+)"$', pyproject, re.MULTILINE)
    if current_match is None:
        raise ValueError("Could not find project version")
    base_version = current_match.group(1).split("+", 1)[0]
    suffix = f"chrome{match.group('major')}.{match.group('revision')}"
    package_version = f"{base_version}+{suffix}"

    changed: list[str] = []
    impersonate_path = root / "curl_cffi" / "requests" / "impersonate.py"
    impersonate = impersonate_path.read_text(encoding="utf-8")
    synced_impersonate = sync_impersonate(impersonate, profiles)
    if update_file(impersonate_path, synced_impersonate, args.check):
        changed.append(str(impersonate_path.relative_to(root)))

    fingerprints_path = root / "curl_cffi" / "fingerprints.py"
    fingerprints = fingerprints_path.read_text(encoding="utf-8")
    synced_fingerprints, native_count = sync_fingerprints(fingerprints, profiles)
    if update_file(fingerprints_path, synced_fingerprints, args.check):
        changed.append(str(fingerprints_path.relative_to(root)))

    synced_pyproject = re.sub(
        r'^version = "[^"]+"$',
        f'version = "{package_version}"',
        pyproject,
        count=1,
        flags=re.MULTILINE,
    )
    if update_file(pyproject_path, synced_pyproject, args.check):
        changed.append(str(pyproject_path.relative_to(root)))

    build_path = root / "scripts" / "build.py"
    build = build_path.read_text(encoding="utf-8")
    synced_build, count = re.subn(
        r'^__version__ = "[^"]+"$',
        f'__version__ = "{args.curl_version}"',
        build,
        flags=re.MULTILINE,
    )
    if count != 1:
        raise ValueError("Could not update scripts/build.py release pin")
    if update_file(build_path, synced_build, args.check):
        changed.append(str(build_path.relative_to(root)))

    docs_path = root / "docs" / "impersonate" / "targets.rst"
    docs = docs_path.read_text(encoding="utf-8")
    synced_docs = sync_docs(docs, profiles)
    if update_file(docs_path, synced_docs, args.check):
        changed.append(str(docs_path.relative_to(root)))

    changelog_path = root / "docs" / "changelog.rst"
    changelog = changelog_path.read_text(encoding="utf-8")
    synced_changelog = sync_changelog(
        changelog, package_version, args.curl_version, profile_targets
    )
    if update_file(changelog_path, synced_changelog, args.check):
        changed.append(str(changelog_path.relative_to(root)))

    readme_path = root / "README.md"
    readme = readme_path.read_text(encoding="utf-8")
    synced_readme, count = re.subn(
        r"Preset_Fingerprints-\d+-blue",
        f"Preset_Fingerprints-{native_count}-blue",
        readme,
    )
    if count != 1:
        raise ValueError("Could not update README preset count")
    if update_file(readme_path, synced_readme, args.check):
        changed.append(str(readme_path.relative_to(root)))

    print(
        json.dumps(
            {
                "changed": changed,
                "curl_version": args.curl_version,
                "package_version": package_version,
                "release_tag": f"v{package_version.replace('+', '-')}",
                "targets": profile_targets,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 1 if args.check and changed else 0


if __name__ == "__main__":
    raise SystemExit(main())
