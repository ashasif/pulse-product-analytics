"""Tests for Pulse PostgreSQL configuration."""

from __future__ import annotations

import unittest

from src.ingestion.database import (
    DatabaseConfig,
    DatabaseConfigError,
)


class DatabaseConfigTests(unittest.TestCase):

    def test_defaults_with_required_password(self):
        config = DatabaseConfig.from_env(
            {
                "PULSE_DB_PASSWORD": "test-password",
            }
        )

        self.assertEqual(
            config.host,
            "localhost",
        )
        self.assertEqual(
            config.port,
            5432,
        )
        self.assertEqual(
            config.dbname,
            "pulse_warehouse",
        )
        self.assertEqual(
            config.user,
            "pulse_app",
        )
        self.assertEqual(
            config.connect_timeout,
            10,
        )

    def test_environment_overrides_defaults(self):
        config = DatabaseConfig.from_env(
            {
                "PULSE_DB_HOST": "db.example",
                "PULSE_DB_PORT": "5544",
                "PULSE_DB_NAME": "warehouse_test",
                "PULSE_DB_USER": "test_user",
                "PULSE_DB_PASSWORD": "secret",
                "PULSE_DB_CONNECT_TIMEOUT": "25",
            }
        )

        self.assertEqual(
            config.host,
            "db.example",
        )
        self.assertEqual(
            config.port,
            5544,
        )
        self.assertEqual(
            config.dbname,
            "warehouse_test",
        )
        self.assertEqual(
            config.user,
            "test_user",
        )
        self.assertEqual(
            config.connect_timeout,
            25,
        )

    def test_password_is_required(self):
        with self.assertRaises(
            DatabaseConfigError
        ):
            DatabaseConfig.from_env({})

    def test_empty_password_is_rejected(self):
        with self.assertRaises(
            DatabaseConfigError
        ):
            DatabaseConfig.from_env(
                {
                    "PULSE_DB_PASSWORD": "",
                }
            )

    def test_invalid_port_is_rejected(self):
        with self.assertRaises(
            DatabaseConfigError
        ):
            DatabaseConfig.from_env(
                {
                    "PULSE_DB_PASSWORD": "secret",
                    "PULSE_DB_PORT": "not-a-number",
                }
            )

    def test_out_of_range_port_is_rejected(self):
        with self.assertRaises(
            DatabaseConfigError
        ):
            DatabaseConfig.from_env(
                {
                    "PULSE_DB_PASSWORD": "secret",
                    "PULSE_DB_PORT": "70000",
                }
            )

    def test_invalid_timeout_is_rejected(self):
        with self.assertRaises(
            DatabaseConfigError
        ):
            DatabaseConfig.from_env(
                {
                    "PULSE_DB_PASSWORD": "secret",
                    "PULSE_DB_CONNECT_TIMEOUT": "zero",
                }
            )

    def test_zero_timeout_is_rejected(self):
        with self.assertRaises(
            DatabaseConfigError
        ):
            DatabaseConfig.from_env(
                {
                    "PULSE_DB_PASSWORD": "secret",
                    "PULSE_DB_CONNECT_TIMEOUT": "0",
                }
            )

    def test_connect_kwargs_are_psycopg_ready(self):
        config = DatabaseConfig.from_env(
            {
                "PULSE_DB_PASSWORD": "secret",
            }
        )

        kwargs = config.connect_kwargs()

        self.assertEqual(
            kwargs["host"],
            "localhost",
        )
        self.assertEqual(
            kwargs["port"],
            5432,
        )
        self.assertEqual(
            kwargs["dbname"],
            "pulse_warehouse",
        )
        self.assertEqual(
            kwargs["user"],
            "pulse_app",
        )
        self.assertEqual(
            kwargs["password"],
            "secret",
        )

    def test_safe_summary_never_contains_password(self):
        config = DatabaseConfig.from_env(
            {
                "PULSE_DB_PASSWORD":
                    "never-show-this-password",
            }
        )

        summary = config.safe_summary()

        self.assertNotIn(
            "never-show-this-password",
            summary,
        )

        self.assertIn(
            "pulse_warehouse",
            summary,
        )

        self.assertIn(
            "pulse_app",
            summary,
        )


if __name__ == "__main__":
    unittest.main()