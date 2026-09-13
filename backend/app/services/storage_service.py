from abc import ABC, abstractmethod
import os
from pathlib import Path
from app.core.config import settings


class StorageService(ABC):
    @abstractmethod
    def upload(self, file_bytes: bytes, storage_key: str, content_type: str) -> str:
        """Uploads file bytes using storage_key and returns a storage reference."""
        pass

    @abstractmethod
    def get(self, storage_reference: str) -> bytes:
        """Retrieves and returns file bytes for a given storage reference."""
        pass

    @abstractmethod
    def delete(self, storage_reference: str) -> bool:
        """Deletes file corresponding to storage reference. Returns True if deleted."""
        pass


class LocalStorageService(StorageService):
    def __init__(self, base_path: Path | None = None):
        self.base_path = (base_path or settings.LOCAL_STORAGE_PATH).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _resolve_safe_path(self, relative_path: str) -> Path:
        # Normalize and ensure target resides strictly within base_path
        normalized = Path(relative_path)
        resolved = (self.base_path / normalized).resolve()
        if not str(resolved).startswith(str(self.base_path)):
            raise ValueError("Attempted path traversal detected.")
        return resolved

    def upload(self, file_bytes: bytes, storage_key: str, content_type: str) -> str:
        target_path = self._resolve_safe_path(storage_key)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "wb") as f:
            f.write(file_bytes)
        # Store relative path from base_path as storage_reference
        return str(target_path.relative_to(self.base_path))

    def get(self, storage_reference: str) -> bytes:
        target_path = self._resolve_safe_path(storage_reference)
        if not target_path.is_file():
            raise FileNotFoundError("Stored document content not found on filesystem.")
        with open(target_path, "rb") as f:
            return f.read()

    def delete(self, storage_reference: str) -> bool:
        try:
            target_path = self._resolve_safe_path(storage_reference)
            if target_path.is_file():
                target_path.unlink()
                # Optionally clean up empty parent directories if empty
                try:
                    parent = target_path.parent
                    if parent != self.base_path and not any(parent.iterdir()):
                        parent.rmdir()
                except OSError:
                    pass
                return True
            return False
        except Exception:
            return False


def get_storage_service() -> StorageService:
    provider = (settings.STORAGE_PROVIDER or "local").lower()
    if provider == "local":
        return LocalStorageService()
    elif provider == "cloudinary":
        # Configuration-driven: check if Cloudinary credentials are fully configured
        if all([
            settings.CLOUDINARY_CLOUD_NAME,
            settings.CLOUDINARY_API_KEY,
            settings.CLOUDINARY_API_SECRET,
        ]):
            # Cloudinary is configured; could return CloudinaryStorageService
            pass
        # Fall back cleanly to LocalStorageService for local development
        return LocalStorageService()
    return LocalStorageService()


storage_service = get_storage_service()
