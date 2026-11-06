from urllib.parse import quote

import httpx

from app.core.config import settings


class SupabaseStorageGateway:
    def _configuration(self) -> tuple[str, str]:
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise RuntimeError("Supabase Storage is not configured")
        return settings.supabase_url.rstrip("/"), settings.supabase_service_role_key

    def upload(self, object_path: str, content: bytes, content_type: str) -> str:
        base_url, service_key = self._configuration()
        encoded_path = quote(object_path.strip("/"), safe="/")
        response = httpx.put(
            f"{base_url}/storage/v1/object/{settings.supabase_storage_bucket}/{encoded_path}",
            headers={
                "Authorization": f"Bearer {service_key}",
                "apikey": service_key,
                "Content-Type": content_type,
                "x-upsert": "false",
            },
            content=content,
            timeout=30,
        )
        response.raise_for_status()
        return object_path

    def create_signed_url(self, object_path: str, expires_in: int = 300) -> str:
        base_url, service_key = self._configuration()
        encoded_path = quote(object_path.strip("/"), safe="/")
        response = httpx.post(
            f"{base_url}/storage/v1/object/sign/{settings.supabase_storage_bucket}/{encoded_path}",
            headers={"Authorization": f"Bearer {service_key}", "apikey": service_key},
            json={"expiresIn": expires_in},
            timeout=15,
        )
        response.raise_for_status()
        signed_url = response.json()["signedURL"]
        return signed_url if signed_url.startswith("http") else f"{base_url}/storage/v1{signed_url}"


storage_gateway = SupabaseStorageGateway()
