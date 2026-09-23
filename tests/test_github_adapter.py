import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from forgewatch.github_app import GitHubAppClient
from forgewatch.service import event_target


class GitHubAdapterTests(unittest.TestCase):
    def test_webhook_target_carries_repository_sha_ref_and_default_branch(self):
        payload = {
            "repository": {"full_name": "acme/widget", "default_branch": "trunk"},
            "after": "a" * 40,
            "ref": "refs/heads/trunk",
        }
        self.assertEqual(
            event_target("push", payload),
            ("acme/widget", "a" * 40, "refs/heads/trunk", "push", "trunk"),
        )

    def test_dispatch_payload_is_portable_to_an_installed_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            key = Path(directory) / "app.pem"
            key.write_text("unused in mocked request", encoding="utf-8")
            client = GitHubAppClient("123", "456", key)
            with patch.object(client, "installation_token", return_value="installation-token"), patch.object(
                client, "_request"
            ) as request:
                client.dispatch_scan(
                    "example/forgewatch",
                    "forgewatch_scan",
                    "acme/widget",
                    "b" * 40,
                    "refs/heads/trunk",
                    "push",
                    "delivery-1",
                    "trunk",
                )
            payload = request.call_args.args[3]["client_payload"]
            self.assertEqual(payload["repository"], "acme/widget")
            self.assertEqual(payload["target_owner"], "acme")
            self.assertEqual(payload["target_name"], "widget")
            self.assertEqual(payload["default_branch"], "trunk")


if __name__ == "__main__":
    unittest.main()
