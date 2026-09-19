from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from forgewatch.dashboard import DashboardController
from forgewatch.store import Store
from helpers import init_fixture_repo


class DashboardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.repository = self.root / "sample-repository"
        self.repository.mkdir()
        init_fixture_repo(self.repository)
        self.store = Store(self.root / ".forgewatch" / "state.db")
        self.config = {
            "schema_version": 1,
            "_config_dir": str(self.root),
            "repository": {"slug": "local/default", "default_branch": "main"},
            "scanners": {},
        }
        self.controller = DashboardController(
            self.config, self.store, self.root / ".forgewatch" / "dashboard.json"
        )

    def tearDown(self) -> None:
        self.controller.close()
        self.store.close()
        self.temporary.cleanup()

    def test_repository_selection_and_frequency_are_persisted(self) -> None:
        repository = self.controller.add_repository(
            {"path": str(self.repository), "slug": "owner/project", "frequency": "manual"}
        )
        self.assertEqual(repository["slug"], "owner/project")
        self.assertIsNone(repository["next_scan_at"])

        updated = self.controller.update_repository(repository["id"], {"frequency": "daily"})
        self.assertEqual(updated["frequency"], "daily")
        self.assertGreater(updated["next_scan_at"], time.time())

        restored = DashboardController(
            self.config, self.store, self.root / ".forgewatch" / "dashboard.json"
        )
        try:
            self.assertEqual(restored.public_state()["repositories"][0]["frequency"], "daily")
        finally:
            restored.close()

    def test_manual_scan_creates_a_plain_language_report(self) -> None:
        repository = self.controller.add_repository(
            {"path": str(self.repository), "slug": "owner/project", "frequency": "manual"}
        )
        self.controller.start_scan(repository["id"])
        deadline = time.time() + 5
        while time.time() < deadline:
            job = self.controller.public_state()["repositories"][0]["job"]
            if job["status"] not in {"queued", "running"}:
                break
            time.sleep(0.02)
        self.assertEqual(job["status"], "finished")
        report = self.controller.latest_report(repository["id"])
        self.assertEqual(report["headline"], "The scan could not finish")
        self.assertIn("Do not treat this result as an all-clear", report["next_step"])
        self.assertTrue(Path(report["report_directory"], "scan.md").is_file())


if __name__ == "__main__":
    unittest.main()
