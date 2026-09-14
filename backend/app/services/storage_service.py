"""Storage service abstraction for medical document persistence.

Provider selection is controlled exclusively by DOCUMENT_STORAGE_PROVIDER (or the legacy alias
STORAGE_PROVIDER).  Cloudinary is only activated when explicitly configured.

Supported DOCUMENT_STORAGE_PROVIDER values:
  - "local"      : LocalStorageService  (default — safe for tests, no credentials required)
  - "cloudinary" : CloudinaryStorageProvider (production — requires full credential set)

Never switch provider based solely on package installation or heuristics.
"""

import io
import json
import logging
import re
import socket
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import settings
from app.core.provider_errors import (
    ProviderAuthError,
    ProviderConfigError,
    ProviderNetworkError,
    ProviderProcessingError,
    ProviderResponseError,
    execute_with_retry,
    sanitize_secret,
)

logger = logging.getLogger(__name__)

# MIME types accepted by the document pipeline.  Must match medical_document_service.ALLOWED_MIME_TYPES.
_ALLOWED_MIME_TYPES: frozenset = frozenset(
    {"application/pdf", "image/jpeg", "image/png", "image/webp"}
)

# Magic byte signatures for accepted MIME types.
_MAGIC_SIGNATURES: dict = {
    "application/pdf": b"%PDF",
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG",
    "image/webp": b"RIFF",  # RIFF....WEBP — first 4 bytes
}


def _check_magic_bytes(file_bytes: bytes, content_type: str) -> None:
    """Raise ValueError if file_bytes do not match the expected magic bytes for content_type."""
    sig = _MAGIC_SIGNATURES.get(content_type)
    if sig and not file_bytes[: len(sig)].startswith(sig):
        raise ValueError(
            f"File content does not match declared MIME type '{content_type}'."
        )


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


class CloudinaryStorageProvider(StorageService):
    """Production document storage provider using Cloudinary's Upload API.

    Security invariants:
    - public_id is server-generated from the sanitized storage_key (which already contains a UUID).
      Client-supplied filenames never control the Cloudinary resource path.
    - Credentials are stored in private instance attributes and NEVER written to logs or
      included in error messages forwarded to API clients.
    - Only the minimum metadata required for lifecycle management is persisted:
      (provider, public_id, resource_type, format, secure_url).
    - All Cloudinary failures are classified into the existing ProviderError hierarchy.
    - Deletion is scoped to the exact stored public_id; arbitrary paths from user
      input cannot trigger deletion of unrelated Cloudinary resources.
    """

    PROVIDER_NAME = "cloudinary"

    def __init__(
        self,
        cloud_name: str | None = None,
        api_key: str | None = None,
        api_secret: str | None = None,
        folder: str | None = None,
        timeout_seconds: int | None = None,
    ):
        self._cloud_name = cloud_name or settings.CLOUDINARY_CLOUD_NAME
        self._api_key = api_key or settings.CLOUDINARY_API_KEY
        self._api_secret = api_secret or settings.CLOUDINARY_API_SECRET
        self._folder = folder or settings.CLOUDINARY_FOLDER
        self._timeout = timeout_seconds if timeout_seconds is not None else settings.CLOUDINARY_TIMEOUT_SECONDS

        if not all([self._cloud_name, self._api_key, self._api_secret]):
            raise ProviderConfigError(
                "Cloudinary storage provider requires CLOUDINARY_CLOUD_NAME, "
                "CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET to be configured.",
                provider_name=self.PROVIDER_NAME,
            )

        try:
            import cloudinary
            import cloudinary.uploader
            self._cloudinary = cloudinary
            self._uploader = cloudinary.uploader
            # Configure at instance level (SDK uses module-level config but we set it explicitly)
            cloudinary.config(
                cloud_name=self._cloud_name,
                api_key=self._api_key,
                api_secret=self._api_secret,
                secure=True,
            )
        except ImportError as exc:
            raise ProviderConfigError(
                "cloudinary Python SDK is not installed. "
                "Add cloudinary>=1.36.0,<2.0.0 to requirements.txt.",
                provider_name=self.PROVIDER_NAME,
            ) from exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_public_id(self, storage_key: str) -> str:
        """Derive a server-controlled Cloudinary public_id from the sanitized storage_key.

        The storage_key arriving here is already prefixed with a UUID by MedicalDocumentService
        so client filenames cannot influence the final path.  We additionally:
          - Strip any characters invalid for Cloudinary public_id
          - Remove '..' and '.' path traversal components
          - Collapse duplicate slashes
          - Prepend the configured folder
          - Enforce the 255-char Cloudinary limit
        """
        safe_key = re.sub(r"[^a-zA-Z0-9._/\-]", "_", storage_key)
        safe_key = re.sub(r"/+", "/", safe_key).strip("/")
        # Remove path traversal segments explicitly (.., .)
        parts = [p for p in safe_key.split("/") if p not in (".", "..")]
        safe_key = "/".join(parts)
        public_id = f"{self._folder}/{safe_key}"
        if len(public_id) > 255:
            # Truncate but preserve UUID suffix (last 40 chars of the key)
            suffix = safe_key[-40:]
            public_id = f"{self._folder}/truncated_{suffix}"
        return public_id

    def _classify_cloudinary_error(self, exc: Exception) -> None:
        """Re-raise exc as the appropriate ProviderError subclass.

        Credentials are redacted from all error messages.
        """
        err_str = sanitize_secret(str(exc), self._api_key, self._api_secret)

        # Try to import Cloudinary exception types if available
        try:
            from cloudinary.exceptions import AuthorizationRequired, Error as CloudinaryError
            if isinstance(exc, AuthorizationRequired):
                raise ProviderAuthError(
                    f"Cloudinary authentication failed: {err_str}",
                    provider_name=self.PROVIDER_NAME,
                ) from exc
        except ImportError:
            pass

        if isinstance(exc, (socket.timeout, TimeoutError)):
            raise ProviderNetworkError(
                f"Cloudinary request timed out: {err_str}",
                provider_name=self.PROVIDER_NAME,
            ) from exc

        if isinstance(exc, (ConnectionError, OSError)):
            raise ProviderNetworkError(
                f"Cloudinary network error: {err_str}",
                provider_name=self.PROVIDER_NAME,
            ) from exc

        # Check status code embedded in error text for transient 5xx / 429
        msg_lower = err_str.lower()
        if any(code in msg_lower for code in ["500", "502", "503", "504", "429", "rate limit"]):
            raise ProviderProcessingError(
                f"Cloudinary transient server error: {err_str}",
                provider_name=self.PROVIDER_NAME,
            ) from exc

        # Auth-related text in generic errors
        if any(word in msg_lower for word in ["unauthorized", "forbidden", "invalid api", "authentication"]):
            raise ProviderAuthError(
                f"Cloudinary authentication error: {err_str}",
                provider_name=self.PROVIDER_NAME,
            ) from exc

        raise ProviderProcessingError(
            f"Cloudinary API error ({type(exc).__name__}): {err_str}",
            provider_name=self.PROVIDER_NAME,
        ) from exc

    # ------------------------------------------------------------------
    # StorageService interface
    # ------------------------------------------------------------------

    def upload(self, file_bytes: bytes, storage_key: str, content_type: str) -> str:
        """Upload file bytes to Cloudinary.

        Returns a JSON string containing the minimum metadata required for
        subsequent get() and delete() operations:
          {"provider": "cloudinary", "public_id": "...", "resource_type": "...",
           "format": "...", "secure_url": "..."}

        The secure_url is never returned to API clients in responses or written to logs.
        """
        # Validate MIME type
        if content_type not in _ALLOWED_MIME_TYPES:
            raise ProviderResponseError(
                f"Unsupported MIME type for Cloudinary upload: '{content_type}'. "
                f"Allowed: {sorted(_ALLOWED_MIME_TYPES)}",
                provider_name=self.PROVIDER_NAME,
            )

        # Defence-in-depth size check (primary enforcement is in MedicalDocumentService)
        max_bytes = settings.MAX_DOCUMENT_SIZE_MB * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise ProviderResponseError(
                f"File exceeds {settings.MAX_DOCUMENT_SIZE_MB} MB limit.",
                provider_name=self.PROVIDER_NAME,
            )
        if len(file_bytes) == 0:
            raise ProviderResponseError(
                "Cannot upload empty file bytes to Cloudinary.",
                provider_name=self.PROVIDER_NAME,
            )

        # Validate magic bytes (content-type spoofing defence)
        try:
            _check_magic_bytes(file_bytes, content_type)
        except ValueError as magic_err:
            raise ProviderResponseError(
                str(magic_err),
                provider_name=self.PROVIDER_NAME,
            ) from magic_err

        # Map MIME to Cloudinary resource_type
        if content_type == "application/pdf":
            resource_type = "raw"
            upload_format = "pdf"
        else:
            resource_type = "image"
            upload_format = content_type.split("/")[-1]  # jpeg / png / webp

        public_id = self._make_public_id(storage_key)

        def _do_upload():
            try:
                result = self._uploader.upload(
                    io.BytesIO(file_bytes),
                    public_id=public_id,
                    resource_type=resource_type,
                    overwrite=False,
                    unique_filename=False,
                    use_filename=False,
                    timeout=self._timeout,
                )
                return result
            except (ProviderAuthError, ProviderConfigError, ProviderResponseError, ProviderNetworkError, ProviderProcessingError):
                raise
            except Exception as exc:
                self._classify_cloudinary_error(exc)

        result = execute_with_retry(_do_upload, max_retries=2, provider_name=self.PROVIDER_NAME)

        if not result or "public_id" not in result:
            raise ProviderResponseError(
                "Cloudinary upload returned an unexpected response (missing public_id).",
                provider_name=self.PROVIDER_NAME,
            )

        # Persist only the minimum required metadata — no raw credentials or signed URLs
        metadata = {
            "provider": "cloudinary",
            "public_id": result["public_id"],
            "resource_type": result.get("resource_type", resource_type),
            "format": result.get("format", upload_format),
            "secure_url": result.get("secure_url", ""),
        }
        logger.info(
            "cloudinary_upload_success public_id=%s resource_type=%s",
            result["public_id"],
            result.get("resource_type"),
        )
        return json.dumps(metadata)

    def get(self, storage_reference: str) -> bytes:
        """Download file bytes from Cloudinary using the stored metadata reference."""
        try:
            meta = json.loads(storage_reference)
        except (json.JSONDecodeError, TypeError) as parse_err:
            raise ProviderResponseError(
                "Invalid Cloudinary storage reference format.",
                provider_name=self.PROVIDER_NAME,
            ) from parse_err

        secure_url = meta.get("secure_url", "")
        public_id = meta.get("public_id", "")

        if not secure_url:
            raise ProviderResponseError(
                "Cloudinary storage reference is missing secure_url required for retrieval.",
                provider_name=self.PROVIDER_NAME,
            )

        def _do_download() -> bytes:
            import urllib.request
            import urllib.error
            try:
                req = urllib.request.Request(secure_url)
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    status_code = resp.status
                    if status_code == 404:
                        raise FileNotFoundError(
                            f"Cloudinary resource not found: public_id={public_id}"
                        )
                    if status_code in (401, 403):
                        raise ProviderAuthError(
                            f"Cloudinary returned HTTP {status_code} on download.",
                            provider_name=self.PROVIDER_NAME,
                        )
                    if status_code >= 500:
                        raise ProviderProcessingError(
                            f"Cloudinary server error HTTP {status_code} during download.",
                            provider_name=self.PROVIDER_NAME,
                        )
                    return resp.read()
            except (FileNotFoundError, ProviderAuthError, ProviderProcessingError, ProviderNetworkError):
                raise
            except urllib.error.HTTPError as http_err:
                if http_err.code == 404:
                    raise FileNotFoundError(
                        f"Cloudinary resource not found (HTTP 404): public_id={public_id}"
                    ) from http_err
                if http_err.code in (401, 403):
                    raise ProviderAuthError(
                        f"Cloudinary authentication error HTTP {http_err.code} on download.",
                        provider_name=self.PROVIDER_NAME,
                    ) from http_err
                raise ProviderProcessingError(
                    f"Cloudinary HTTP error {http_err.code} during download.",
                    provider_name=self.PROVIDER_NAME,
                ) from http_err
            except (socket.timeout, TimeoutError) as te:
                raise ProviderNetworkError(
                    "Cloudinary download request timed out.",
                    provider_name=self.PROVIDER_NAME,
                ) from te
            except (ConnectionError, OSError) as net_err:
                raise ProviderNetworkError(
                    f"Cloudinary download network error: {type(net_err).__name__}",
                    provider_name=self.PROVIDER_NAME,
                ) from net_err

        return execute_with_retry(_do_download, max_retries=2, provider_name=self.PROVIDER_NAME)

    def delete(self, storage_reference: str) -> bool:
        """Delete a Cloudinary resource using the stored metadata reference.

        Scoped strictly to the exact public_id persisted at upload time and
        must reside under the configured folder prefix.
        """
        try:
            meta = json.loads(storage_reference)
        except (json.JSONDecodeError, TypeError) as parse_err:
            raise ProviderResponseError(
                "Invalid Cloudinary storage reference format for deletion.",
                provider_name=self.PROVIDER_NAME,
            ) from parse_err

        public_id = meta.get("public_id", "")
        resource_type = meta.get("resource_type", "image")

        if not public_id:
            raise ProviderResponseError(
                "Cloudinary storage reference is missing public_id required for deletion.",
                provider_name=self.PROVIDER_NAME,
            )

        # Scope guard: only delete resources under our configured folder
        expected_prefix = self._folder + "/"
        if not public_id.startswith(expected_prefix):
            raise ProviderResponseError(
                "Cloudinary public_id is outside the configured folder scope. "
                "Deletion rejected for security.",
                provider_name=self.PROVIDER_NAME,
            )

        def _do_delete() -> bool:
            try:
                result = self._uploader.destroy(
                    public_id,
                    resource_type=resource_type,
                    timeout=self._timeout,
                )
                outcome = result.get("result", "")
                if outcome == "ok":
                    logger.info(
                        "cloudinary_delete_success public_id=%s resource_type=%s",
                        public_id,
                        resource_type,
                    )
                    return True
                if outcome == "not found":
                    logger.warning(
                        "cloudinary_delete_not_found public_id=%s resource_type=%s",
                        public_id,
                        resource_type,
                    )
                    return False
                raise ProviderProcessingError(
                    f"Cloudinary deletion returned unexpected result: '{outcome}'",
                    provider_name=self.PROVIDER_NAME,
                )
            except (ProviderAuthError, ProviderProcessingError, ProviderResponseError, ProviderNetworkError):
                raise
            except Exception as exc:
                self._classify_cloudinary_error(exc)

        return execute_with_retry(_do_delete, max_retries=2, provider_name=self.PROVIDER_NAME)


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------

def get_storage_service() -> StorageService:
    """Return the configured StorageService implementation.

    Selection is driven exclusively by DOCUMENT_STORAGE_PROVIDER (falls back to
    the legacy STORAGE_PROVIDER alias).  The Cloudinary SDK being installed does
    NOT automatically activate Cloudinary storage.

    Raises ProviderConfigError if DOCUMENT_STORAGE_PROVIDER=cloudinary is
    requested but one or more credentials are missing.
    """
    provider = settings.DOCUMENT_STORAGE_PROVIDER.strip().lower()

    if provider == "cloudinary":
        # Fail-closed: raise immediately if any credential is absent
        if not all([
            settings.CLOUDINARY_CLOUD_NAME,
            settings.CLOUDINARY_API_KEY,
            settings.CLOUDINARY_API_SECRET,
        ]):
            raise ProviderConfigError(
                "DOCUMENT_STORAGE_PROVIDER=cloudinary requires CLOUDINARY_CLOUD_NAME, "
                "CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET to be set in the environment. "
                "No credentials should be committed to version control.",
                provider_name="cloudinary",
            )
        return CloudinaryStorageProvider()

    if provider != "local":
        logger.warning(
            "Unknown DOCUMENT_STORAGE_PROVIDER value '%s'. Defaulting to 'local'.", provider
        )
    return LocalStorageService()


storage_service = get_storage_service()
