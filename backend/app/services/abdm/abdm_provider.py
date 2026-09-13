import re
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel
from app.core.config import settings


class AbhaVerificationResult(BaseModel):
    verified: bool
    abha_id: str
    abha_address: Optional[str] = None
    profile_data: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class ABDMProvider(ABC):
    @abstractmethod
    def verify_and_fetch_profile(
        self, abha_id: str, abha_address: Optional[str] = None
    ) -> AbhaVerificationResult:
        """
        Verify ABHA health identity and fetch minimal profile verification data.
        """
        pass


class MockABDMProvider(ABDMProvider):
    """
    Deterministic mock provider for ABDM/ABHA integration.
    Allows local development and automated testing without live credentials.
    """

    def verify_and_fetch_profile(
        self, abha_id: str, abha_address: Optional[str] = None
    ) -> AbhaVerificationResult:
        clean_id = abha_id.strip()

        # Simulated test failure triggers
        if "FAIL" in clean_id or clean_id == "99-9999-9999-9999":
            return AbhaVerificationResult(
                verified=False,
                abha_id=clean_id,
                abha_address=abha_address,
                error_code="ABDM_VERIFICATION_FAILED",
                error_message="ABHA verification failed: Record not found in national registry.",
            )

        if "TIMEOUT" in clean_id:
            raise TimeoutError("Simulated ABDM connection timeout after 10s")

        if "UNAVAILABLE" in clean_id:
            raise ConnectionError("Simulated ABDM gateway service temporarily unavailable (HTTP 503)")

        # Normal deterministic verification
        resolved_address = abha_address or f"patient.{clean_id.replace('-', '')[:8]}@abdm"
        return AbhaVerificationResult(
            verified=True,
            abha_id=clean_id,
            abha_address=resolved_address,
            profile_data={
                "name": "Verified ABHA User",
                "gender": "M",
                "date_of_birth": "1990-01-01",
                "verification_type": "MOCK_SYNC_VERIFIED",
            },
        )


class SandboxABDMProvider(ABDMProvider):
    """
    API-ready adapter for ABDM Sandbox environment.
    Validates required configuration and prepares for live gateway communication.
    """

    def __init__(self):
        if not settings.ABDM_BASE_URL or not settings.ABDM_CLIENT_ID or not settings.ABDM_CLIENT_SECRET:
            raise ValueError(
                "ABDM Sandbox environment is selected, but required configuration "
                "(ABDM_BASE_URL, ABDM_CLIENT_ID, ABDM_CLIENT_SECRET) is missing. "
                "Please configure them in environment variables."
            )
        self.base_url = settings.ABDM_BASE_URL
        self.client_id = settings.ABDM_CLIENT_ID
        self.client_secret = settings.ABDM_CLIENT_SECRET
        self.timeout = settings.ABDM_TIMEOUT_SECONDS

    def verify_and_fetch_profile(
        self, abha_id: str, abha_address: Optional[str] = None
    ) -> AbhaVerificationResult:
        # In sandbox mode, structured gateway call would be executed here
        raise NotImplementedError(
            "Live Sandbox ABDM connectivity is not configured for local execution. "
            "Please use ABDM_ENVIRONMENT=MOCK for development and testing."
        )


def get_abdm_provider() -> ABDMProvider:
    env = (settings.ABDM_ENVIRONMENT or "MOCK").upper()
    if env == "MOCK":
        return MockABDMProvider()
    elif env in ("SANDBOX", "PRODUCTION"):
        return SandboxABDMProvider()
    else:
        raise ValueError(f"Unsupported ABDM_ENVIRONMENT: '{env}'. Supported values: MOCK, SANDBOX, PRODUCTION.")
