from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.db.session import create_database, engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.validate_production()
    if settings.auto_create_tables:
        create_database()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="API modular para personajes y conversaciones de roleplay con IA.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
if settings.is_production:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if settings.is_production:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    return response
app.include_router(api_router)
Path(settings.local_media_root).mkdir(parents=True, exist_ok=True)
app.mount(
    "/media",
    StaticFiles(directory=settings.local_media_root, check_dir=False),
    name="media",
)


@app.get("/health", tags=["System"])
def health(response: Response) -> dict[str, object]:
    components = {"database": "ok", "ai": "ready"}
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        components["database"] = "unavailable"

    if settings.ai_provider == "ollama_cloud":
        if not settings.ollama_api_key:
            components["ai"] = "unavailable"
    elif settings.ai_provider == "ollama":
        try:
            response = httpx.get(
                f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=1.5
            )
            response.raise_for_status()
            models = (response.json().get("models") or [])
            available = {item.get("name") for item in models}
            if settings.ollama_chat_model not in available:
                components["ai"] = "model_unavailable"
        except httpx.HTTPError:
            components["ai"] = "unavailable"

    payload = {
        "status": "ok" if all(value in {"ok", "ready"} for value in components.values()) else "degraded",
        "service": settings.app_name,
        "environment": settings.app_env,
        "components": components,
    }
    if payload["status"] == "ok":
        return payload
    response.status_code = 503
    return payload
