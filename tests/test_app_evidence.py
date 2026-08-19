from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from src.app.evidence import (
    EXPECTED_PHASE6_FINAL_RESULTS_SHA256,
    EvidenceIntegrityError,
    load_phase5_evidence,
    load_phase6_evidence,
    resolve_repo_path,
    sha256_file,
)


class AppEvidenceTests(unittest.TestCase):

    def test_sha256_file_matches_hashlib(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.txt"
            path.write_bytes(b"pulse-evidence")

            expected = hashlib.sha256(
                b"pulse-evidence"
            ).hexdigest()

            self.assertEqual(
                sha256_file(path),
                expected,
            )

    def test_repository_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            with self.assertRaises(EvidenceIntegrityError):
                resolve_repo_path(
                    "../outside.json",
                    repo_root=root,
                )

    def test_phase5_evidence_is_synthetic_and_phase_locked(self):
        payload = load_phase5_evidence()

        self.assertEqual(payload["phase"], 5)
        self.assertTrue(payload["synthetic_data"])
        self.assertEqual(payload["experiment_count"], 3)
        self.assertEqual(
            payload["statistically_detectable_result_count"],
            0,
        )

    def test_phase6_locked_model_and_calibration_are_preserved(self):
        evidence = load_phase6_evidence()
        manifest = evidence["manifest"]

        self.assertEqual(
            manifest["selected_model"],
            "behavioural_logistic",
        )
        self.assertEqual(
            manifest["calibration"],
            "uncalibrated",
        )

    def test_phase6_final_results_hash_is_verified(self):
        evidence = load_phase6_evidence()

        self.assertEqual(
            evidence["verified_final_results_sha256"],
            EXPECTED_PHASE6_FINAL_RESULTS_SHA256,
        )


if __name__ == "__main__":
    unittest.main()