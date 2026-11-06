"""Crea Lumora, habilita pgvector y ejecuta Alembic sin guardar la contrasena."""

import getpass
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote_plus

import psycopg
from psycopg import sql


ROOT = Path(__file__).resolve().parents[1]
PG_BIN = Path(os.getenv("PG_BIN", r"C:\Program Files\PostgreSQL\17\bin"))
HOST = os.getenv("PGHOST", "127.0.0.1")
PORT = int(os.getenv("PGPORT", "5432"))
USER = os.getenv("PGUSER", "postgres")
DATABASE = os.getenv("PGDATABASE", "Lumora")


def vector_control_file() -> Path | None:
    pg_config = PG_BIN / "pg_config.exe"
    if not pg_config.exists():
        return None
    sharedir = subprocess.check_output(
        [str(pg_config), "--sharedir"], text=True, encoding="utf-8"
    ).strip()
    return Path(sharedir) / "extension" / "vector.control"


def main() -> int:
    control = vector_control_file()
    if not control or not control.exists():
        print("pgvector no esta instalado en PostgreSQL 17.")
        print("Instalalo primero y confirma que exista:")
        print(r"C:\Program Files\PostgreSQL\17\share\extension\vector.control")
        return 2

    password = os.getenv("PGPASSWORD") or getpass.getpass(
        f"Contrasena de {USER} en PostgreSQL: "
    )
    connection_options = {
        "host": HOST,
        "port": PORT,
        "user": USER,
        "password": password,
    }
    with psycopg.connect(dbname="postgres", **connection_options) as connection:
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT datname FROM pg_database WHERE lower(datname) = lower(%s)",
                (DATABASE,),
            )
            existing = cursor.fetchone()
            actual_database = existing[0] if existing else DATABASE
            if not existing:
                cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DATABASE)))
                print(f"Base {DATABASE} creada.")
            else:
                print(f"Base {actual_database} encontrada.")

    with psycopg.connect(dbname=actual_database, **connection_options) as connection:
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cursor.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            print(f"pgvector habilitado: {cursor.fetchone()[0]}")

    database_url = (
        f"postgresql+psycopg://{quote_plus(USER)}:{quote_plus(password)}"
        f"@{HOST}:{PORT}/{quote_plus(actual_database)}"
    )
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    environment["AUTO_CREATE_TABLES"] = "false"
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env=environment,
        check=True,
    )
    print(f"Lumora quedo migrada en PostgreSQL: {actual_database}")
    print(r"Siguiente paso: python scripts\configure_postgres.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
