import unittest

from forgewatch.redaction import REDACTED, redact, redact_text


class RedactionTests(unittest.TestCase):
    def test_redacts_common_credentials_and_sensitive_keys(self):
        github_token = "gh" + "p_" + "A" * 24
        openai_key = "sk-" + "B" * 24
        output = redact_text(f"Authorization: Bearer abc123 {github_token} {openai_key}")
        self.assertNotIn("abc123", output)
        self.assertNotIn(github_token, output)
        self.assertNotIn(openai_key, output)
        self.assertEqual(redact({"Secret": "visible", "safe": "ok"}), {"Secret": REDACTED, "safe": "ok"})


if __name__ == "__main__":
    unittest.main()
