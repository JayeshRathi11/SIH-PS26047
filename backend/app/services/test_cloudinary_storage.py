"""Step 22: Cloudinary Document Storage Adapter — Mock-Only Test Suite.

ALL tests in this file use mocked Cloudinary client calls.
ZERO outbound network requests to api.cloudinary.com or any CDN are made.

Coverage:
 1. Factory selects LocalStorageService by default
 2. Factory selects CloudinaryStorageProvider when configured
 3. Factory fails closed with ProviderConfigError when credentials missing
 4. Factory fails closed when partial credentials provided
 5. Factory falls back to local for unknown provider name
 6. Upload success PDF (mocked Cloudinary client)
 7. Upload success JPEG
 8. Upload success PNG
 9. Upload success WebP
10. Upload failure — provider server error (5xx)
11. Upload authentication failure (text in error message)
12. Upload timeout / network failure (socket.timeout)
13. Upload unsupported MIME type rejected before SDK call
14. Upload file > 10 MB rejected before SDK call
15. Upload empty file rejected before SDK call
16. Upload magic byte mismatch rejected
17. Upload missing public_id in Cloudinary response raises ProviderResponseError
18. Upload public_id is server-controlled (client filename not used)
19. Upload path traversal in storage_key neutralized
20. Upload use_filename=False enforced
21. Get (read) success — returns file bytes
22. Get failure — HTTP 404 -> FileNotFoundError
23. Get failure — HTTP 500 -> ProviderProcessingError
24. Get failure — invalid JSON reference -> ProviderResponseError
25. Get failure — missing secure_url -> ProviderResponseError
26. Get failure — socket.timeout -> ProviderNetworkError
27. Get failure — HTTP 401 -> ProviderAuthError
28. Delete success -> True
29. Delete not-found -> False
30. Delete server error -> ProviderProcessingError
31. Delete invalid reference -> ProviderResponseError
32. Delete missing public_id -> ProviderResponseError
33. Delete rejects public_id outside folder scope
34. Delete network timeout -> ProviderNetworkError
35. Credentials not in storage reference JSON
36. Path traversal in _make_public_id neutralized
37. _make_public_id is deterministic
38. _make_public_id caps at 255 chars
39. _make_public_id sanitizes special chars
40. Error messages do not leak credentials
41. Provider is StorageService subclass
42. Init with explicit params (not settings)
43. Init missing all credentials -> ProviderConfigError
44. Init missing one credential -> ProviderConfigError
45. LocalStorageService upload/get roundtrip
46. LocalStorageService delete removes file
47. LocalStorageService delete nonexistent returns False
48. LocalStorageService path traversal rejected
49. LocalStorageService get missing raises FileNotFoundError
50. Pipeline upload→delete lifecycle via mocked Cloudinary
51. Upload failure prevents storage ref being returned
52. Pipeline retrieval works with mocked Cloudinary storage
"""

import io
import json
import os
import socket as socket_module
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

# Ensure local storage is selected at module import time — no env pollution
os.environ.setdefault("DOCUMENT_STORAGE_PROVIDER", "local")

# Minimal valid file fixtures (match magic bytes for each type)
_PDF_BYTES = b"%PDF-1.4 Test medical document content here"
_JPEG_BYTES = b"\xff\xd8\xff\xe0Test JPEG image bytes"
_PNG_BYTES = b"\x89PNGTest PNG image bytes"
_WEBP_BYTES = b"RIFFTestWEBP image bytes"


# ---------------------------------------------------------------------------
# Helper: build a CloudinaryStorageProvider with a fully mocked _uploader
# ---------------------------------------------------------------------------

def _make_provider(
    upload_return=None,
    upload_side_effect=None,
    destroy_return=None,
    destroy_side_effect=None,
    folder="medikiosk_documents",
    timeout=5,
):
    """Create a CloudinaryStorageProvider with cloudinary.config patched out.

    The _uploader attribute is replaced with a MagicMock directly after
    construction, so no real Cloudinary network call is ever made.
    """
    # Ensure cloudinary.uploader submodule is imported so patching works
    import cloudinary.uploader  # noqa: F401

    mock_uploader = MagicMock()
    if upload_side_effect:
        mock_uploader.upload.side_effect = upload_side_effect
    elif upload_return is not None:
        mock_uploader.upload.return_value = upload_return
    else:
        mock_uploader.upload.return_value = {
            "public_id": f"{folder}/patients/1/interviews/2/abc123_doc.pdf",
            "resource_type": "raw",
            "format": "pdf",
            "secure_url": f"https://res.cloudinary.com/test/raw/upload/{folder}/patients/1/interviews/2/abc123_doc.pdf",
        }

    if destroy_side_effect:
        mock_uploader.destroy.side_effect = destroy_side_effect
    elif destroy_return is not None:
        mock_uploader.destroy.return_value = destroy_return
    else:
        mock_uploader.destroy.return_value = {"result": "ok"}

    with patch("cloudinary.config"):
        from app.services.storage_service import CloudinaryStorageProvider
        provider = CloudinaryStorageProvider(
            cloud_name="test-cloud",
            api_key="test-api-key",
            api_secret="test-api-secret",
            folder=folder,
            timeout_seconds=timeout,
        )
    # Replace uploader with our mock (avoids module-attribute patch issues)
    provider._uploader = mock_uploader
    return provider, mock_uploader


def _make_cloudinary_ref(
    public_id=None,
    resource_type="raw",
    fmt="pdf",
    secure_url=None,
    folder="medikiosk_documents",
):
    pid = public_id or f"{folder}/patients/1/interviews/2/abc123_doc.pdf"
    return json.dumps({
        "provider": "cloudinary",
        "public_id": pid,
        "resource_type": resource_type,
        "format": fmt,
        "secure_url": secure_url or f"https://res.cloudinary.com/test/raw/upload/{pid}",
    })


# ===========================================================================
# 1. Provider Factory
# ===========================================================================

class TestStorageProviderFactory(unittest.TestCase):
    """Tests for get_storage_service() provider factory."""

    def test_factory_returns_local_by_default(self):
        """Factory returns LocalStorageService when DOCUMENT_STORAGE_PROVIDER=local."""
        with patch("app.services.storage_service.settings") as ms:
            ms.DOCUMENT_STORAGE_PROVIDER = "local"
            ms.LOCAL_STORAGE_PATH = Path(tempfile.mkdtemp())
            from app.services.storage_service import get_storage_service, LocalStorageService
            svc = get_storage_service()
        self.assertIsInstance(svc, LocalStorageService)

    def test_factory_returns_cloudinary_when_configured(self):
        """Factory returns CloudinaryStorageProvider when provider=cloudinary with credentials."""
        import cloudinary.uploader  # noqa: F401
        with patch("app.services.storage_service.settings") as ms, \
             patch("cloudinary.config"):
            ms.DOCUMENT_STORAGE_PROVIDER = "cloudinary"
            ms.CLOUDINARY_CLOUD_NAME = "test-cloud"
            ms.CLOUDINARY_API_KEY = "test-api-key"
            ms.CLOUDINARY_API_SECRET = "test-api-secret"
            ms.CLOUDINARY_FOLDER = "medikiosk_documents"
            ms.CLOUDINARY_TIMEOUT_SECONDS = 15
            from app.services.storage_service import get_storage_service, CloudinaryStorageProvider
            svc = get_storage_service()
        self.assertIsInstance(svc, CloudinaryStorageProvider)

    def test_factory_fail_closed_all_credentials_missing(self):
        """Factory raises ProviderConfigError when cloudinary requested without any credentials."""
        from app.core.provider_errors import ProviderConfigError
        with patch("app.services.storage_service.settings") as ms:
            ms.DOCUMENT_STORAGE_PROVIDER = "cloudinary"
            ms.CLOUDINARY_CLOUD_NAME = None
            ms.CLOUDINARY_API_KEY = None
            ms.CLOUDINARY_API_SECRET = None
            from app.services.storage_service import get_storage_service
            with self.assertRaises(ProviderConfigError):
                get_storage_service()

    def test_factory_fail_closed_partial_credentials(self):
        """Factory raises ProviderConfigError when only some credentials are present."""
        from app.core.provider_errors import ProviderConfigError
        with patch("app.services.storage_service.settings") as ms:
            ms.DOCUMENT_STORAGE_PROVIDER = "cloudinary"
            ms.CLOUDINARY_CLOUD_NAME = "my-cloud"
            ms.CLOUDINARY_API_KEY = "key"
            ms.CLOUDINARY_API_SECRET = None
            from app.services.storage_service import get_storage_service
            with self.assertRaises(ProviderConfigError):
                get_storage_service()

    def test_factory_unknown_provider_defaults_to_local(self):
        """Factory logs warning and returns LocalStorageService for unknown provider name."""
        with patch("app.services.storage_service.settings") as ms:
            ms.DOCUMENT_STORAGE_PROVIDER = "s3_or_something_else"
            ms.LOCAL_STORAGE_PATH = Path(tempfile.mkdtemp())
            from app.services.storage_service import get_storage_service, LocalStorageService
            svc = get_storage_service()
        self.assertIsInstance(svc, LocalStorageService)


# ===========================================================================
# 2. CloudinaryStorageProvider — Upload
# ===========================================================================

class TestCloudinaryUpload(unittest.TestCase):
    """Tests for CloudinaryStorageProvider.upload()."""

    def test_upload_success_pdf(self):
        """Upload succeeds and returns valid JSON metadata with required fields."""
        provider, mock_uploader = _make_provider()
        result = provider.upload(_PDF_BYTES, "patients/1/interviews/2/abc123_doc.pdf", "application/pdf")
        meta = json.loads(result)
        self.assertEqual(meta["provider"], "cloudinary")
        self.assertIn("public_id", meta)
        self.assertIn("resource_type", meta)
        self.assertIn("format", meta)
        self.assertIn("secure_url", meta)
        mock_uploader.upload.assert_called_once()

    def test_upload_success_jpeg(self):
        """Upload succeeds for JPEG with resource_type=image."""
        provider, mock_uploader = _make_provider(upload_return={
            "public_id": "medikiosk_documents/patients/1/interviews/2/abc123_scan.jpg",
            "resource_type": "image",
            "format": "jpg",
            "secure_url": "https://res.cloudinary.com/test/image/upload/x.jpg",
        })
        result = provider.upload(_JPEG_BYTES, "patients/1/interviews/2/abc123_scan.jpg", "image/jpeg")
        meta = json.loads(result)
        self.assertEqual(meta["resource_type"], "image")

    def test_upload_success_png(self):
        """Upload succeeds for PNG image."""
        provider, mock_uploader = _make_provider(upload_return={
            "public_id": "medikiosk_documents/patients/3/interviews/4/uuid123_report.png",
            "resource_type": "image",
            "format": "png",
            "secure_url": "https://res.cloudinary.com/test/image/upload/x.png",
        })
        result = provider.upload(_PNG_BYTES, "patients/3/interviews/4/uuid123_report.png", "image/png")
        meta = json.loads(result)
        self.assertEqual(meta["format"], "png")

    def test_upload_success_webp(self):
        """Upload succeeds for WebP image."""
        provider, mock_uploader = _make_provider(upload_return={
            "public_id": "medikiosk_documents/patients/5/interviews/6/uuid456_photo.webp",
            "resource_type": "image",
            "format": "webp",
            "secure_url": "https://res.cloudinary.com/test/image/upload/x.webp",
        })
        result = provider.upload(_WEBP_BYTES, "patients/5/interviews/6/uuid456.webp", "image/webp")
        meta = json.loads(result)
        self.assertEqual(meta["format"], "webp")

    def test_upload_server_error_5xx_raises_processing_error(self):
        """Upload raises ProviderProcessingError on Cloudinary 5xx server error."""
        from app.core.provider_errors import ProviderProcessingError
        provider, _ = _make_provider(upload_side_effect=Exception("Server error HTTP 503: unavailable"))
        with self.assertRaises(ProviderProcessingError):
            provider.upload(_PDF_BYTES, "patients/1/interviews/1/abc_doc.pdf", "application/pdf")

    def test_upload_auth_failure_raises_auth_error(self):
        """Upload raises ProviderAuthError when Cloudinary signals authentication failure."""
        from app.core.provider_errors import ProviderAuthError
        provider, _ = _make_provider(upload_side_effect=Exception("Invalid API key authentication failed"))
        with self.assertRaises(ProviderAuthError):
            provider.upload(_PDF_BYTES, "patients/1/interviews/1/abc_doc.pdf", "application/pdf")

    def test_upload_network_timeout_raises_network_error(self):
        """Upload raises ProviderNetworkError on socket timeout."""
        from app.core.provider_errors import ProviderNetworkError
        provider, _ = _make_provider(upload_side_effect=socket_module.timeout("Connection timed out"))
        with self.assertRaises(ProviderNetworkError):
            provider.upload(_PDF_BYTES, "patients/1/interviews/1/abc_doc.pdf", "application/pdf")

    def test_upload_unsupported_mime_rejected_before_sdk_call(self):
        """Upload raises ProviderResponseError for unsupported MIME type; SDK is never called."""
        from app.core.provider_errors import ProviderResponseError
        provider, mock_uploader = _make_provider()
        with self.assertRaises(ProviderResponseError):
            provider.upload(b"GIF89a...", "patients/1/interviews/1/anim.gif", "image/gif")
        mock_uploader.upload.assert_not_called()

    def test_upload_oversized_file_rejected(self):
        """Upload raises ProviderResponseError when file exceeds 10 MB limit."""
        from app.core.provider_errors import ProviderResponseError
        large_bytes = b"%PDF" + (b"x" * (11 * 1024 * 1024))
        provider, mock_uploader = _make_provider()
        with patch("app.services.storage_service.settings") as ms:
            ms.MAX_DOCUMENT_SIZE_MB = 10
            with self.assertRaises(ProviderResponseError):
                provider.upload(large_bytes, "patients/1/interviews/1/large.pdf", "application/pdf")
        mock_uploader.upload.assert_not_called()

    def test_upload_empty_file_rejected(self):
        """Upload raises ProviderResponseError for zero-byte file."""
        from app.core.provider_errors import ProviderResponseError
        provider, mock_uploader = _make_provider()
        with self.assertRaises(ProviderResponseError):
            provider.upload(b"", "patients/1/interviews/1/empty.pdf", "application/pdf")
        mock_uploader.upload.assert_not_called()

    def test_upload_magic_byte_mismatch_rejected(self):
        """Upload raises ProviderResponseError when file bytes do not match declared MIME type."""
        from app.core.provider_errors import ProviderResponseError
        provider, mock_uploader = _make_provider()
        # Claim PDF but supply JPEG bytes
        with self.assertRaises(ProviderResponseError) as ctx:
            provider.upload(_JPEG_BYTES, "patients/1/interviews/1/fake.pdf", "application/pdf")
        self.assertIn("MIME type", str(ctx.exception))
        mock_uploader.upload.assert_not_called()

    def test_upload_missing_public_id_in_response_raises_response_error(self):
        """Upload raises ProviderResponseError when Cloudinary response lacks public_id."""
        from app.core.provider_errors import ProviderResponseError
        provider, _ = _make_provider(upload_return={"secure_url": "https://example.com"})
        with self.assertRaises(ProviderResponseError):
            provider.upload(_PDF_BYTES, "patients/1/interviews/1/doc.pdf", "application/pdf")

    def test_upload_public_id_is_server_controlled(self):
        """Cloudinary public_id is derived from server storage_key, never raw client input."""
        captured_kwargs = {}

        def _mock_upload(file_obj, **kwargs):
            captured_kwargs.update(kwargs)
            return {
                "public_id": kwargs["public_id"],
                "resource_type": "raw",
                "format": "pdf",
                "secure_url": "https://res.cloudinary.com/test/raw/upload/" + kwargs["public_id"],
            }

        provider, mock_uploader = _make_provider()
        mock_uploader.upload.side_effect = _mock_upload

        # storage_key has a UUID prefix (server-generated in MedicalDocumentService)
        server_key = "patients/99/interviews/42/a1b2c3d4_medical_report.pdf"
        provider.upload(_PDF_BYTES, server_key, "application/pdf")

        called_public_id = captured_kwargs.get("public_id", "")
        # Must include the UUID portion from the key
        self.assertIn("a1b2c3d4", called_public_id)
        # Must not be just the raw filename
        self.assertNotEqual(called_public_id, "medical_report.pdf")
        # Must be rooted under our folder
        self.assertTrue(called_public_id.startswith("medikiosk_documents/"))

    def test_upload_path_traversal_in_storage_key_neutralized(self):
        """Path traversal sequences in storage_key are neutralized before creating public_id."""
        captured_kwargs = {}

        def _mock_upload(file_obj, **kwargs):
            captured_kwargs.update(kwargs)
            return {
                "public_id": kwargs["public_id"],
                "resource_type": "raw",
                "format": "pdf",
                "secure_url": "https://res.cloudinary.com/test/raw/upload/" + kwargs["public_id"],
            }

        provider, mock_uploader = _make_provider()
        mock_uploader.upload.side_effect = _mock_upload
        malicious_key = "patients/1/interviews/2/../../../admin/sensitive.pdf"
        provider.upload(_PDF_BYTES, malicious_key, "application/pdf")

        called_public_id = captured_kwargs.get("public_id", "")
        # '..' traversal components must be stripped so no directory escape is possible
        self.assertNotIn("../", called_public_id)
        self.assertNotIn("..", called_public_id.split("/"))
        # Must remain under our managed folder (scope enforced by delete guard)
        self.assertTrue(called_public_id.startswith("medikiosk_documents/"))

    def test_upload_use_filename_false_enforced(self):
        """upload() always calls Cloudinary with use_filename=False."""
        captured_kwargs = {}

        def _mock_upload(file_obj, **kwargs):
            captured_kwargs.update(kwargs)
            return {
                "public_id": kwargs["public_id"],
                "resource_type": "raw",
                "format": "pdf",
                "secure_url": "https://example.com/x.pdf",
            }

        provider, mock_uploader = _make_provider()
        mock_uploader.upload.side_effect = _mock_upload
        provider.upload(_PDF_BYTES, "patients/1/interviews/1/uuid123_doc.pdf", "application/pdf")

        self.assertFalse(captured_kwargs.get("use_filename", True))
        self.assertFalse(captured_kwargs.get("unique_filename", True))


# ===========================================================================
# 3. CloudinaryStorageProvider — Get
# ===========================================================================

class TestCloudinaryGet(unittest.TestCase):
    """Tests for CloudinaryStorageProvider.get()."""

    def _urlopen_mock(self, content=None, status=200):
        mock_resp = MagicMock()
        mock_resp.status = status
        mock_resp.read.return_value = content or b"%PDF-1.4 Downloaded"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    def test_get_success_returns_bytes(self):
        """get() returns file bytes on successful download."""
        provider, _ = _make_provider()
        expected = b"%PDF-1.4 downloaded content"
        ref = _make_cloudinary_ref()
        with patch("urllib.request.urlopen", return_value=self._urlopen_mock(content=expected)):
            result = provider.get(ref)
        self.assertEqual(result, expected)

    def test_get_not_found_raises_file_not_found(self):
        """get() raises FileNotFoundError when Cloudinary returns HTTP 404."""
        import urllib.error
        provider, _ = _make_provider()
        ref = _make_cloudinary_ref()
        with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
            "https://example.com", 404, "Not Found", {}, None
        )):
            with self.assertRaises(FileNotFoundError):
                provider.get(ref)

    def test_get_server_error_raises_processing_error(self):
        """get() raises ProviderProcessingError on HTTP 500."""
        import urllib.error
        from app.core.provider_errors import ProviderProcessingError
        provider, _ = _make_provider()
        ref = _make_cloudinary_ref()
        with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
            "https://example.com", 500, "Internal Server Error", {}, None
        )):
            with self.assertRaises(ProviderProcessingError):
                provider.get(ref)

    def test_get_invalid_json_reference_raises_response_error(self):
        """get() raises ProviderResponseError if storage reference is not valid JSON."""
        from app.core.provider_errors import ProviderResponseError
        provider, _ = _make_provider()
        with self.assertRaises(ProviderResponseError):
            provider.get("not-valid-json-{{{")

    def test_get_missing_secure_url_raises_response_error(self):
        """get() raises ProviderResponseError if secure_url is absent in reference."""
        from app.core.provider_errors import ProviderResponseError
        provider, _ = _make_provider()
        ref = json.dumps({
            "provider": "cloudinary",
            "public_id": "medikiosk_documents/x",
            "resource_type": "raw",
            "format": "pdf",
            # no secure_url
        })
        with self.assertRaises(ProviderResponseError):
            provider.get(ref)

    def test_get_network_timeout_raises_network_error(self):
        """get() raises ProviderNetworkError on socket timeout."""
        from app.core.provider_errors import ProviderNetworkError
        provider, _ = _make_provider()
        ref = _make_cloudinary_ref()
        with patch("urllib.request.urlopen", side_effect=socket_module.timeout("timeout")):
            with self.assertRaises(ProviderNetworkError):
                provider.get(ref)

    def test_get_auth_error_raises_provider_auth_error(self):
        """get() raises ProviderAuthError on HTTP 401."""
        import urllib.error
        from app.core.provider_errors import ProviderAuthError
        provider, _ = _make_provider()
        ref = _make_cloudinary_ref()
        with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
            "https://example.com", 401, "Unauthorized", {}, None
        )):
            with self.assertRaises(ProviderAuthError):
                provider.get(ref)


# ===========================================================================
# 4. CloudinaryStorageProvider — Delete
# ===========================================================================

class TestCloudinaryDelete(unittest.TestCase):
    """Tests for CloudinaryStorageProvider.delete()."""

    def test_delete_success_returns_true(self):
        """delete() returns True when Cloudinary confirms deletion with result=ok."""
        provider, mock_uploader = _make_provider(destroy_return={"result": "ok"})
        result = provider.delete(_make_cloudinary_ref())
        self.assertTrue(result)
        mock_uploader.destroy.assert_called_once()

    def test_delete_not_found_returns_false(self):
        """delete() returns False when Cloudinary says result=not found (idempotent)."""
        provider, _ = _make_provider(destroy_return={"result": "not found"})
        result = provider.delete(_make_cloudinary_ref())
        self.assertFalse(result)

    def test_delete_server_error_raises_processing_error(self):
        """delete() raises ProviderProcessingError on Cloudinary server error."""
        from app.core.provider_errors import ProviderProcessingError
        provider, _ = _make_provider(destroy_side_effect=Exception("Server error 503: unavailable"))
        with self.assertRaises(ProviderProcessingError):
            provider.delete(_make_cloudinary_ref())

    def test_delete_invalid_reference_raises_response_error(self):
        """delete() raises ProviderResponseError for non-JSON storage reference."""
        from app.core.provider_errors import ProviderResponseError
        provider, _ = _make_provider()
        with self.assertRaises(ProviderResponseError):
            provider.delete("garbage-not-json")

    def test_delete_missing_public_id_raises_response_error(self):
        """delete() raises ProviderResponseError if public_id is absent in reference."""
        from app.core.provider_errors import ProviderResponseError
        provider, _ = _make_provider()
        ref = json.dumps({"provider": "cloudinary", "resource_type": "raw", "format": "pdf"})
        with self.assertRaises(ProviderResponseError):
            provider.delete(ref)

    def test_delete_rejects_public_id_outside_folder_scope(self):
        """delete() raises ProviderResponseError if public_id is outside configured folder."""
        from app.core.provider_errors import ProviderResponseError
        provider, mock_uploader = _make_provider()
        malicious_ref = json.dumps({
            "provider": "cloudinary",
            "public_id": "other_app/sensitive/data.pdf",
            "resource_type": "raw",
            "format": "pdf",
        })
        with self.assertRaises(ProviderResponseError) as ctx:
            provider.delete(malicious_ref)
        self.assertIn("scope", str(ctx.exception))
        mock_uploader.destroy.assert_not_called()

    def test_delete_network_timeout_raises_network_error(self):
        """delete() raises ProviderNetworkError on socket timeout."""
        from app.core.provider_errors import ProviderNetworkError
        provider, _ = _make_provider(destroy_side_effect=socket_module.timeout("timed out"))
        with self.assertRaises(ProviderNetworkError):
            provider.delete(_make_cloudinary_ref())


# ===========================================================================
# 5. Security Invariants
# ===========================================================================

class TestCloudinarySecurityInvariants(unittest.TestCase):
    """Security invariant tests: path traversal, credential safety, scope guards."""

    def test_credentials_not_in_storage_reference(self):
        """Storage reference JSON must not contain API key or secret."""
        provider, _ = _make_provider()
        provider._api_key = "secret-api-key-1234"
        provider._api_secret = "secret-api-secret-5678"
        result = provider.upload(_PDF_BYTES, "patients/1/interviews/1/uuid_doc.pdf", "application/pdf")
        self.assertNotIn("secret-api-key-1234", result)
        self.assertNotIn("secret-api-secret-5678", result)

    def test_path_traversal_in_make_public_id_neutralized(self):
        """_make_public_id strips traversal sequences from storage_key."""
        provider, _ = _make_provider()
        public_id = provider._make_public_id("patients/1/../../admin/etc/passwd")
        # '..' traversal segments must be stripped so path cannot escape the folder
        self.assertNotIn("../", public_id)
        self.assertNotIn("..", public_id.split("/"))
        # Path must still live under the managed folder
        self.assertTrue(public_id.startswith("medikiosk_documents/"))

    def test_delete_scope_guard_prevents_out_of_folder_deletion(self):
        """delete() refuses resources outside the configured folder prefix."""
        from app.core.provider_errors import ProviderResponseError
        provider, mock_uploader = _make_provider()
        evil_ref = json.dumps({
            "provider": "cloudinary",
            "public_id": "some_other_app/critical_data.pdf",
            "resource_type": "raw",
            "format": "pdf",
        })
        with self.assertRaises(ProviderResponseError):
            provider.delete(evil_ref)
        mock_uploader.destroy.assert_not_called()

    def test_error_classification_redacts_credentials(self):
        """Error classification redacts API key/secret from exception messages."""
        provider, _ = _make_provider()
        provider._api_key = "secret-api-key-9999"
        provider._api_secret = "secret-api-secret-0000"
        err = Exception("Invalid api-key 'secret-api-key-9999' for cloud test")
        try:
            provider._classify_cloudinary_error(err)
            self.fail("Expected ProviderError to be raised")
        except Exception as raised:
            self.assertNotIn("secret-api-key-9999", str(raised))
            self.assertNotIn("secret-api-secret-0000", str(raised))


# ===========================================================================
# 6. _make_public_id Unit Tests
# ===========================================================================

class TestPublicIdGeneration(unittest.TestCase):
    """Unit tests for _make_public_id determinism, safety, and constraints."""

    def _provider(self):
        with patch("cloudinary.config"):
            from app.services.storage_service import CloudinaryStorageProvider
            p = CloudinaryStorageProvider(
                cloud_name="c",
                api_key="k",
                api_secret="s",
                folder="medikiosk_documents",
                timeout_seconds=5,
            )
        return p

    def test_public_id_starts_with_folder(self):
        p = self._provider()
        pid = p._make_public_id("patients/1/interviews/1/abc123_doc.pdf")
        self.assertTrue(pid.startswith("medikiosk_documents/"))

    def test_public_id_is_deterministic(self):
        p = self._provider()
        pid1 = p._make_public_id("patients/1/interviews/1/abc123_doc.pdf")
        pid2 = p._make_public_id("patients/1/interviews/1/abc123_doc.pdf")
        self.assertEqual(pid1, pid2)

    def test_public_id_length_capped_at_255(self):
        p = self._provider()
        long_key = "patients/1/interviews/1/" + "x" * 300
        pid = p._make_public_id(long_key)
        self.assertLessEqual(len(pid), 255)

    def test_special_chars_sanitized(self):
        p = self._provider()
        key = "patients/1/interviews/1/file name with spaces & symbols!.pdf"
        pid = p._make_public_id(key)
        self.assertNotIn(" ", pid)
        self.assertNotIn("&", pid)
        self.assertNotIn("!", pid)


# ===========================================================================
# 7. CloudinaryStorageProvider Config / Init
# ===========================================================================

class TestCloudinaryProviderConfig(unittest.TestCase):
    """CloudinaryStorageProvider instantiation and configuration edge cases."""

    def test_init_missing_all_credentials_raises_config_error(self):
        """Instantiation without credentials raises ProviderConfigError."""
        from app.services.storage_service import CloudinaryStorageProvider
        from app.core.provider_errors import ProviderConfigError
        with patch("app.services.storage_service.settings") as ms:
            ms.CLOUDINARY_CLOUD_NAME = None
            ms.CLOUDINARY_API_KEY = None
            ms.CLOUDINARY_API_SECRET = None
            ms.CLOUDINARY_FOLDER = "medikiosk_documents"
            ms.CLOUDINARY_TIMEOUT_SECONDS = 15
            with self.assertRaises(ProviderConfigError):
                CloudinaryStorageProvider()

    def test_init_missing_one_credential_raises_config_error(self):
        """Instantiation fails if any single credential is missing."""
        from app.services.storage_service import CloudinaryStorageProvider
        from app.core.provider_errors import ProviderConfigError
        with patch("app.services.storage_service.settings") as ms:
            ms.CLOUDINARY_CLOUD_NAME = "my-cloud"
            ms.CLOUDINARY_API_KEY = "key"
            ms.CLOUDINARY_API_SECRET = None
            ms.CLOUDINARY_FOLDER = "medikiosk_documents"
            ms.CLOUDINARY_TIMEOUT_SECONDS = 15
            with self.assertRaises(ProviderConfigError):
                CloudinaryStorageProvider()

    def test_provider_is_storage_service_subclass(self):
        """CloudinaryStorageProvider implements the StorageService interface."""
        from app.services.storage_service import CloudinaryStorageProvider, StorageService
        self.assertTrue(issubclass(CloudinaryStorageProvider, StorageService))

    def test_init_with_explicit_params(self):
        """Constructor accepts explicit params without reading settings."""
        with patch("cloudinary.config"):
            from app.services.storage_service import CloudinaryStorageProvider
            p = CloudinaryStorageProvider(
                cloud_name="explicit-cloud",
                api_key="explicit-key",
                api_secret="explicit-secret",
                folder="test_folder",
                timeout_seconds=30,
            )
        self.assertEqual(p._cloud_name, "explicit-cloud")
        self.assertEqual(p._folder, "test_folder")
        self.assertEqual(p._timeout, 30)


# ===========================================================================
# 8. LocalStorageService Regression Tests
# ===========================================================================

class TestLocalStorageContinuesWorking(unittest.TestCase):
    """Regression: existing LocalStorageService behaviour is unchanged."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="medikiosk_local_test_")
        from app.services.storage_service import LocalStorageService
        self.svc = LocalStorageService(base_path=Path(self._tmpdir))

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_upload_and_get_roundtrip(self):
        """Upload then get returns identical bytes."""
        data = b"Test medical document content"
        ref = self.svc.upload(data, "patients/1/interviews/1/uuid_doc.pdf", "application/pdf")
        self.assertEqual(self.svc.get(ref), data)

    def test_delete_removes_file(self):
        """delete() removes stored file and returns True."""
        data = b"Some bytes"
        ref = self.svc.upload(data, "patients/2/interviews/3/uuid_file.pdf", "application/pdf")
        self.assertTrue(self.svc.delete(ref))
        with self.assertRaises(FileNotFoundError):
            self.svc.get(ref)

    def test_delete_nonexistent_returns_false(self):
        """delete() returns False for non-existent storage reference."""
        self.assertFalse(self.svc.delete("patients/0/interviews/0/missing.pdf"))

    def test_path_traversal_rejected(self):
        """_resolve_safe_path raises ValueError on path traversal attempt."""
        with self.assertRaises(ValueError):
            self.svc._resolve_safe_path("../../etc/passwd")

    def test_get_missing_raises_file_not_found(self):
        """get() raises FileNotFoundError when file does not exist."""
        with self.assertRaises(FileNotFoundError):
            self.svc.get("patients/99/interviews/99/nonexistent.pdf")


# ===========================================================================
# 9. Pipeline Integration
# ===========================================================================

class TestCloudinaryPipelineIntegration(unittest.TestCase):
    """Pipeline integration: processing service works with mocked Cloudinary storage."""

    def test_storage_get_used_by_pipeline(self):
        """storage.get() returns expected content when backed by mocked Cloudinary."""
        expected_content = b"%PDF-1.4 Mock medical report for pipeline integration test"
        provider, _ = _make_provider()
        ref = _make_cloudinary_ref()

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = expected_content
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            content = provider.get(ref)

        self.assertEqual(content, expected_content)

    def test_upload_then_delete_lifecycle(self):
        """Full upload → delete lifecycle works end-to-end through mocked provider."""
        provider, mock_uploader = _make_provider(
            upload_return={
                "public_id": "medikiosk_documents/patients/5/interviews/10/uuid001_rx.pdf",
                "resource_type": "raw",
                "format": "pdf",
                "secure_url": "https://res.cloudinary.com/test/raw/upload/medikiosk_documents/patients/5/interviews/10/uuid001_rx.pdf",
            },
            destroy_return={"result": "ok"},
        )

        storage_ref = provider.upload(_PDF_BYTES, "patients/5/interviews/10/uuid001_rx.pdf", "application/pdf")
        self.assertIsInstance(storage_ref, str)
        meta = json.loads(storage_ref)
        self.assertEqual(meta["provider"], "cloudinary")

        deleted = provider.delete(storage_ref)
        self.assertTrue(deleted)
        mock_uploader.destroy.assert_called_once()

    def test_upload_failure_prevents_storage_ref_being_returned(self):
        """If upload raises, no storage reference is returned (no partial state)."""
        from app.core.provider_errors import ProviderProcessingError
        provider, _ = _make_provider(upload_side_effect=Exception("Server error 500"))
        with self.assertRaises(ProviderProcessingError):
            provider.upload(_PDF_BYTES, "patients/1/interviews/1/uuid_doc.pdf", "application/pdf")

    def test_mocked_cloudinary_is_storage_service(self):
        """CloudinaryStorageProvider satisfies the StorageService interface contract."""
        from app.services.storage_service import StorageService
        provider, _ = _make_provider()
        self.assertIsInstance(provider, StorageService)


if __name__ == "__main__":
    unittest.main()
