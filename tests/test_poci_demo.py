from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "examples" / "poci-witness" / "run_demo.py"


class PoCIDemoTests(unittest.TestCase):
    def test_demo_exports_expected_reports(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw)
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), "--output-dir", str(output), "--check"],
                cwd=ROOT,
                check=False,
                text=True,
                capture_output=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("PASS evidence accepted; tampering challenged", completed.stdout)

            accept = json.loads((output / "accept-report.json").read_text(encoding="utf-8"))
            challenge = json.loads((output / "challenge-report.json").read_text(encoding="utf-8"))
            summary = json.loads((output / "demo-summary.json").read_text(encoding="utf-8"))

            self.assertEqual(accept["decision"], "ACCEPT")
            self.assertEqual(challenge["decision"], "CHALLENGE")
            self.assertEqual(challenge["primary_reason_code"], "RESULT_DIGEST_MISMATCH")
            self.assertTrue(summary["passed"])
            self.assertEqual(len(summary["reports"]), 2)


if __name__ == "__main__":
    unittest.main()
