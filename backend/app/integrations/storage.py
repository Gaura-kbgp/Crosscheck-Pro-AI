from supabase import create_client, Client
from app.core.config import settings

class StorageService:
    def __init__(self):
        if settings.APP_ENV != "test" and settings.SUPABASE_URL and settings.SUPABASE_URL != "https://placeholder.supabase.co":
            self.client: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
        else:
            self.client = None
        self.bucket_name = settings.SUPABASE_STORAGE_BUCKET

    def upload_file(self, path: str, file_bytes: bytes, content_type: str) -> None:
        if not self.client:
            return
        self.client.storage.from_(self.bucket_name).upload(
            path,
            file_bytes,
            file_options={"content-type": content_type}
        )

    def delete_file(self, path: str) -> None:
        if not self.client:
            return
        self.client.storage.from_(self.bucket_name).remove([path])

    def get_file(self, path: str) -> bytes:
        if not self.client:
            return b"mock file bytes"
        return self.client.storage.from_(self.bucket_name).download(path)

    def create_signed_url(self, path: str, expires_in: int = 3600) -> str:
        if not self.client:
            return f"https://mock-storage.local/{self.bucket_name}/{path}"
        res = self.client.storage.from_(self.bucket_name).create_signed_url(path, expires_in)
        if hasattr(res, "get"):
            return res.get("signedURL") or res.get("signedUrl")
        return res['signedURL']
