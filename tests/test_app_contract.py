from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AppContractTests(unittest.TestCase):

    def test_requirements_pin_streamlit_and_pandas(self):
        requirements = (
            ROOT / "requirements.txt"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "streamlit==1.61.1",
            requirements,
        )
        self.assertIn(
            "pandas==3.0.5",
            requirements,
        )

    def test_env_example_matches_pulse_database_contract(self):
        lines = (
            ROOT / ".env.example"
        ).read_text(encoding="utf-8").splitlines()

        keys = {
            line.split("=", 1)[0]
            for line in lines
            if line and not line.startswith("#") and "=" in line
        }

        expected = {
            "PULSE_DB_HOST",
            "PULSE_DB_PORT",
            "PULSE_DB_NAME",
            "PULSE_DB_USER",
            "PULSE_DB_PASSWORD",
            "PULSE_DB_CONNECT_TIMEOUT",
        }

        self.assertEqual(keys, expected)

        legacy_keys = {
            key
            for key in keys
            if key.startswith("DB_")
        }

        self.assertEqual(
            legacy_keys,
            set(),
        )

    def test_phase7_contract_preserves_synthetic_and_frozen_boundaries(self):
        contract = (
            ROOT / "docs" / "phase7-productisation-contract.md"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "synthetic customer behaviour",
            contract.lower(),
        )
        self.assertIn(
            "behavioural_logistic",
            contract,
        )
        self.assertIn(
            "OPEN",
            contract.upper(),
        )
        self.assertIn(
            "ec1eadb21395b8dfda95399766e1993781c95b9621d8c6d500c9a0a1f429737e",
            contract,
        )


if __name__ == "__main__":
    unittest.main()