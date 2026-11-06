from pydantic import BaseModel


class UploadedImage(BaseModel):
    url: str
    storage_path: str
    content_type: str
    size: int
