"""Release allocation regressions; no compiled curl library is required."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from sync_fork_profiles import available_package_version


class ReleaseVersionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "test")
        self.git("config", "user.email", "test@example.invalid")
        (self.root / "scripts").mkdir()
        (self.root / "scripts/build.py").write_text('__version__ = "2.0.0-os151.2"\n')
        self.git("add", ".")
        self.git("commit", "-qm", "published wrapper release")
        self.git("tag", "v0.16.0.151.3")

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], text=True)

    def test_native_update_does_not_reuse_a_wrapper_tag(self):
        self.assertEqual(
            available_package_version(self.root, "0.16.0.151.3", "2.0.0-os151.3"),
            "0.16.0.151.4",
        )

    def test_retry_keeps_the_allocated_version(self):
        self.assertEqual(
            available_package_version(self.root, "0.16.0.151.4", "2.0.0-os151.3"),
            "0.16.0.151.4",
        )

    def test_matching_published_native_release_is_idempotent(self):
        self.assertEqual(
            available_package_version(self.root, "0.16.0.151.3", "2.0.0-os151.2"),
            "0.16.0.151.3",
        )


if __name__ == "__main__":
    unittest.main()
