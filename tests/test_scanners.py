import unittest
from pathlib import Path
from unittest.mock import patch

from forgewatch.scanners import run_semgrep


class ScannerFailureTests(unittest.TestCase):
    @patch("forgewatch.scanners._version", return_value="1.177.0")
    @patch("forgewatch.scanners._run", return_value=(2, "", "fatal scanner error", 10))
    def test_scanner_failure_is_not_reported_as_passed(self, _run, _version):
        result = run_semgrep(Path.cwd(), {"binary": "semgrep", "config": "rules.yml"})
        self.assertEqual(result.status, "failed")
        self.assertIn("fatal scanner error", result.error)


if __name__ == "__main__":
    unittest.main()
