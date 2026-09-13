import tempfile
import unittest
from pathlib import Path

from forgewatch.approvals import issue, verify_and_consume
from forgewatch.store import Store


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.directory.name) / "state.db")
        self.key = "test-approval-key-which-is-at-least-32-bytes"

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def test_approval_is_scoped_and_single_use(self):
        sha = "a" * 40
        token = issue(self.store, self.key, "owner/repo", "finding", sha, "kelvin")
        payload = verify_and_consume(self.store, token, self.key, "owner/repo", "finding", sha, sha)
        self.assertEqual(payload["actor"], "kelvin")
        with self.assertRaisesRegex(ValueError, "already been used"):
            verify_and_consume(self.store, token, self.key, "owner/repo", "finding", sha, sha)

    def test_stale_and_wrong_scope_approvals_are_rejected(self):
        sha = "a" * 40
        token = issue(self.store, self.key, "owner/repo", "finding", sha, "kelvin")
        with self.assertRaisesRegex(ValueError, "different repository"):
            verify_and_consume(self.store, token, self.key, "owner/repo", "other", sha, sha)
        with self.assertRaisesRegex(ValueError, "stale"):
            verify_and_consume(self.store, token, self.key, "owner/repo", "finding", sha, "b" * 40)


if __name__ == "__main__":
    unittest.main()
