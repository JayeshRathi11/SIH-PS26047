from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel

from app.core.config import settings


class HISTransmissionResult(BaseModel):
    success: bool
    external_reference: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    adapter_name: str
    environment: str


class HISAdapter(ABC):
    """
    Abstract interface for transmitting FHIR R4 clinical cases
    to Hospital Information Systems (HIS) / EMRs.
    """

    @abstractmethod
    def transmit(self, bundle: Dict[str, Any], context: Dict[str, Any]) -> HISTransmissionResult:
        pass


class MockHISAdapter(HISAdapter):
    """
    Deterministic mock adapter for testing HIS / EMR interoperability.
    Supports deterministic failure hooks for verification testing.
    """

    def transmit(self, bundle: Dict[str, Any], context: Dict[str, Any]) -> HISTransmissionResult:
        trigger = str(context.get("trigger", "")).upper()

        if "REJECT" in trigger:
            return HISTransmissionResult(
                success=False,
                error_code="HIS_REJECTED",
                error_message="Hospital EMR rejected the case payload: Patient eligibility or bed allocation error.",
                adapter_name="MockHISAdapter",
                environment="MOCK",
            )
        elif "TIMEOUT" in trigger:
            return HISTransmissionResult(
                success=False,
                error_code="HIS_TIMEOUT",
                error_message="Hospital EMR gateway connection timed out.",
                adapter_name="MockHISAdapter",
                environment="MOCK",
            )
        elif "UNAVAILABLE" in trigger:
            return HISTransmissionResult(
                success=False,
                error_code="HIS_UNAVAILABLE",
                error_message="Hospital EMR service is currently unavailable.",
                adapter_name="MockHISAdapter",
                environment="MOCK",
            )

        export_id = context.get("export_id", 1)
        summary_version = context.get("summary_version", 1)
        external_reference = f"HIS-REF-{export_id}-{summary_version}"

        return HISTransmissionResult(
            success=True,
            external_reference=external_reference,
            adapter_name="MockHISAdapter",
            environment="MOCK",
        )


class SandboxHISAdapter(HISAdapter):
    """
    Configuration-ready adapter for external sandbox HIS / EMR endpoints.
    """

    def transmit(self, bundle: Dict[str, Any], context: Dict[str, Any]) -> HISTransmissionResult:
        if not settings.HIS_BASE_URL or not settings.HIS_CLIENT_ID or not settings.HIS_CLIENT_SECRET:
            return HISTransmissionResult(
                success=False,
                error_code="CONFIG_MISSING",
                error_message="Sandbox HIS credentials (HIS_BASE_URL, HIS_CLIENT_ID, HIS_CLIENT_SECRET) missing.",
                adapter_name="SandboxHISAdapter",
                environment="SANDBOX",
            )

        # In sandbox mode, HTTP client calls would be performed here
        return HISTransmissionResult(
            success=False,
            error_code="SANDBOX_NOT_CONNECTED",
            error_message="Sandbox HIS endpoint configured but external network exchange is not connected.",
            adapter_name="SandboxHISAdapter",
            environment="SANDBOX",
        )


def get_his_adapter() -> HISAdapter:
    env = (settings.HIS_ENVIRONMENT or "MOCK").upper()
    if env == "SANDBOX":
        return SandboxHISAdapter()
    return MockHISAdapter()
