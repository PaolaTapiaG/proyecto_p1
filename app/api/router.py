from fastapi import APIRouter

from app.modules.administration.router import router as administration_router
from app.modules.auth.router import router as auth_router
from app.modules.characters.router import router as characters_router
from app.modules.conversations.router import router as conversations_router
from app.modules.personas.router import router as personas_router
from app.modules.subscriptions.router import router as subscriptions_router
from app.modules.usage.router import router as usage_router
from app.modules.uploads.router import router as uploads_router
from app.modules.users.router import router as users_router


api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(personas_router)
api_router.include_router(characters_router, prefix="/bots")
api_router.include_router(characters_router, prefix="/characters", include_in_schema=False)
api_router.include_router(conversations_router)
api_router.include_router(usage_router)
api_router.include_router(subscriptions_router)
api_router.include_router(administration_router)
api_router.include_router(uploads_router)
