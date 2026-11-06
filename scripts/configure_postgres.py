"""Configura la conexion local de Lumora sin mostrar la contrasena."""

import getpass
import os
import re
from pathlib import Path
from urllib.parse import quote

import psycopg


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
ENV_TEMPLATE = ROOT / ".env.example"
HOST = os.getenv("PGHOST", "127.0.0.1")
PORT = int(os.getenv("PGPORT", "5432"))
USER = os.getenv("PGUSER", "postgres")
DATABASE = os.getenv("PGDATABASE", "Lumora")


def _set_value(content: str, key: str, value: str) -> str:
    line = f"{key}={value}"
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    if pattern.search(content):
        return pattern.sub(line, content)
    return f"{content.rstrip()}\n{line}\n"


def main() -> int:
    password = getpass.getpass(f"Contrasena de {USER} en PostgreSQL: ")
    connection_options = {
        "host": HOST,
        "port": PORT,
        "user": USER,
        "password": password,
        "dbname": DATABASE,
    }
    try:
        with psycopg.connect(**connection_options) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
                )
                vector_version = cursor.fetchone()
                cursor.execute("SELECT version_num FROM alembic_version")
                migration_version = cursor.fetchone()
    except psycopg.Error as exc:
        print(f"No se pudo validar PostgreSQL: {exc}")
        return 1

    if not vector_version or not migration_version:
        print("La base no tiene pgvector o las migraciones de Lumora completas.")
        return 2

    content = (
        ENV_FILE.read_text(encoding="utf-8")
        if ENV_FILE.exists()
        else ENV_TEMPLATE.read_text(encoding="utf-8")
    )
    database_url = (
        f"postgresql+psycopg://{quote(USER, safe='')}:{quote(password, safe='')}"
        f"@{HOST}:{PORT}/{quote(DATABASE, safe='')}"
    )
    content = _set_value(content, "DATABASE_URL", database_url)
    content = _set_value(content, "AUTO_CREATE_TABLES", "false")
    ENV_FILE.write_text(content, encoding="utf-8")
    try:
        ENV_FILE.chmod(0o600)
    except OSError:
        pass

    print(f"Conexion guardada localmente en {ENV_FILE}")
    print(f"pgvector: {vector_version[0]}")
    print(f"Migracion: {migration_version[0]}")
    print("Siguiente paso: python index.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
