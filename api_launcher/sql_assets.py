from __future__ import annotations

import re


VALID_SQL_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")


def validate_sql_identifier(name: str) -> str:
    value = name.strip()
    if not VALID_SQL_IDENTIFIER.fullmatch(value):
        raise ValueError(f"Unsafe SQL identifier: {name!r}")
    return value


def database_uninstall_command(engine: str, database_name: str) -> str:
    engine = engine.strip().lower()
    database_name = validate_sql_identifier(database_name)
    if engine in {"mysql", "mariadb"}:
        return f"DROP DATABASE IF EXISTS `{database_name}`;"
    if engine in {"postgres", "postgresql"}:
        return f'DROP DATABASE IF EXISTS "{database_name}";'
    raise ValueError(f"Unsupported database engine for uninstall command: {engine}")
