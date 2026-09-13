import unittest

from forgewatch.engine import deduplicate
from forgewatch.models import Finding, Location, ScannerRun


class DeduplicationTests(unittest.TestCase):
    def test_cross_scanner_code_findings_with_same_cwe_and_location_merge(self):
        common = dict(
            category="code",
            severity="medium",
            confidence="high",
            title="XSS",
            explanation="x",
            remediation="fix",
            locations=[Location("src/App.tsx", 10, 10)],
            cwes=["CWE-79"],
        )
        first = Finding(scanner="semgrep", rule_id="rule-a", **common)
        second = Finding(scanner="another", rule_id="rule-b", severity="high", **{k: v for k, v in common.items() if k != "severity"})
        values = deduplicate(
            [ScannerRun("semgrep", "1", "findings", "code", 1, [first]), ScannerRun("another", "1", "findings", "code", 1, [second])]
        )
        self.assertEqual(len(values), 1)
        self.assertEqual(values[0].severity, "high")
        self.assertEqual(values[0].source_ids, ["another:rule-b", "semgrep:rule-a"])


if __name__ == "__main__":
    unittest.main()
