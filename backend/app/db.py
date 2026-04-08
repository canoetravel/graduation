import os
from pathlib import Path
from typing import List, Optional

import pymysql


DB_HOST = os.getenv("DB_HOST", "mysql")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "123456")
DB_NAME = os.getenv("DB_NAME", "os_judge")

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"

#数据库连接
def get_db_connection():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def _list_migration_files() -> List[Path]:
    if not MIGRATIONS_DIR.exists():
        return []
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def _split_sql_statements(sql_text: str) -> List[str]:
    parts = []
    for chunk in sql_text.split(";"):
        statement = chunk.strip()
        if statement:
            parts.append(statement)
    return parts


def _ensure_migration_table(conn) -> None:
    create_sql = """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        id INT AUTO_INCREMENT PRIMARY KEY,
        migration_name VARCHAR(255) NOT NULL UNIQUE,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    with conn.cursor() as cur:
        cur.execute(create_sql)


def _applied_migrations(conn) -> set:
    with conn.cursor() as cur:
        cur.execute("SELECT migration_name FROM schema_migrations")
        rows = cur.fetchall()
    return {row["migration_name"] for row in rows}


def _apply_single_migration(conn, migration_file: Path) -> None:
    sql_text = migration_file.read_text(encoding="utf-8")
    statements = _split_sql_statements(sql_text)
    if not statements:
        return

    with conn.cursor() as cur:
        for statement in statements:
            cur.execute(statement)
        cur.execute(
            "INSERT INTO schema_migrations (migration_name) VALUES (%s)",
            (migration_file.name,),
        )


def init_db() -> Optional[str]:
    try:
        with get_db_connection() as conn:
            _ensure_migration_table(conn)
            applied = _applied_migrations(conn)
            for migration_file in _list_migration_files():
                if migration_file.name in applied:
                    continue
                _apply_single_migration(conn, migration_file)
        return None
    except Exception as exc:
        return str(exc)
