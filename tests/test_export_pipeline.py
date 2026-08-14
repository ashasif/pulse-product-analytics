"""End-to-end tests for the Pulse Phase 2 export pipeline."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.generation.export_pipeline import (
    DATASET_SCHEMAS,
    PRIMARY_KEYS,
    RAW_FILENAMES,
    export_datasets,
    generate_all_datasets,
    get_default_installation_count,
    validate_dataset_bundle,
)
from src.generation.installations import load_simulation_config


class SyntheticDataExportPipelineTests(unittest.TestCase):
    """Validate orchestration, integration, determinism and raw export."""

    SAMPLE_INSTALLATIONS = 1_000

    @classmethod
    def setUpClass(cls):
        cls.datasets = generate_all_datasets(
            installation_count=cls.SAMPLE_INSTALLATIONS,
        )
        cls.summary = validate_dataset_bundle(
            cls.datasets,
            expected_installation_count=cls.SAMPLE_INSTALLATIONS,
        )

    def test_bundle_contains_every_approved_dataset(self):
        self.assertEqual(
            set(self.datasets),
            set(DATASET_SCHEMAS),
        )
        self.assertEqual(
            self.summary["installations"],
            self.SAMPLE_INSTALLATIONS,
        )

    def test_every_dataset_has_exact_schema_and_unique_primary_key(self):
        for dataset_name, rows in self.datasets.items():
            expected_fields = set(DATASET_SCHEMAS[dataset_name])
            primary_key = PRIMARY_KEYS[dataset_name]

            for row in rows:
                self.assertEqual(
                    set(row),
                    expected_fields,
                )

            identifiers = [
                row[primary_key]
                for row in rows
            ]
            self.assertEqual(
                len(identifiers),
                len(set(identifiers)),
            )

    def test_final_product_events_include_subscription_lifecycle(self):
        event_counts = Counter(
            row["event_name"]
            for row in self.datasets["product_events"]
        )

        self.assertEqual(
            event_counts["app_install"],
            len(self.datasets["installations"]),
        )
        self.assertEqual(
            event_counts["signup"],
            len(self.datasets["users"]),
        )
        self.assertEqual(
            event_counts["trial_started"],
            len(self.datasets["subscriptions"]),
        )

        successful_initial = sum(
            row["transaction_type"] == "initial_charge"
            and row["payment_status"] == "succeeded"
            for row in self.datasets["subscription_transactions"]
        )
        successful_renewals = sum(
            row["transaction_type"] == "renewal"
            and row["payment_status"] == "succeeded"
            for row in self.datasets["subscription_transactions"]
        )
        failed_transactions = sum(
            row["payment_status"] == "failed"
            for row in self.datasets["subscription_transactions"]
        )

        self.assertEqual(
            event_counts["subscription_started"],
            successful_initial,
        )
        self.assertEqual(
            event_counts["subscription_renewed"],
            successful_renewals,
        )
        self.assertEqual(
            event_counts["payment_failed"],
            failed_transactions,
        )

    def test_cross_dataset_referential_integrity(self):
        installation_ids = {
            row["installation_id"]
            for row in self.datasets["installations"]
        }
        user_ids = {
            row["user_id"]
            for row in self.datasets["users"]
        }
        subscription_ids = {
            row["subscription_id"]
            for row in self.datasets["subscriptions"]
        }

        self.assertTrue(
            all(
                row["installation_id"] in installation_ids
                for row in self.datasets["users"]
            )
        )
        self.assertTrue(
            all(
                row["installation_id"] in installation_ids
                for row in self.datasets["product_events"]
            )
        )
        self.assertTrue(
            all(
                row["user_id"] is None
                or row["user_id"] in user_ids
                for row in self.datasets["product_events"]
            )
        )
        self.assertTrue(
            all(
                row["user_id"] in user_ids
                for row in self.datasets["subscriptions"]
            )
        )
        self.assertTrue(
            all(
                row["subscription_id"] in subscription_ids
                for row in self.datasets["subscription_transactions"]
            )
        )
        self.assertTrue(
            all(
                row["user_id"] in user_ids
                for row in self.datasets["experiment_assignments"]
            )
        )

    def test_generation_is_deterministic_end_to_end(self):
        repeated = generate_all_datasets(
            installation_count=self.SAMPLE_INSTALLATIONS,
        )
        self.assertEqual(
            repeated,
            self.datasets,
        )

    def test_export_writes_stable_named_csv_files_with_expected_headers(self):
        with TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            paths = export_datasets(
                self.datasets,
                output_dir=output_dir,
            )

            self.assertEqual(
                set(paths),
                set(DATASET_SCHEMAS),
            )

            for dataset_name, path in paths.items():
                self.assertEqual(
                    path.name,
                    RAW_FILENAMES[dataset_name],
                )
                self.assertTrue(path.is_file())

                with path.open(
                    "r",
                    encoding="utf-8",
                    newline="",
                ) as file:
                    reader = csv.reader(file)
                    header = next(reader)

                self.assertEqual(
                    header,
                    list(DATASET_SCHEMAS[dataset_name]),
                )

    def test_export_is_byte_stable_for_same_dataset_bundle(self):
        with TemporaryDirectory() as first_directory, TemporaryDirectory() as second_directory:
            first_paths = export_datasets(
                self.datasets,
                output_dir=Path(first_directory),
            )
            second_paths = export_datasets(
                self.datasets,
                output_dir=Path(second_directory),
            )

            for dataset_name in DATASET_SCHEMAS:
                self.assertEqual(
                    first_paths[dataset_name].read_bytes(),
                    second_paths[dataset_name].read_bytes(),
                )

    def test_default_final_installation_count_uses_approved_scale_minimum(self):
        config = load_simulation_config()
        self.assertEqual(
            get_default_installation_count(),
            int(config["scale"]["installations_min"]),
        )


if __name__ == "__main__":
    unittest.main()