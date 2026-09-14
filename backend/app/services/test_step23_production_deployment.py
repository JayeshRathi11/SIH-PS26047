"""
Step 23: Production Configuration & Render Deployment Readiness Test Suite.

Validates:
1. Environment & configuration hardening:
   - Required vs optional vs development defaults.
   - Fail-fast production configuration validator (detects missing DB URL, insecure JWT secret, wildcard CORS).
   - Insecure development secrets allowed with warning in dev/test mode.
2. PostgreSQL database configuration:
   - Normalization of Render 'postgres://' and 'postgresql://' URLs to 'postgresql+psycopg://'.
   - Connection pool settings (DB_POOL_SIZE, DB_MAX_OVERFLOW, DB_POOL_TIMEOUT, DB_POOL_RECYCLE, DB_POOL_PRE_PING).
   - Safe operational database connection error handling (zero credential or hostname leakage).
3. Application startup & lifespan:
   - Safe lifespan initialization without external API calls or database mutations.
   - Render PORT and HOST binding configuration.
4. CORS & security configuration:
   - Rejection of wildcard origins with credentials in production.
5. Health endpoints safety:
   - Redaction of all secrets, passwords, connection strings, and PHI across /health, /health/db, /health/status, and /health/metrics.
   - Non-live status reporting for providers, storage, and fallback.
6. Logging & observability PHI/credential protection:
   - Stripping of sensitive metadata and patient identifiers from operational logs.
7. Storage & provider configuration safety:
   - Deterministic local storage by default.
   - Cloudinary and external AI provider integrity validation.
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.core.config import (
    KNOWN_INSECURE_JWT_SECRETS,
    Settings,
    enforce_production_config,
    settings,
    validate_production_config,
)
from app.core.database import check_db_connection, get_engine
from app.core.observability import (
    FORBIDDEN_METADATA_KEYS,
    log_operational_event,
)
from app.main import app


class TestStep23ProductionDeployment(unittest.TestCase):
    """Test suite for Step 23: Production configuration and Render readiness."""

    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)

    # -------------------------------------------------------------------------
    # 1. Database URL Normalization & Render Compatibility
    # -------------------------------------------------------------------------

    def test_database_url_normalization_postgres_render(self):
        """Render provides 'postgres://' URLs. Verify it normalizes to 'postgresql+psycopg://'."""
        with patch.dict(os.environ, {"DATABASE_URL": "postgres://render_user:secret_pass@dpg-abc-a.oregon-postgres.render.com/medikiosk_db"}):
            s = Settings()
            self.assertEqual(
                s.database_url,
                "postgresql+psycopg://render_user:secret_pass@dpg-abc-a.oregon-postgres.render.com/medikiosk_db",
            )

    def test_database_url_normalization_postgresql_render(self):
        """Verify standard 'postgresql://' URL normalizes to 'postgresql+psycopg://'."""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://usr:pwd@host:5432/db"}):
            s = Settings()
            self.assertEqual(
                s.database_url,
                "postgresql+psycopg://usr:pwd@host:5432/db",
            )

    def test_database_url_with_driver_preserved(self):
        """Verify explicit 'postgresql+psycopg://' URL is preserved unchanged."""
        explicit_url = "postgresql+psycopg://usr:pwd@host:5432/db"
        with patch.dict(os.environ, {"DATABASE_URL": explicit_url}):
            s = Settings()
            self.assertEqual(s.database_url, explicit_url)

    def test_database_url_discrete_credentials_assembly(self):
        """Verify fallback to discrete POSTGRES_* environment variables."""
        env_vars = {
            "DATABASE_URL": "",
            "POSTGRES_USER": "test_user",
            "POSTGRES_PASSWORD": "p@ssword#123",
            "POSTGRES_HOST": "db.internal",
            "POSTGRES_PORT": "5432",
            "POSTGRES_DB": "test_db",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            s = Settings()
            # Clear cached properties / reinitialize
            s.POSTGRES_USER = "test_user"
            s.POSTGRES_PASSWORD = "p@ssword#123"
            s.POSTGRES_HOST = "db.internal"
            s.POSTGRES_PORT = "5432"
            s.POSTGRES_DB = "test_db"
            self.assertIn("postgresql+psycopg://test_user:p%40ssword%23123@db.internal:5432/test_db", s.database_url)

    # -------------------------------------------------------------------------
    # 2. Database Connection Pooling Configuration
    # -------------------------------------------------------------------------

    def test_database_pooling_settings_defaults(self):
        """Verify default connection pool settings."""
        s = Settings()
        self.assertGreaterEqual(s.DB_POOL_SIZE, 1)
        self.assertGreaterEqual(s.DB_MAX_OVERFLOW, 0)
        self.assertGreaterEqual(s.DB_POOL_TIMEOUT, 5)
        self.assertGreaterEqual(s.DB_POOL_RECYCLE, 300)
        self.assertTrue(s.DB_POOL_PRE_PING)

    def test_database_pooling_settings_custom_env(self):
        """Verify connection pool settings can be configured via environment."""
        env_vars = {
            "DB_POOL_SIZE": "20",
            "DB_MAX_OVERFLOW": "40",
            "DB_POOL_TIMEOUT": "60",
            "DB_POOL_RECYCLE": "3600",
            "DB_POOL_PRE_PING": "false",
        }
        with patch.dict(os.environ, env_vars):
            s = Settings()
            self.assertEqual(s.DB_POOL_SIZE, 20)
            self.assertEqual(s.DB_MAX_OVERFLOW, 40)
            self.assertEqual(s.DB_POOL_TIMEOUT, 60)
            self.assertEqual(s.DB_POOL_RECYCLE, 3600)
            self.assertFalse(s.DB_POOL_PRE_PING)

    # -------------------------------------------------------------------------
    # 3. Database Connection Failure & Credential Sanitization
    # -------------------------------------------------------------------------

    def test_check_db_connection_sanitizes_failures(self):
        """Verify check_db_connection() never leaks credentials or connection strings on failure."""
        with patch("app.core.database.get_engine") as mock_engine:
            mock_engine.side_effect = Exception("FATAL: password authentication failed for user 'secret_user'")
            connected, detail = check_db_connection()
            self.assertFalse(connected)
            self.assertEqual(detail, "Database connection failed")
            # Ensure no username or password fragments in detail
            self.assertNotIn("secret_user", detail)
            self.assertNotIn("password", detail.lower())

    def test_check_db_connection_when_url_missing(self):
        """Verify check_db_connection() returns safe failure if database_url is None."""
        from unittest.mock import PropertyMock
        with patch.object(type(settings), "database_url", new_callable=PropertyMock, return_value=None):
            connected, detail = check_db_connection()
            self.assertFalse(connected)
            self.assertEqual(detail, "Database connection failed")

    # -------------------------------------------------------------------------
    # 4. Production Configuration Validation (validate_production_config)
    # -------------------------------------------------------------------------

    def test_validate_production_config_valid(self):
        """A valid production configuration should yield zero validation errors."""
        s = Settings()
        s.ENVIRONMENT = "production"
        s.POSTGRES_USER = "prod_user"
        s.POSTGRES_PASSWORD = "prod_password"
        s.POSTGRES_HOST = "prod_host"
        s.POSTGRES_PORT = "5432"
        s.POSTGRES_DB = "prod_db"
        s.JWT_SECRET = "a" * 64  # Secure 64-char random secret
        s.CORS_ORIGINS = ["https://kiosk.hospital.org", "https://doctor.hospital.org"]
        s.CORS_ALLOW_CREDENTIALS = True
        s.DOCUMENT_STORAGE_PROVIDER = "local"
        s.NLP_EXTRACTION_PROVIDER = "mock"
        s.EXTRACTION_PROVIDER = "mock"
        s.SUMMARY_PROVIDER = "mock"
        s.TRANSLATION_PROVIDER = "mock"
        s.ASR_PROVIDER = "mock"
        s.OCR_PROVIDER = "mock"
        s.LLM_FALLBACK_ENABLED = False

        errors = validate_production_config(s)
        self.assertEqual(errors, [])

    def test_validate_production_config_detects_missing_database(self):
        """Detects missing database configuration."""
        s = Settings()
        s.POSTGRES_USER = None
        s.POSTGRES_PASSWORD = None
        s.POSTGRES_HOST = None
        s.POSTGRES_PORT = None
        s.POSTGRES_DB = None
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            errors = validate_production_config(s)
            self.assertTrue(any("database configuration missing" in e.lower() for e in errors))

    def test_validate_production_config_detects_insecure_jwt_secret(self):
        """Detects known default or short JWT secrets in production."""
        for insecure_secret in KNOWN_INSECURE_JWT_SECRETS:
            s = Settings()
            s.JWT_SECRET = insecure_secret
            errors = validate_production_config(s)
            self.assertTrue(
                any("insecure jwt_secret" in e.lower() for e in errors),
                f"Failed to catch insecure secret: {insecure_secret}",
            )

        # Also test secret too short (< 32 characters)
        s = Settings()
        s.JWT_SECRET = "short-secret-12345"
        errors = validate_production_config(s)
        self.assertTrue(any("insecure jwt_secret" in e.lower() for e in errors))

    def test_validate_production_config_cors_wildcard_rejected(self):
        """Detects wildcard CORS with credentials in production."""
        s = Settings()
        s.CORS_ORIGINS = ["*"]
        s.CORS_ALLOW_CREDENTIALS = True
        errors = validate_production_config(s)
        self.assertTrue(any("wildcard cors" in e.lower() for e in errors))

    def test_validate_production_config_cloudinary_credentials(self):
        """Detects missing Cloudinary credentials when Cloudinary is selected."""
        s = Settings()
        s.DOCUMENT_STORAGE_PROVIDER = "cloudinary"
        s.CLOUDINARY_CLOUD_NAME = None
        s.CLOUDINARY_API_KEY = None
        s.CLOUDINARY_API_SECRET = None
        errors = validate_production_config(s)
        self.assertTrue(any("cloudinary" in e.lower() for e in errors))

    def test_validate_production_config_external_provider_integrity(self):
        """Detects when an external provider is enabled without its required API key."""
        s = Settings()
        s.NLP_EXTRACTION_PROVIDER = "gemini"
        s.GEMINI_API_KEY = None
        s.ASR_PROVIDER = "sarvam"
        s.SARVAM_API_KEY = None
        s.LLM_FALLBACK_ENABLED = True
        s.GROQ_API_KEY = None

        errors = validate_production_config(s)
        self.assertTrue(any("gemini_api_key" in e.lower() for e in errors))
        self.assertTrue(any("sarvam_api_key" in e.lower() for e in errors))
        self.assertTrue(any("groq_api_key" in e.lower() for e in errors))

    def test_enforce_production_config_raises_only_in_production(self):
        """enforce_production_config raises in production, but logs non-fatal warnings in development."""
        s = Settings()
        s.ENVIRONMENT = "production"
        s.JWT_SECRET = "insecure-default-change-before-deploy"

        with self.assertRaises(RuntimeError) as ctx:
            enforce_production_config(s)
        self.assertIn("Production startup failed", str(ctx.exception))

        # In development, it should not raise
        s.ENVIRONMENT = "development"
        try:
            enforce_production_config(s)
        except RuntimeError:
            self.fail("enforce_production_config should not raise in development mode")

    # -------------------------------------------------------------------------
    # 5. Health Endpoints Secret & PHI Redaction
    # -------------------------------------------------------------------------

    def test_health_check_endpoint(self):
        """GET /health returns healthy status without internal details."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["service"], "MediKiosk Backend")
        # Ensure no sensitive keys exist
        for key in ("password", "secret", "url", "database", "key"):
            self.assertNotIn(key, data)

    def test_database_health_endpoint_success(self):
        """GET /health/db returns connection status with sanitized details."""
        with patch("app.api.health.check_db_connection", return_value=(True, "Database connection successful")):
            response = self.client.get("/health/db")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertTrue(data["connected"])
            self.assertEqual(data["detail"], "Database connection successful")
            self.assertNotIn("localhost", str(data))
            self.assertNotIn("password", str(data))

    def test_database_health_endpoint_failure_sanitization(self):
        """GET /health/db returns safe failure message when database fails."""
        with patch("app.api.health.check_db_connection", return_value=(False, "Database connection failed")):
            response = self.client.get("/health/db")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertFalse(data["connected"])
            self.assertEqual(data["detail"], "Database connection failed")

    def test_service_status_health_endpoint(self):
        """GET /health/status reports configuration state without secrets or network calls."""
        response = self.client.get("/health/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "operational")
        self.assertIn("providers", data)
        providers = data["providers"]
        self.assertIn("storage", providers)
        self.assertIn("llm_fallback", providers)

        # Ensure all provider statuses are safe descriptors ('mock', 'configured', 'local', 'enabled', 'disabled')
        allowed_descriptors = {"mock", "configured", "local", "enabled", "disabled"}
        for k, v in providers.items():
            self.assertIn(v, allowed_descriptors, f"Unexpected provider status value: {v} for {k}")

        # Ensure zero credentials or keys leaked in JSON
        raw_text = response.text.lower()
        self.assertNotIn("key", raw_text)
        self.assertNotIn("password", raw_text)
        self.assertNotIn("secret", raw_text)

    def test_health_metrics_endpoint_no_phi(self):
        """GET /health/metrics returns operational metrics without PHI."""
        response = self.client.get("/health/metrics")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("http_requests", data)
        self.assertIn("providers", data)
        self.assertIn("pipeline_stages", data)

        # Check for forbidden PHI fields
        for bad_key in FORBIDDEN_METADATA_KEYS:
            self.assertNotIn(bad_key, data)

    # -------------------------------------------------------------------------
    # 6. Logging & Observability PHI Protection
    # -------------------------------------------------------------------------

    def test_operational_logging_strips_forbidden_phi_and_secrets(self):
        """Verify log_operational_event strips any forbidden metadata keys."""
        with patch("app.core.observability.logger.info") as mock_log:
            log_operational_event(
                event_name="test_event",
                patient_name="John Doe",
                phone_number="+919876543210",
                password="secret_pass_123",
                secret="some_api_secret",
                transcript="Patient says chest pain",
                ocr_text="Medical report text",
                interview_id=42,
                document_id=7,
            )
            mock_log.assert_called_once()
            logged_payload = mock_log.call_args[0][0]

            # Allowed operational IDs
            self.assertIn('"interview_id": 42', logged_payload)
            self.assertIn('"document_id": 7', logged_payload)

            # Forbidden keys must be stripped
            self.assertNotIn("John Doe", logged_payload)
            self.assertNotIn("+919876543210", logged_payload)
            self.assertNotIn("secret_pass_123", logged_payload)
            self.assertNotIn("chest pain", logged_payload)
            self.assertNotIn("Medical report text", logged_payload)

    # -------------------------------------------------------------------------
    # 7. Render Port and Host Configuration
    # -------------------------------------------------------------------------

    def test_render_port_and_host_configuration(self):
        """Verify application honors Render PORT and HOST environment variables."""
        with patch.dict(os.environ, {"PORT": "10000", "HOST": "0.0.0.0"}):
            s = Settings()
            self.assertEqual(s.PORT, 10000)
            self.assertEqual(s.HOST, "0.0.0.0")

    # -------------------------------------------------------------------------
    # 8. Test Environment Invariants
    # -------------------------------------------------------------------------

    def test_test_environment_requires_zero_live_credentials(self):
        """Verify default test settings do not demand live credentials."""
        s = Settings()
        self.assertEqual(s.OCR_PROVIDER, "mock")
        self.assertEqual(s.EXTRACTION_PROVIDER, "mock")
        self.assertEqual(s.NLP_EXTRACTION_PROVIDER, "mock")
        self.assertEqual(s.SUMMARY_PROVIDER, "mock")
        self.assertEqual(s.TRANSLATION_PROVIDER, "mock")
        self.assertEqual(s.ASR_PROVIDER, "mock")
        self.assertEqual(s.DOCUMENT_STORAGE_PROVIDER, "local")
        self.assertFalse(s.LLM_FALLBACK_ENABLED)


if __name__ == "__main__":
    unittest.main()
