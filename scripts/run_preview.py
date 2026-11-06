"""Arranca una vista previa aislada sin cambiar la configuracion PostgreSQL."""

import json
import os
import socket
import sys
from urllib.error import URLError
from urllib.request import urlopen
from pathlib import Path

HOST = "127.0.0.1"
PORT = int(os.getenv("LUMORA_PREVIEW_PORT", "8011"))


def _port_in_use() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        return probe.connect_ex((HOST, PORT)) == 0


def _lumora_is_running() -> bool:
    try:
        with urlopen(f"http://{HOST}:{PORT}/health", timeout=2) as response:
            payload = json.load(response)
        return payload.get("service") == "Lumora Roleplay API"
    except (OSError, URLError, ValueError):
        return False


if _port_in_use():
    if _lumora_is_running():
        print(f"Lumora ya esta ejecutandose en http://{HOST}:{PORT}")
        raise SystemExit(0)
    raise SystemExit(
        f"El puerto {PORT} esta ocupado por otra aplicacion. "
        "Define LUMORA_PREVIEW_PORT con un puerto libre."
    )

os.environ.setdefault("DATABASE_URL", "sqlite:///./preview_lumora_v2.db")
os.environ.setdefault("AUTO_CREATE_TABLES", "true")
os.environ.setdefault("AI_PROVIDER", "ollama")
os.environ.setdefault("ALLOW_DEV_AUTH", "true")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import uvicorn
from app.main import app


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
