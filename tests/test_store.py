import datetime as dt
import tempfile
import unittest
import uuid
from pathlib import Path

from forgewatch.models import ScanResult, ScannerRun
from forgewatch.store import Store

from helpers import finding, result


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.directory.name) / "state.db")

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def clean_result(self, sha: str, status: str = "clean") -> ScanResult:
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        return ScanResult(
            str(uuid.uuid4()), "owner/repo", sha, "push", "main", now, now, status,
            [ScannerRun("semgrep", "1", "passed" if status == "clean" else "failed", "fixture", 1)], [],
        )

    def test_dismissal_persists_while_present_and_recurrence_reopens(self):
        item = finding()
        self.store.record_scan(result(item), True)
        self.store.dismiss("owner/repo", item.fingerprint, "Not reachable in the fixture", "kelvin", "now")
        self.store.record_scan(result(finding(), sha="b" * 40), True)
        self.assertEqual(self.store.get_finding("owner/repo", item.fingerprint)["status"], "dismissed")
        self.store.record_scan(self.clean_result("c" * 40), True)
        self.assertEqual(self.store.get_finding("owner/repo", item.fingerprint)["present"], 0)
        self.store.record_scan(result(finding(), sha="d" * 40), True)
        row = self.store.get_finding("owner/repo", item.fingerprint)
        self.assertEqual(row["status"], "open")
        self.assertEqual(row["dismissal_reason"], None)

    def test_incomplete_default_branch_scan_does_not_resolve_findings(self):
        item = finding()
        self.store.record_scan(result(item), True)
        self.store.record_scan(self.clean_result("b" * 40, "incomplete"), True)
        row = self.store.get_finding("owner/repo", item.fingerprint)
        self.assertEqual(row["status"], "open")
        self.assertEqual(row["present"], 1)


if __name__ == "__main__":
    unittest.main()
