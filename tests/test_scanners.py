import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from forgewatch.scanners import run_osv, run_semgrep


class ScannerFailureTests(unittest.TestCase):
    @patch("forgewatch.scanners._version", return_value="1.177.0")
    @patch("forgewatch.scanners._run", return_value=(2, "", "fatal scanner error", 10))
    def test_scanner_failure_is_not_reported_as_passed(self, _run, _version):
        result = run_semgrep(Path.cwd(), {"binary": "semgrep", "config": "rules.yml"})
        self.assertEqual(result.status, "failed")
        self.assertIn("fatal scanner error", result.error)

    @patch("forgewatch.scanners._version", return_value="1.177.0")
    @patch(
        "forgewatch.scanners._run",
        return_value=(0, '{"results": [], "paths": {"scanned": [], "skipped": []}}', "", 10),
    )
    def test_no_supported_source_files_are_not_an_operational_failure(self, _run, _version):
        result = run_semgrep(Path.cwd(), {"binary": "semgrep", "config": "rules.yml"})
        self.assertEqual(result.status, "not_applicable")
        self.assertIsNone(result.error)

    @patch("forgewatch.scanners._version", return_value="2.5.1")
    @patch("forgewatch.scanners._run", return_value=(0, '{"results": []}', "", 10))
    def test_no_supported_dependency_files_are_not_an_operational_failure(self, _run, _version):
        with TemporaryDirectory() as directory:
            result = run_osv(Path(directory), {"binary": "osv-scanner"})
        self.assertEqual(result.status, "not_applicable")
        self.assertIsNone(result.error)


if __name__ == "__main__":
    unittest.main()
