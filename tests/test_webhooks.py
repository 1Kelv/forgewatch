import hashlib
import hmac
import tempfile
import unittest
from pathlib import Path

from forgewatch.store import Store
from forgewatch.webhooks import accept_delivery


class WebhookTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.directory.name) / "state.db")

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def test_signature_and_delivery_deduplication(self):
        body = b'{"ref":"refs/heads/main"}'
        secret = "webhook-secret"
        signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        accept_delivery(self.store, body, signature, secret, "delivery-1", "push")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            accept_delivery(self.store, body, signature, secret, "delivery-1", "push")
        with self.assertRaisesRegex(ValueError, "invalid"):
            accept_delivery(self.store, body, "sha256=" + "0" * 64, secret, "delivery-2", "push")


if __name__ == "__main__":
    unittest.main()
