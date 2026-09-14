import logging
import re
import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.metrics import operational_metrics, OperationalMetrics
from app.core.observability import (
    sanitize_request_id,
    classify_error,
    log_operational_event,
    get_current_request_id,
    set_current_request_id,
    ErrorCategory,
    FORBIDDEN_METADATA_KEYS,
)
from app.core.provider_errors import (
    ProviderNetworkError,
    ProviderAuthError,
    ProviderConfigError,
    ProviderResponseError,
)
from app.models.patient_consent import ConsentPurpose
from app.services.consent_service import ConsentRequiredException


class TestStep19Observability(unittest.TestCase):
    """
    Step 19 Verification:
    - Standardized Correlation IDs (X-Request-ID generation, propagation, sanitization)
    - Request Logging Middleware (privacy-safe, no tokens/passwords/bodies/query params/PHI)
    - Error Categorization
    - Bounded In-Process Metrics (thread-safe, zero PHI labels, bounded cardinality)
    - Health Endpoints (/health, /health/db, /health/status, /health/metrics)
    - Pipeline Stage Observability (structured events with zero PHI)
    """

    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)
        operational_metrics.reset()

    def tearDown(self):
        operational_metrics.reset()

    # ==========================================
    # 1. Correlation ID (X-Request-ID)
    # ==========================================

    def test_request_id_generated_when_absent(self):
        """When client does not send X-Request-ID, the server generates a valid UUIDv4 and returns it."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        req_id = response.headers.get("X-Request-ID")
        self.assertIsNotNone(req_id)
        # Should match UUIDv4 format
        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
            re.IGNORECASE,
        )
        self.assertTrue(uuid_pattern.match(req_id), f"Generated ID {req_id} is not valid UUIDv4")

    def test_request_id_propagated_when_valid(self):
        """When client sends a valid X-Request-ID, the server propagates it into the response header."""
        custom_id = "req-test-client-9988-safe"
        response = self.client.get("/health", headers={"X-Request-ID": custom_id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-Request-ID"), custom_id)

    def test_request_id_sanitized_when_oversized(self):
        """When client sends an ID exceeding 64 chars, it is sanitized and replaced with a valid UUIDv4."""
        oversized_id = "a" * 100
        response = self.client.get("/health", headers={"X-Request-ID": oversized_id})
        self.assertEqual(response.status_code, 200)
        req_id = response.headers.get("X-Request-ID")
        self.assertNotEqual(req_id, oversized_id)
        self.assertLessEqual(len(req_id), 64)

    def test_request_id_sanitized_when_malicious_characters(self):
        """When client sends an ID with forbidden characters (e.g. SQL injection, path traversal), it is replaced."""
        bad_ids = [
            "id; DROP TABLE users;--",
            "../../../etc/passwd",
            "id<script>alert(1)</script>",
            "id with spaces",
            "id\nwith\nnewlines",
            "id\x00nullbyte",
        ]
        for bad_id in bad_ids:
            sanitized = sanitize_request_id(bad_id)
            self.assertNotEqual(sanitized, bad_id)
            self.assertRegex(sanitized, r"^[0-9a-f\-]+$")

    def test_request_id_present_on_404(self):
        """X-Request-ID is present even on 404 Not Found."""
        response = self.client.get("/non-existent-path-for-testing")
        self.assertEqual(response.status_code, 404)
        self.assertIn("X-Request-ID", response.headers)

    def test_request_id_present_on_422_validation_error(self):
        """X-Request-ID is present on 422 Unprocessable Entity and included in the JSON body."""
        # POST to /api/auth/login with empty invalid JSON
        response = self.client.post("/api/auth/login", json={})
        self.assertEqual(response.status_code, 422)
        req_id = response.headers.get("X-Request-ID")
        self.assertIsNotNone(req_id)
        data = response.json()
        self.assertIn("request_id", data)
        self.assertEqual(data["request_id"], req_id)

    def test_request_id_present_on_500_internal_server_error(self):
        """Unhandled 500 error sanitizes error details, includes request_id in payload, and sets X-Request-ID header."""
        with patch("app.api.health.check_db_connection", side_effect=RuntimeError("Unhandled internal fault")):
            response = self.client.get("/health/db")
            self.assertEqual(response.status_code, 500)
            req_id = response.headers.get("X-Request-ID")
            self.assertIsNotNone(req_id)
            data = response.json()
            self.assertEqual(data.get("request_id"), req_id)
            self.assertEqual(data.get("error"), "INTERNAL_SERVER_ERROR")
            # Verify that internal traceback / exception details are NOT exposed
            self.assertNotIn("RuntimeError", str(data))
            self.assertNotIn("Unhandled internal fault", str(data))

    # ==========================================
    # 2. Error Categorization
    # ==========================================

    def test_classify_error_categories(self):
        """classify_error maps exceptions to appropriate operational categories."""
        self.assertEqual(
            classify_error(ProviderNetworkError("Connection refused")),
            ErrorCategory.PROVIDER_NETWORK_FAILURE.value,
        )
        self.assertEqual(
            classify_error(ProviderAuthError("Invalid API key")),
            ErrorCategory.PROVIDER_AUTH_FAILURE.value,
        )
        self.assertEqual(
            classify_error(ProviderConfigError("Missing secret")),
            ErrorCategory.PROVIDER_CONFIG_FAILURE.value,
        )
        self.assertEqual(
            classify_error(ProviderResponseError("Malformed JSON")),
            ErrorCategory.PROVIDER_RESPONSE_FAILURE.value,
        )
        self.assertEqual(
            classify_error(ConsentRequiredException(ConsentPurpose.DATA_SHARING, "Consent missing", patient_id=1)),
            ErrorCategory.CONSENT_FAILURE.value,
        )
        self.assertEqual(
            classify_error(PermissionError("Denied")),
            ErrorCategory.AUTHORIZATION_FAILURE.value,
        )
        self.assertEqual(
            classify_error(ValueError("validation error")),
            ErrorCategory.VALIDATION_FAILURE.value,
        )
        self.assertEqual(
            classify_error(RuntimeError("Unknown bug")),
            ErrorCategory.UNEXPECTED_INTERNAL_FAILURE.value,
        )

    # ==========================================
    # 3. Privacy-Safe Structured Logging
    # ==========================================

    def test_log_operational_event_filters_forbidden_phi_keys(self):
        """log_operational_event strictly filters out clinical content, tokens, passwords, and transcripts."""
        with self.assertLogs("medikiosk.observability", level="INFO") as captured:
            log_operational_event(
                "test_event",
                stage="test_stage",
                status="success",
                duration_ms=45.2,
                interview_id="iv-123",
                document_id="doc-456",
                safe_adapter="mock",
                page_count=3,
                password="supersecretpassword",
                token="bearer jwt.token.here",
                transcript="Patient complains of severe acute chest pain",
                clinical_summary="Diagnosis: Acute myocardial infarction",
                raw_text="Hospital admission clinical notes",
                audio_content=b"binary_audio_data",
                patient_name="Rushi",
            )

        log_output = "\n".join(captured.output)
        # Safe fields present
        self.assertIn("test_event", log_output)
        self.assertIn("test_stage", log_output)
        self.assertIn("iv-123", log_output)
        self.assertIn("doc-456", log_output)
        self.assertIn("safe_adapter", log_output)
        self.assertIn("page_count", log_output)

        # PHI / Secrets strictly absent
        self.assertNotIn("supersecretpassword", log_output)
        self.assertNotIn("jwt.token.here", log_output)
        self.assertNotIn("severe acute chest pain", log_output)
        self.assertNotIn("Acute myocardial infarction", log_output)
        self.assertNotIn("Hospital admission clinical notes", log_output)
        self.assertNotIn("Rushi", log_output)

    def test_request_logging_middleware_privacy(self):
        """Request logging does not output Authorization headers, request body, query params or PHI."""
        with self.assertLogs("medikiosk.observability", level="INFO") as captured:
            headers = {
                "Authorization": "Bearer super-secret-bearer-token-12345",
                "Cookie": "session_id=confidential_cookie_value",
            }
            # Send request with sensitive query param
            response = self.client.get("/health?api_key=secret_in_url&phone=9876543210", headers=headers)
            self.assertEqual(response.status_code, 200)

        log_output = "\n".join(captured.output)
        # Method and path are logged
        self.assertIn("GET", log_output)
        self.assertIn("/health", log_output)
        # Secrets and query parameters are NOT in logs
        self.assertNotIn("super-secret-bearer-token-12345", log_output)
        self.assertNotIn("confidential_cookie_value", log_output)
        self.assertNotIn("secret_in_url", log_output)
        self.assertNotIn("9876543210", log_output)

    # ==========================================
    # 4. In-Process Thread-Safe Operational Metrics
    # ==========================================

    def test_operational_metrics_recording_and_snapshot(self):
        """Operational metrics record requests, provider calls, and pipeline stages with bounded cardinality."""
        metrics = OperationalMetrics()

        # Record HTTP requests
        metrics.record_request("GET", 200, 15.0)
        metrics.record_request("GET", 200, 25.0)
        metrics.record_request("POST", 400, 10.0)
        metrics.record_request("POST", 500, 50.0)

        # Record provider calls
        metrics.record_provider_call("gemini", "generate_summary", success=True)
        metrics.record_provider_call("gemini", "generate_summary", success=False, error_category="provider_network")
        metrics.record_provider_call("sarvam", "transcribe", success=True)

        # Record pipeline stages
        metrics.record_pipeline_stage("voice_asr", success=True, duration_ms=120.0)
        metrics.record_pipeline_stage("interview_nlp", success=True, duration_ms=250.0)
        metrics.record_pipeline_stage("his_export", success=False, duration_ms=40.0, error_category="provider_response")

        snapshot = metrics.get_metrics_snapshot()

        # Check HTTP stats
        self.assertEqual(snapshot["http_requests"]["total"], 4)
        self.assertEqual(snapshot["http_requests"]["by_method_and_status"]["GET_2xx"], 2)
        self.assertEqual(snapshot["http_requests"]["by_method_and_status"]["POST_4xx"], 1)
        self.assertEqual(snapshot["http_requests"]["by_method_and_status"]["POST_5xx"], 1)
        self.assertEqual(snapshot["http_requests"]["avg_duration_ms"], 25.0)

        # Check Provider stats
        self.assertEqual(snapshot["providers"]["calls"]["gemini_generate_summary"], 2)
        self.assertEqual(snapshot["providers"]["calls"]["sarvam_transcribe"], 1)
        self.assertEqual(snapshot["providers"]["failures"]["gemini_provider_network"], 1)

        # Check Pipeline stages
        self.assertIn("voice_asr", snapshot["pipeline_stages"])
        self.assertEqual(snapshot["pipeline_stages"]["voice_asr"]["success"], 1)
        self.assertEqual(snapshot["pipeline_stages"]["voice_asr"]["avg_duration_ms"], 120.0)
        self.assertEqual(snapshot["pipeline_stages"]["his_export"]["failure"], 1)

    def test_metrics_updated_via_middleware(self):
        """Requests routed through middleware automatically increment operational metrics."""
        self.client.get("/health")
        self.client.get("/health")
        snapshot = operational_metrics.get_metrics_snapshot()
        self.assertGreaterEqual(snapshot["http_requests"]["total"], 2)
        self.assertIn("GET_2xx", snapshot["http_requests"]["by_method_and_status"])

    # ==========================================
    # 5. Health Endpoints
    # ==========================================

    def test_health_check_endpoint(self):
        """GET /health returns healthy status."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["service"], "MediKiosk Backend")

    def test_health_db_endpoint_sanitizes_credentials(self):
        """GET /health/db reports connection status without leaking host or credentials."""
        response = self.client.get("/health/db")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("connected", data)
        self.assertIn("detail", data)
        # Verify no connection string or credentials leaked
        self.assertNotIn("postgresql://", data["detail"].lower())
        self.assertNotIn("password", data["detail"].lower())
        self.assertNotIn("localhost", data["detail"].lower())

    def test_health_status_endpoint_no_secrets(self):
        """GET /health/status reports operational status and provider modes without secrets."""
        response = self.client.get("/health/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "operational")
        self.assertIn("environment", data)
        self.assertIn("providers", data)
        providers = data["providers"]
        for p in ["asr", "ocr", "nlp", "extraction", "summary", "translation", "abdm", "his"]:
            self.assertIn(p, providers)
            self.assertIn(providers[p], ["mock", "configured"])
        # Ensure no secrets leaked in response
        data_str = str(data).lower()
        self.assertNotIn("key", data_str)
        self.assertNotIn("secret", data_str)
        self.assertNotIn("token", data_str)

    def test_health_metrics_endpoint(self):
        """GET /health/metrics returns the operational metrics snapshot."""
        response = self.client.get("/health/metrics")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("http_requests", data)
        self.assertIn("providers", data)
        self.assertIn("pipeline_stages", data)


if __name__ == "__main__":
    unittest.main()
