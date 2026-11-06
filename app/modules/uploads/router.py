import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.core.auth import current_user
from app.core.config import settings
from app.db.models import User
from app.modules.uploads.schemas import UploadedImage


router = APIRouter(prefix="/uploads", tags=["Uploads"])


def _image_extension(content: bytes) -> tuple[str, str] | None:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png", "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return ".jpg", "image/jpeg"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return ".webp", "image/webp"
    return None


@router.post("/images", response_model=UploadedImage, status_code=status.HTTP_201_CREATED)
async def upload_image(
    image: UploadFile = File(...),
    user: User = Depends(current_user),
) -> UploadedImage:
    content = await image.read(settings.max_upload_bytes + 1)
    await image.close()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Image exceeds the 6 MB limit"
        )
    detected = _image_extension(content)
    if not detected:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "Only PNG, JPEG and WebP images are supported",
        )

    extension, content_type = detected
    safe_user_id = re.sub(r"[^A-Za-z0-9_-]", "_", user.id)
    relative_path = Path(safe_user_id) / f"{uuid.uuid4().hex}{extension}"
    media_root = Path(settings.local_media_root).resolve()
    destination = (media_root / relative_path).resolve()
    if media_root not in destination.parents:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid storage path")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)

    url_path = relative_path.as_posix()
    return UploadedImage(
        url=f"/media/{url_path}",
        storage_path=url_path,
        content_type=content_type,
        size=len(content),
    )
