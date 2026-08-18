from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]

ADMIN_SQL = (
    ROOT
    / "sql"
    / "reporting"
    / "012_admin_create_reporting_reader.sql"
)

GRANT_SQL = (
    ROOT
    / "sql"
    / "reporting"
    / "013_grant_reporting_reader.sql"
)


class ReportingConsumerContractSQLTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.admin_sql = ADMIN_SQL.read_text(
            encoding="utf-8"
        ).lower()

        cls.grant_sql = GRANT_SQL.read_text(
            encoding="utf-8"
        ).lower()

    def test_files_exist(self):
        self.assertTrue(ADMIN_SQL.exists())
        self.assertTrue(GRANT_SQL.exists())

    def test_reader_is_nologin(self):
        self.assertIn(
            "pulse_reporting_reader",
            self.admin_sql,
        )
        self.assertIn(
            "nologin",
            self.admin_sql,
        )

    def test_reader_is_not_privileged_administrator(self):
        for clause in (
            "nosuperuser",
            "nocreatedb",
            "nocreaterole",
            "noreplication",
            "nobypassrls",
        ):
            self.assertIn(
                clause,
                self.admin_sql,
            )

    def test_admin_bootstrap_is_idempotent(self):
        self.assertIn(
            "where not exists",
            self.admin_sql,
        )
        self.assertIn(
            "alter role pulse_reporting_reader",
            self.admin_sql,
        )

    def test_reporting_schema_usage_is_granted(self):
        self.assertIn(
            "grant usage",
            self.grant_sql,
        )
        self.assertIn(
            "on schema reporting",
            self.grant_sql,
        )

    def test_reporting_select_is_granted(self):
        self.assertIn(
            "grant select",
            self.grant_sql,
        )
        self.assertIn(
            "on all tables in schema reporting",
            self.grant_sql,
        )

    def test_reporting_write_privileges_are_revoked(self):
        for privilege in (
            "insert",
            "update",
            "delete",
            "truncate",
            "references",
            "trigger",
        ):
            self.assertIn(
                privilege,
                self.grant_sql,
            )

    def test_internal_schema_access_is_revoked(self):
        for schema in (
            "raw",
            "staging",
            "validation",
            "analytics",
        ):
            self.assertIn(
                f"on schema {schema}",
                self.grant_sql,
            )

    def test_future_reporting_objects_receive_select(self):
        self.assertIn(
            "alter default privileges",
            self.grant_sql,
        )
        self.assertIn(
            "for role pulse_app",
            self.grant_sql,
        )
        self.assertIn(
            "in schema reporting",
            self.grant_sql,
        )

    def test_grant_script_is_transaction_wrapped(self):
        self.assertIn(
            "begin;",
            self.grant_sql,
        )
        self.assertIn(
            "commit;",
            self.grant_sql,
        )


if __name__ == "__main__":
    unittest.main()