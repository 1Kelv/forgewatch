import json
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from forgewatch.redaction import REDACTED
from forgewatch.scanners import _run, run_osv, run_semgrep


class ScannerFailureTests(unittest.TestCase):
    @patch("forgewatch.scanners._version", return_value="2.5.1")
    @patch("forgewatch.scanners.subprocess.run")
    def test_osv_advisory_examples_are_redacted_without_breaking_json(self, process, _version):
        sample_token = "gh" + "p_" + "A" * 24
        payload = {
            "results": [{
                "source": {"path": "package-lock.json"},
                "packages": [{
                    "package": {"name": "example-package", "version": "1.0.0"},
                    "vulnerabilities": [{
                        "id": "OSV-EXAMPLE-1",
                        "details": f'An example uses token="example-value" and {sample_token}.',
                        "database_specific": {"severity": "HIGH"},
                    }],
                }],
            }],
        }
        process.return_value = subprocess.CompletedProcess([], 1, json.dumps(payload), "")
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "package-lock.json").write_text('{"lockfileVersion": 3}', encoding="utf-8")
            result = run_osv(root, {"binary": "osv-scanner"})
        self.assertEqual(result.status, "findings")
        self.assertIsNone(result.error)
        self.assertEqual(len(result.findings), 1)
        self.assertEqual(result.findings[0].severity, "high")
        self.assertIn("OSV-EXAMPLE-1", result.findings[0].rule_id)
        self.assertNotIn("example-value", json.dumps(result.to_dict()))
        self.assertNotIn(sample_token, json.dumps(result.to_dict()))
        self.assertIn(REDACTED, result.findings[0].title)

    @patch("forgewatch.scanners.subprocess.run")
    def test_scanner_stdout_redaction_preserves_nested_json_and_escaped_quotes(self, process):
        payload = {
            "message": 'Example: Authorization: Bearer "example-credential".',
            "nested": {"token": "private-value", "count": 2},
            "items": ['password="example-password"', "ordinary text"],
        }
        process.return_value = subprocess.CompletedProcess([], 0, json.dumps(payload), "")
        _, stdout, _, _ = _run(["example-scanner"], Path.cwd(), 10)
        parsed = json.loads(stdout)
        self.assertEqual(parsed["nested"]["count"], 2)
        self.assertEqual(parsed["nested"]["token"], REDACTED)
        self.assertEqual(parsed["items"][1], "ordinary text")
        for value in ("private-value", "example-credential", "example-password"):
            self.assertNotIn(value, stdout)

    @patch("forgewatch.scanners._version", return_value="2.5.1")
    @patch("forgewatch.scanners.subprocess.run")
    def test_genuinely_malformed_osv_json_still_makes_scan_incomplete(self, process, _version):
        process.return_value = subprocess.CompletedProcess([], 0, '{"results": [', "")
        with TemporaryDirectory() as directory:
            result = run_osv(Path(directory), {"binary": "osv-scanner"})
        self.assertEqual(result.status, "failed")
        self.assertIn("invalid JSON output", result.error)

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
