import json
import tempfile
import unittest
from pathlib import Path

from forgewatch.reporting import markdown, write_reports

from forgewatch.models import ScannerRun
from helpers import finding, result


class ReportingTests(unittest.TestCase):
    def test_human_report_leads_with_plain_language_and_keeps_technical_details_separate(self):
        item = finding()
        report = markdown(result(item))
        self.assertIn("Problems need review", report)
        self.assertIn("A new-tab link could let another site control the original page", report)
        self.assertIn("Why this matters", report)
        self.assertIn("What to do", report)
        self.assertIn("Technical details for maintainers", report)

    def test_json_report_contains_a_plain_language_summary(self):
        scan = result(finding())
        with tempfile.TemporaryDirectory() as directory:
            write_reports(scan, Path(directory))
            payload = json.loads((Path(directory) / "scan.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["plain_language"]["headline"], "Problems need review")
        self.assertIn(scan.findings[0].fingerprint, payload["plain_language"]["findings"])
        self.assertIn("closing_summary", payload["plain_language"])

    def test_fix_steps_and_closing_summary_are_exported(self):
        item = finding()
        item.fix_guidance = {"steps": ["Edit App.tsx", "Run the tests"], "basis": ["Found in App.tsx"], "commands": ["npm run test"], "working_directory": ".", "disclaimer": "Not tested"}
        report = markdown(result(item))
        self.assertIn("1. Edit App.tsx", report)
        self.assertIn("2. Run the tests", report)
        self.assertIn("## Summary\n", report)
        self.assertLess(report.index("Technical details for maintainers"), report.index("## Summary\n"))

    def test_incomplete_report_explains_failed_check_in_plain_language(self):
        scan = result(finding(), status="incomplete")
        scan.findings = []
        scan.scanner_runs = [
            ScannerRun(
                scanner="osv-scanner",
                version="2.5.1",
                status="failed",
                coverage="supported manifests and lockfiles",
                duration_ms=10,
                error="invalid JSON output: unexpected character",
            )
        ]
        report = markdown(scan)
        self.assertIn("Dependency version checks could not finish", report)
        self.assertIn("returned information Forgewatch could not read", report)
        self.assertIn("Failure message: invalid JSON output", report)
        scan.scanner_runs.append(ScannerRun("gitleaks", "1", "passed", "working tree", 1))
        report = markdown(scan)
        self.assertLess(report.index("| Exposed secret checks"), report.index("> **Why"))


if __name__ == "__main__":
    unittest.main()
