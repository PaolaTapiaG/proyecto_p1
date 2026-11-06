"""Arranca Vite para la vista previa local de React."""

import os
import subprocess
from pathlib import Path


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    frontend = root / "frontend"
    environment = os.environ.copy()
    environment.setdefault(
        "LUMORA_API_TARGET",
        "http://127.0.0.1:8000" if (root / ".env").exists() else "http://127.0.0.1:8011",
    )
    subprocess.run(
        [
            "node",
            str(frontend / "node_modules" / "vite" / "bin" / "vite.js"),
            "--host",
            "127.0.0.1",
            "--port",
            "5173",
        ],
        cwd=frontend,
        env=environment,
        check=True,
    )
