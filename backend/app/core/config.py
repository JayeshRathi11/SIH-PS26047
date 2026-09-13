import os
from pathlib import Path
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Load .env file from backend directory if present
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    POSTGRES_USER: str | None = os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD: str | None = os.getenv("POSTGRES_PASSWORD")
    POSTGRES_HOST: str | None = os.getenv("POSTGRES_HOST")
    POSTGRES_PORT: str | None = os.getenv("POSTGRES_PORT")
    POSTGRES_DB: str | None = os.getenv("POSTGRES_DB")

    # Document Storage Configuration
    STORAGE_PROVIDER: str = os.getenv("STORAGE_PROVIDER", "local")
    MAX_DOCUMENT_SIZE_MB: int = int(os.getenv("MAX_DOCUMENT_SIZE_MB", "10"))
    LOCAL_STORAGE_PATH: Path = Path(os.getenv("LOCAL_STORAGE_PATH", str(BASE_DIR / "uploads")))

    # OCR and Medical Extraction Provider Configuration
    OCR_PROVIDER: str = os.getenv("OCR_PROVIDER", "mock")
    EXTRACTION_PROVIDER: str = os.getenv("EXTRACTION_PROVIDER", "mock")
    SUMMARY_PROVIDER: str = os.getenv("SUMMARY_PROVIDER", "mock")
    GEMINI_MODEL_NAME: str = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-flash")
    SARVAM_API_KEY: str | None = os.getenv("SARVAM_API_KEY")
    GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")

    # AI/OCR Confidence Thresholds (Feature 21)
    # Scores are provider-supplied values in [0.0, 1.0].
    # HIGH:   score >= CONFIDENCE_HIGH_THRESHOLD
    # MEDIUM: score >= CONFIDENCE_MEDIUM_THRESHOLD and < HIGH
    # LOW:    score <  CONFIDENCE_MEDIUM_THRESHOLD
    # UNKNOWN: score is None (provider did not supply one)
    # Do NOT hard-code clinical assumptions into these thresholds.
    CONFIDENCE_HIGH_THRESHOLD: float = float(os.getenv("CONFIDENCE_HIGH_THRESHOLD", "0.85"))
    CONFIDENCE_MEDIUM_THRESHOLD: float = float(os.getenv("CONFIDENCE_MEDIUM_THRESHOLD", "0.60"))

    # Cloudinary credentials (optional/configuration-driven)
    CLOUDINARY_CLOUD_NAME: str | None = os.getenv("CLOUDINARY_CLOUD_NAME")
    CLOUDINARY_API_KEY: str | None = os.getenv("CLOUDINARY_API_KEY")
    CLOUDINARY_API_SECRET: str | None = os.getenv("CLOUDINARY_API_SECRET")

    # ABDM / ABHA Integration Configuration
    ABDM_ENABLED: bool = os.getenv("ABDM_ENABLED", "true").lower() in ("true", "1", "yes")
    ABDM_ENVIRONMENT: str = os.getenv("ABDM_ENVIRONMENT", "MOCK")
    ABDM_BASE_URL: str | None = os.getenv("ABDM_BASE_URL")
    ABDM_CLIENT_ID: str | None = os.getenv("ABDM_CLIENT_ID")
    ABDM_CLIENT_SECRET: str | None = os.getenv("ABDM_CLIENT_SECRET")
    ABDM_TIMEOUT_SECONDS: int = int(os.getenv("ABDM_TIMEOUT_SECONDS", "10"))

    # HIS / EMR Integration Configuration
    HIS_ENABLED: bool = os.getenv("HIS_ENABLED", "true").lower() in ("true", "1", "yes")
    HIS_ENVIRONMENT: str = os.getenv("HIS_ENVIRONMENT", "MOCK")
    HIS_BASE_URL: str | None = os.getenv("HIS_BASE_URL")
    HIS_CLIENT_ID: str | None = os.getenv("HIS_CLIENT_ID")
    HIS_CLIENT_SECRET: str | None = os.getenv("HIS_CLIENT_SECRET")
    HIS_TIMEOUT_SECONDS: int = int(os.getenv("HIS_TIMEOUT_SECONDS", "15"))

    # Feature 26: Noise & Speech Quality Configuration
    ASR_SILENCE_THRESHOLD_MS: int = int(os.getenv("ASR_SILENCE_THRESHOLD_MS", "5000"))
    SPEECH_QUALITY_FAILURE_WINDOW_MINUTES: int = int(os.getenv("SPEECH_QUALITY_FAILURE_WINDOW_MINUTES", "15"))
    SPEECH_QUALITY_REPEAT_THRESHOLD: int = int(os.getenv("SPEECH_QUALITY_REPEAT_THRESHOLD", "2"))
    SPEECH_QUALITY_TEXT_FALLBACK_THRESHOLD: int = int(os.getenv("SPEECH_QUALITY_TEXT_FALLBACK_THRESHOLD", "3"))
    SPEECH_QUALITY_ASSISTANCE_THRESHOLD: int = int(os.getenv("SPEECH_QUALITY_ASSISTANCE_THRESHOLD", "4"))

    # Feature 27: Adaptive Accessibility Engine — Presentation Mode Thresholds
    # These thresholds control when the state machine transitions between
    # presentation modes based on accumulated difficulty signals.
    # They control HOW questions are presented, NOT clinical decisions.
    ADAPTIVE_OPEN_TO_GUIDED_THRESHOLD: int = int(os.getenv("ADAPTIVE_OPEN_TO_GUIDED_THRESHOLD", "2"))
    ADAPTIVE_GUIDED_TO_TOUCH_THRESHOLD: int = int(os.getenv("ADAPTIVE_GUIDED_TO_TOUCH_THRESHOLD", "2"))
    ADAPTIVE_TOUCH_TO_ASSISTED_THRESHOLD: int = int(os.getenv("ADAPTIVE_TOUCH_TO_ASSISTED_THRESHOLD", "2"))

    # Feature 28: Multi-Source Contradiction Engine
    # Severity rules for contradiction categories.
    # HIGH_SEVERITY_CATEGORIES: comma-separated category names that receive HIGH severity by default.
    # LOW_CONFIDENCE_SKIP: if True, skip comparisons where BOTH sides have LOW confidence.
    CONTRADICTION_HIGH_SEVERITY_CATEGORIES: str = os.getenv(
        "CONTRADICTION_HIGH_SEVERITY_CATEGORIES", "ALLERGY,MEDICATION"
    )
    CONTRADICTION_LOW_CONFIDENCE_SKIP: bool = os.getenv(
        "CONTRADICTION_LOW_CONFIDENCE_SKIP", "true"
    ).lower() in ("true", "1", "yes")

    @property
    def database_url(self) -> str | None:
        direct_url = os.getenv("DATABASE_URL")
        if direct_url:
            return direct_url

        if not all([self.POSTGRES_USER, self.POSTGRES_PASSWORD, self.POSTGRES_HOST, self.POSTGRES_PORT, self.POSTGRES_DB]):
            return None

        user = quote_plus(self.POSTGRES_USER)
        password = quote_plus(self.POSTGRES_PASSWORD)
        return f"postgresql+psycopg://{user}:{password}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"


settings = Settings()
