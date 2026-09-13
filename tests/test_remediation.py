import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from forgewatch.remediation import detect_reverse_tabnabbing, prepare_fix
from forgewatch.models import ScannerRun
from forgewatch.store import Store

from helpers import finding, init_fixture_repo, result


class RemediationTests(unittest.TestCase):
    def test_fixture_fails_before_fix_passes_after_and_records_blocked_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sha = init_fixture_repo(root)
            item = finding()
            store = Store(root / ".forgewatch" / "state.db")
            store.record_scan(result(item, sha), True)
            config = {
                "repository": {"slug": "owner/repo", "default_branch": "main"},
                "policy": {"fix_generation": "automatic"},
                "scanners": {"semgrep": {"enabled": True}},
                "execution": {"isolation": "container", "validation_commands": ["false"]},
                "state": {"artifacts": ".forgewatch/artifacts"},
            }
            with patch("forgewatch.remediation.shutil.which", return_value=None), patch(
                "forgewatch.remediation.run_configured_scanner",
                return_value=ScannerRun("semgrep", "1.177.0", "passed", "fixture", 1),
            ):
                artifact = prepare_fix(root, config, store, item.fingerprint, sha)
            metadata = json.loads((artifact / "metadata.json").read_text(encoding="utf-8"))
            patch_text = (artifact / "change.patch").read_text(encoding="utf-8")
            self.assertEqual(metadata["regression_check"]["before"], "failed")
            self.assertEqual(metadata["regression_check"]["after"], "passed")
            self.assertEqual(metadata["security_rescan"]["status"], "passed")
            self.assertEqual(metadata["validation_status"], "blocked")
            self.assertIn("rel=\"noopener noreferrer\"", patch_text)
            store.close()

    def test_unsuccessful_remediation_does_not_create_an_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sha = init_fixture_repo(root)
            item = finding(line=99)
            store = Store(root / ".forgewatch" / "state.db")
            store.record_scan(result(item, sha), True)
            config = {
                "repository": {"slug": "owner/repo", "default_branch": "main"},
                "policy": {"fix_generation": "automatic"},
                "execution": {"isolation": "container"},
                "state": {"artifacts": ".forgewatch/artifacts"},
            }
            with self.assertRaisesRegex(ValueError, "expected one"):
                prepare_fix(root, config, store, item.fingerprint, sha)
            self.assertFalse((root / ".forgewatch" / "artifacts").exists())
            store.close()


if __name__ == "__main__":
    unittest.main()
