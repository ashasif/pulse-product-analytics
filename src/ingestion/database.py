"""PostgreSQL connection configuration for Pulse ingestion."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Mapping

import psycopg
from psycopg import Connection


class DatabaseConfigError(ValueError):
    """Raised when PostgreSQL configuration is invalid."""


@dataclass(frozen=True)
class DatabaseConfig:
    """Environment-backed PostgreSQL connection configuration."""

    host: str
    port: int
    dbname: str
    user: str
    password: str
    connect_timeout: int = 10
    application_name: str = "pulse-product-analytics"

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
    ) -> "DatabaseConfig":
        """Build configuration from project-scoped environment variables."""

        values = os.environ if env is None else env

        host = values.get("PULSE_DB_HOST", "localhost").strip()
        dbname = values.get(
            "PULSE_DB_NAME",
            "pulse_warehouse",
        ).strip()
        user = values.get(
            "PULSE_DB_USER",
            "pulse_app",
        ).strip()
        password = values.get("PULSE_DB_PASSWORD", "")

        port_raw = values.get("PULSE_DB_PORT", "5432")
        timeout_raw = values.get(
            "PULSE_DB_CONNECT_TIMEOUT",
            "10",
        )

        if not host:
            raise DatabaseConfigError(
                "PULSE_DB_HOST must not be empty."
            )

        if not dbname:
            raise DatabaseConfigError(
                "PULSE_DB_NAME must not be empty."
            )

        if not user:
            raise DatabaseConfigError(
                "PULSE_DB_USER must not be empty."
            )

        if not password:
            raise DatabaseConfigError(
                "PULSE_DB_PASSWORD is required."
            )

        try:
            port = int(port_raw)
        except ValueError as exc:
            raise DatabaseConfigError(
                "PULSE_DB_PORT must be an integer."
            ) from exc

        if not 1 <= port <= 65535:
            raise DatabaseConfigError(
                "PULSE_DB_PORT must be between 1 and 65535."
            )

        try:
            connect_timeout = int(timeout_raw)
        except ValueError as exc:
            raise DatabaseConfigError(
                "PULSE_DB_CONNECT_TIMEOUT must be an integer."
            ) from exc

        if connect_timeout <= 0:
            raise DatabaseConfigError(
                "PULSE_DB_CONNECT_TIMEOUT must be greater than zero."
            )

        return cls(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password,
            connect_timeout=connect_timeout,
        )

    def connect_kwargs(self) -> dict[str, object]:
        """Return keyword arguments suitable for psycopg.connect()."""

        return {
            "host": self.host,
            "port": self.port,
            "dbname": self.dbname,
            "user": self.user,
            "password": self.password,
            "connect_timeout": self.connect_timeout,
            "application_name": self.application_name,
        }

    def safe_summary(self) -> str:
        """Return connection information without exposing credentials."""

        return (
            f"host={self.host} "
            f"port={self.port} "
            f"dbname={self.dbname} "
            f"user={self.user}"
        )


def connect_database(
    config: DatabaseConfig | None = None,
) -> Connection:
    """Open a PostgreSQL connection using Pulse configuration."""

    resolved = (
        DatabaseConfig.from_env()
        if config is None
        else config
    )

    return psycopg.connect(
        **resolved.connect_kwargs()
    )