import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from forgewatch.guidance import enrich_guidance
from forgewatch.models import Finding, Location
from helpers import finding


class GuidanceTests(unittest.TestCase):
    def dependency(self, name="vite", ecosystem="npm"):
        return Finding(
            scanner="osv-scanner", rule_id=f"GHSA-example:{name}", category="dependency",
            severity="high", confidence="high", title=f"{name} 1.0.0: security issue",
            explanation="A known issue", remediation="Update it", locations=[Location("app/package-lock.json")],
            dependency={"name": name, "version": "1.0.0", "ecosystem": ecosystem, "fixed_versions": ["1.0.1"]},
        )

    @patch("subprocess.run", side_effect=AssertionError("Project code must never execute"))
    def test_direct_dependency_uses_real_manifest_and_existing_scripts_only(self, _run):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app").mkdir()
            (root / "app/package.json").write_text(json.dumps({"devDependencies": {"vite": "^1.0.0"}, "scripts": {"build": "vite build", "test": "vitest"}}))
            (root / "app/package-lock.json").write_text("{}")
            item = self.dependency()
            enrich_guidance(root, [item])
        guidance = item.fix_guidance
        self.assertIn("app/package.json (devDependencies)", " ".join(guidance["steps"]))
        self.assertIn("1.0.1", " ".join(guidance["steps"]))
        self.assertEqual(guidance["working_directory"], "app")
        self.assertEqual(guidance["commands"], ["npm explain vite", "npm run test", "npm run build"])
        self.assertIn("not an applied or tested patch", guidance["disclaimer"])

    def test_transitive_dependency_points_to_parent_without_blind_install(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app").mkdir()
            (root / "app/package.json").write_text('{"dependencies":{"vite":"1.0.0"},"packageManager":"pnpm@9.0.0"}')
            (root / "app/package-lock.json").write_text(json.dumps({"packages": {"node_modules/vite": {"dependencies": {"esbuild": "1.0.0"}}}}))
            item = self.dependency("esbuild")
            enrich_guidance(root, [item])
        self.assertIn("node_modules/vite", " ".join(item.fix_guidance["basis"]))
        self.assertIn("parent package", " ".join(item.fix_guidance["steps"]))
        self.assertEqual(item.fix_guidance["commands"], ["pnpm why esbuild"])
        self.assertNotIn("install", " ".join(item.fix_guidance["commands"]))

    def test_non_npm_dependency_does_not_get_javascript_upgrade_advice(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "package.json").write_text('{"dependencies":{"vite":"1.0.0"}}')
            item = self.dependency("vite", "PyPI")
            item.dependency["fixed_versions"] = []
            enrich_guidance(root, [item])
        self.assertIn("did not supply a fixed release", " ".join(item.fix_guidance["steps"]))
        self.assertFalse(item.fix_guidance["commands"])
        self.assertNotIn("devDependencies", " ".join(item.fix_guidance["steps"]))

    def test_secret_advice_never_copies_source_or_secret_value(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            token = "gh" + "p_" + "A" * 24
            (root / "config.js").write_text(f'const token = "{token}";')
            item = finding("config.js")
            item.category = "secret"
            enrich_guidance(root, [item])
        text = json.dumps(item.fix_guidance)
        self.assertNotIn(token, text)
        self.assertIn("revoke or rotate", text)

    def test_manifest_symlink_cannot_read_outside_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            outside = Path(directory) / "outside.json"
            outside.write_text('{"scripts":{"test":"outside-command"}}')
            (root / "package.json").symlink_to(outside)
            item = finding()
            enrich_guidance(root, [item])
        self.assertNotIn("outside-command", json.dumps(item.fix_guidance))
        self.assertFalse(item.fix_guidance["commands"])

    def test_code_fix_identifies_exact_file_and_preserves_existing_attributes(self):
        with tempfile.TemporaryDirectory() as directory:
            item = finding("src/Page.tsx", 18)
            enrich_guidance(Path(directory), [item])
        steps = " ".join(item.fix_guidance["steps"])
        self.assertIn("src/Page.tsx around line 18", steps)
        self.assertIn('rel="noopener noreferrer"', steps)
        self.assertIn("preserve any existing rel", steps)


if __name__ == "__main__":
    unittest.main()
