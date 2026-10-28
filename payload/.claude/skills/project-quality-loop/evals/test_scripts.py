#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DETECT = ROOT / "scripts" / "detect_project.py"
BOOTSTRAP = ROOT / "scripts" / "bootstrap_quality.py"


class SkillScriptTests(unittest.TestCase):
    def test_mixed_web_project_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "package.json").write_text(
                json.dumps(
                    {
                        "scripts": {"build": "next build", "test": "vitest", "e2e": "playwright test"},
                        "dependencies": {"next": "1", "react": "1", "express": "1", "stripe": "1"},
                        "devDependencies": {"@playwright/test": "1", "vitest": "1"},
                    }
                ),
                encoding="utf-8",
            )
            (project / "Dockerfile").write_text("FROM node:22\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(DETECT), "--root", str(project)],
                check=True,
                capture_output=True,
                text=True,
            )
            data = json.loads(result.stdout)
            self.assertIn("mixed-product", data["project_types"])
            self.assertIn("web-ui", data["project_types"])
            self.assertIn("backend-api", data["project_types"])
            self.assertIn("infrastructure-devops", data["project_types"])
            self.assertIn("payment-or-billing", data["risk_signals"])

    def test_bootstrap_is_non_destructive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            subprocess.run(
                [sys.executable, str(BOOTSTRAP), "--root", str(project), "--mode", "audit"],
                check=True,
                capture_output=True,
                text=True,
            )
            manifest = project / ".claude" / "quality" / "manifest.md"
            manifest.write_text("CUSTOM\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(BOOTSTRAP), "--root", str(project), "--mode", "audit"],
                check=True,
                capture_output=True,
                text=True,
            )
            summary = json.loads(result.stdout)
            self.assertEqual(manifest.read_text(encoding="utf-8"), "CUSTOM\n")
            self.assertIn(str(manifest), summary["preserved"])


if __name__ == "__main__":
    unittest.main()
