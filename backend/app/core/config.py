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
    # DOCUMENT_STORAGE_PROVIDER selects the storage backend explicitly.
    # Supported values: "local" (safe default for tests/dev), "cloudinary" (production).
    # STORAGE_PROVIDER is the legacy alias; DOCUMENT_STORAGE_PROVIDER takes precedence.
    STORAGE_PROVIDER: str = os.getenv("STORAGE_PROVIDER", "local")
    DOCUMENT_STORAGE_PROVIDER: str = os.getenv(
        "DOCUMENT_STORAGE_PROVIDER",
        os.getenv("STORAGE_PROVIDER", "local"),
    )
    MAX_DOCUMENT_SIZE_MB: int = int(os.getenv("MAX_DOCUMENT_SIZE_MB", "10"))
    LOCAL_STORAGE_PATH: Path = Path(os.getenv("LOCAL_STORAGE_PATH", str(BASE_DIR / "uploads")))

    # OCR, NLP and AI Provider Configuration
    OCR_PROVIDER: str = os.getenv("OCR_PROVIDER", "mock")
    EXTRACTION_PROVIDER: str = os.getenv("EXTRACTION_PROVIDER", "mock")
    NLP_EXTRACTION_PROVIDER: str = os.getenv("NLP_EXTRACTION_PROVIDER", "mock")
    SUMMARY_PROVIDER: str = os.getenv("SUMMARY_PROVIDER", "mock")
    TRANSLATION_PROVIDER: str = os.getenv("TRANSLATION_PROVIDER", "mock")
    ASR_PROVIDER: str = os.getenv("ASR_PROVIDER", "mock")
    TTS_PROVIDER: str = os.getenv("TTS_PROVIDER", "mock")

    # Gemini API Configuration
    GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash"))
    GEMINI_MODEL_NAME: str = GEMINI_MODEL
    GEMINI_TIMEOUT_SECONDS: int = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "15"))

    # Sarvam AI ASR & OCR Configuration
    SARVAM_API_KEY: str | None = os.getenv("SARVAM_API_KEY")
    SARVAM_MODEL: str = os.getenv("SARVAM_MODEL", os.getenv("SARVAM_MODEL_NAME", "saaras:v3"))
    SARVAM_MODEL_NAME: str = SARVAM_MODEL
    SARVAM_TIMEOUT_SECONDS: int = int(os.getenv("SARVAM_TIMEOUT_SECONDS", "15"))
    SARVAM_TTS_MODEL: str = os.getenv("SARVAM_TTS_MODEL", "bulbul:v1")

    # Step 21C: Controlled LLM Fallback (Gemini -> Groq)
    LLM_FALLBACK_ENABLED: bool = os.getenv("LLM_FALLBACK_ENABLED", "false").lower() in ("true", "1", "yes")
    GROQ_API_KEY: str | None = os.getenv("GROQ_API_KEY")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", os.getenv("GROQ_MODEL_NAME", "openai/gpt-oss-120b"))
    GROQ_MODEL_NAME: str = GROQ_MODEL
    GROQ_TIMEOUT_SECONDS: int = int(os.getenv("GROQ_TIMEOUT_SECONDS", "15"))

    # Step 17: JWT Authentication Configuration
    # JWT_SECRET must be set via environment variable. The default value is
    # intentionally insecure and will cause a startup warning if not overridden.
    JWT_SECRET: str = os.getenv(
        "JWT_SECRET",
        "INSECURE-DEFAULT-CHANGE-BEFORE-DEPLOY",
    )
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    )

    # Step 18: CORS & Security Configuration
    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip()
    ]
    CORS_ALLOW_CREDENTIALS: bool = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() in ("true", "1", "yes")

    # Step 18: In-Memory Rate Limiting Configuration (Authentication)
    RATE_LIMIT_LOGIN_MAX_ATTEMPTS: int = int(os.getenv("RATE_LIMIT_LOGIN_MAX_ATTEMPTS", "5"))
    RATE_LIMIT_LOGIN_WINDOW_SECONDS: int = int(os.getenv("RATE_LIMIT_LOGIN_WINDOW_SECONDS", "60"))


    # AI/OCR Confidence Thresholds (Feature 21)
    # Scores are provider-supplied values in [0.0, 1.0].
    # HIGH:   score >= CONFIDENCE_HIGH_THRESHOLD
    # MEDIUM: score >= CONFIDENCE_MEDIUM_THRESHOLD and < HIGH
    # LOW:    score <  CONFIDENCE_MEDIUM_THRESHOLD
    # UNKNOWN: score is None (provider did not supply one)
    # Do NOT hard-code clinical assumptions into these thresholds.
    CONFIDENCE_HIGH_THRESHOLD: float = float(os.getenv("CONFIDENCE_HIGH_THRESHOLD", "0.85"))
    CONFIDENCE_MEDIUM_THRESHOLD: float = float(os.getenv("CONFIDENCE_MEDIUM_THRESHOLD", "0.60"))

    # Step 22: Cloudinary Document Storage (optional/configuration-driven)
    # Activated ONLY when DOCUMENT_STORAGE_PROVIDER=cloudinary and all three credentials are set.
    # Never expose CLOUDINARY_API_KEY or CLOUDINARY_API_SECRET in logs, URLs, or API responses.
    CLOUDINARY_CLOUD_NAME: str | None = os.getenv("CLOUDINARY_CLOUD_NAME")
    CLOUDINARY_API_KEY: str | None = os.getenv("CLOUDINARY_API_KEY")
    CLOUDINARY_API_SECRET: str | None = os.getenv("CLOUDINARY_API_SECRET")
    # Documents are stored under this folder path inside Cloudinary.
    CLOUDINARY_FOLDER: str = os.getenv("CLOUDINARY_FOLDER", "medikiosk_documents")
    CLOUDINARY_TIMEOUT_SECONDS: int = int(os.getenv("CLOUDINARY_TIMEOUT_SECONDS", "15"))

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

    # Step 23: Environment & Deployment Configuration
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", os.getenv("APP_ENV", "development")).lower()
    PORT: int = int(os.getenv("PORT", "8000"))
    HOST: str = os.getenv("HOST", "0.0.0.0")

    # Step 23: Production Database Connection Pooling
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "5"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    DB_POOL_TIMEOUT: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "1800"))
    DB_POOL_PRE_PING: bool = os.getenv("DB_POOL_PRE_PING", "true").lower() in ("true", "1", "yes")

    def __init__(self):
        self.reload()

    def reload(self):
        """Reload configuration values from current os.environ."""
        self.POSTGRES_USER = os.getenv("POSTGRES_USER")
        self.POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
        self.POSTGRES_HOST = os.getenv("POSTGRES_HOST")
        self.POSTGRES_PORT = os.getenv("POSTGRES_PORT")
        self.POSTGRES_DB = os.getenv("POSTGRES_DB")

        self.STORAGE_PROVIDER = os.getenv("STORAGE_PROVIDER", "local")
        self.DOCUMENT_STORAGE_PROVIDER = os.getenv(
            "DOCUMENT_STORAGE_PROVIDER",
            os.getenv("STORAGE_PROVIDER", "local"),
        )
        self.MAX_DOCUMENT_SIZE_MB = int(os.getenv("MAX_DOCUMENT_SIZE_MB", "10"))
        self.LOCAL_STORAGE_PATH = Path(os.getenv("LOCAL_STORAGE_PATH", str(BASE_DIR / "uploads")))

        self.OCR_PROVIDER = os.getenv("OCR_PROVIDER", "mock")
        self.EXTRACTION_PROVIDER = os.getenv("EXTRACTION_PROVIDER", "mock")
        self.NLP_EXTRACTION_PROVIDER = os.getenv("NLP_EXTRACTION_PROVIDER", "mock")
        self.SUMMARY_PROVIDER = os.getenv("SUMMARY_PROVIDER", "mock")
        self.TRANSLATION_PROVIDER = os.getenv("TRANSLATION_PROVIDER", "mock")
        self.ASR_PROVIDER = os.getenv("ASR_PROVIDER", "mock")
        self.TTS_PROVIDER = os.getenv("TTS_PROVIDER", "mock")

        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        self.GEMINI_MODEL = os.getenv("GEMINI_MODEL", os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash"))
        self.GEMINI_MODEL_NAME = self.GEMINI_MODEL
        self.GEMINI_TIMEOUT_SECONDS = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "15"))

        self.SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
        self.SARVAM_MODEL = os.getenv("SARVAM_MODEL", os.getenv("SARVAM_MODEL_NAME", "saaras:v3"))
        self.SARVAM_MODEL_NAME = self.SARVAM_MODEL
        self.SARVAM_TIMEOUT_SECONDS = int(os.getenv("SARVAM_TIMEOUT_SECONDS", "15"))
        self.SARVAM_TTS_MODEL = os.getenv("SARVAM_TTS_MODEL", "bulbul:v1")

        self.LLM_FALLBACK_ENABLED = os.getenv("LLM_FALLBACK_ENABLED", "false").lower() in ("true", "1", "yes")
        self.GROQ_API_KEY = os.getenv("GROQ_API_KEY")
        self.GROQ_MODEL = os.getenv("GROQ_MODEL", os.getenv("GROQ_MODEL_NAME", "openai/gpt-oss-120b"))
        self.GROQ_MODEL_NAME = self.GROQ_MODEL
        self.GROQ_TIMEOUT_SECONDS = int(os.getenv("GROQ_TIMEOUT_SECONDS", "15"))

        self.JWT_SECRET = os.getenv(
            "JWT_SECRET",
            "INSECURE-DEFAULT-CHANGE-BEFORE-DEPLOY",
        )
        self.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(
            os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60")
        )

        self.CORS_ORIGINS = [
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS",
                "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173",
            ).split(",")
            if origin.strip()
        ]
        self.CORS_ALLOW_CREDENTIALS = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() in ("true", "1", "yes")

        self.RATE_LIMIT_LOGIN_MAX_ATTEMPTS = int(os.getenv("RATE_LIMIT_LOGIN_MAX_ATTEMPTS", "5"))
        self.RATE_LIMIT_LOGIN_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_LOGIN_WINDOW_SECONDS", "60"))

        self.CONFIDENCE_HIGH_THRESHOLD = float(os.getenv("CONFIDENCE_HIGH_THRESHOLD", "0.85"))
        self.CONFIDENCE_MEDIUM_THRESHOLD = float(os.getenv("CONFIDENCE_MEDIUM_THRESHOLD", "0.60"))

        self.CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
        self.CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
        self.CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")
        self.CLOUDINARY_FOLDER = os.getenv("CLOUDINARY_FOLDER", "medikiosk_documents")
        self.CLOUDINARY_TIMEOUT_SECONDS = int(os.getenv("CLOUDINARY_TIMEOUT_SECONDS", "15"))

        self.ABDM_ENABLED = os.getenv("ABDM_ENABLED", "true").lower() in ("true", "1", "yes")
        self.ABDM_ENVIRONMENT = os.getenv("ABDM_ENVIRONMENT", "MOCK")
        self.ABDM_BASE_URL = os.getenv("ABDM_BASE_URL")
        self.ABDM_CLIENT_ID = os.getenv("ABDM_CLIENT_ID")
        self.ABDM_CLIENT_SECRET = os.getenv("ABDM_CLIENT_SECRET")
        self.ABDM_TIMEOUT_SECONDS = int(os.getenv("ABDM_TIMEOUT_SECONDS", "10"))

        self.HIS_ENABLED = os.getenv("HIS_ENABLED", "true").lower() in ("true", "1", "yes")
        self.HIS_ENVIRONMENT = os.getenv("HIS_ENVIRONMENT", "MOCK")
        self.HIS_BASE_URL = os.getenv("HIS_BASE_URL")
        self.HIS_CLIENT_ID = os.getenv("HIS_CLIENT_ID")
        self.HIS_CLIENT_SECRET = os.getenv("HIS_CLIENT_SECRET")
        self.HIS_TIMEOUT_SECONDS = int(os.getenv("HIS_TIMEOUT_SECONDS", "15"))

        self.ASR_SILENCE_THRESHOLD_MS = int(os.getenv("ASR_SILENCE_THRESHOLD_MS", "5000"))
        self.SPEECH_QUALITY_FAILURE_WINDOW_MINUTES = int(os.getenv("SPEECH_QUALITY_FAILURE_WINDOW_MINUTES", "15"))
        self.SPEECH_QUALITY_REPEAT_THRESHOLD = int(os.getenv("SPEECH_QUALITY_REPEAT_THRESHOLD", "2"))
        self.SPEECH_QUALITY_TEXT_FALLBACK_THRESHOLD = int(os.getenv("SPEECH_QUALITY_TEXT_FALLBACK_THRESHOLD", "3"))
        self.SPEECH_QUALITY_ASSISTANCE_THRESHOLD = int(os.getenv("SPEECH_QUALITY_ASSISTANCE_THRESHOLD", "4"))

        self.ADAPTIVE_OPEN_TO_GUIDED_THRESHOLD = int(os.getenv("ADAPTIVE_OPEN_TO_GUIDED_THRESHOLD", "2"))
        self.ADAPTIVE_GUIDED_TO_TOUCH_THRESHOLD = int(os.getenv("ADAPTIVE_GUIDED_TO_TOUCH_THRESHOLD", "2"))
        self.ADAPTIVE_TOUCH_TO_ASSISTED_THRESHOLD = int(os.getenv("ADAPTIVE_TOUCH_TO_ASSISTED_THRESHOLD", "2"))

        self.CONTRADICTION_HIGH_SEVERITY_CATEGORIES = os.getenv(
            "CONTRADICTION_HIGH_SEVERITY_CATEGORIES", "ALLERGY,MEDICATION"
        )
        self.CONTRADICTION_LOW_CONFIDENCE_SKIP = os.getenv(
            "CONTRADICTION_LOW_CONFIDENCE_SKIP", "true"
        ).lower() in ("true", "1", "yes")

        self.ENVIRONMENT = os.getenv("ENVIRONMENT", os.getenv("APP_ENV", "development")).lower()
        self.PORT = int(os.getenv("PORT", "8000"))
        self.HOST = os.getenv("HOST", "0.0.0.0")

        self.DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
        self.DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
        self.DB_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))
        self.DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "1800"))
        self.DB_POOL_PRE_PING = os.getenv("DB_POOL_PRE_PING", "true").lower() in ("true", "1", "yes")

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT in ("production", "prod")

    @property
    def is_test(self) -> bool:
        return self.ENVIRONMENT in ("test", "testing")

    @property
    def database_url(self) -> str | None:
        direct_url = os.getenv("DATABASE_URL")
        if direct_url:
            direct_url = direct_url.strip()
            # Render / Heroku compatibility: normalize postgres:// and postgresql:// to postgresql+psycopg://
            if direct_url.startswith("postgres://"):
                return "postgresql+psycopg://" + direct_url[len("postgres://"):]
            elif direct_url.startswith("postgresql://") and not direct_url.startswith("postgresql+"):
                return "postgresql+psycopg://" + direct_url[len("postgresql://"):]
            return direct_url

        if not all([self.POSTGRES_USER, self.POSTGRES_PASSWORD, self.POSTGRES_HOST, self.POSTGRES_PORT, self.POSTGRES_DB]):
            return None

        user = quote_plus(self.POSTGRES_USER)
        password = quote_plus(self.POSTGRES_PASSWORD)
        return f"postgresql+psycopg://{user}:{password}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"


KNOWN_INSECURE_JWT_SECRETS = {
    "insecure-default-change-before-deploy",
    "change-me-use-a-secure-random-value-in-production",
    "dev-only-secret-not-for-production-change-before-deploy",
    "secret",
    "changeme",
    "password",
    "default",
}


def validate_production_config(settings_obj: Settings | None = None) -> list[str]:
    """
    Validate production readiness of backend configuration.
    Returns a list of configuration error messages (empty list if completely valid).
    Zero secrets or credentials are ever reflected in the returned messages.
    """
    cfg = settings_obj or settings
    errors: list[str] = []

    # 1. Database Configuration
    if not cfg.database_url:
        errors.append(
            "Production database configuration missing: DATABASE_URL (or POSTGRES_* variables) must be set."
        )

    # 2. JWT Secret Safety
    jwt_secret = (cfg.JWT_SECRET or "").strip()
    if not jwt_secret:
        errors.append("Production security configuration missing: JWT_SECRET must be set.")
    elif jwt_secret.lower() in KNOWN_INSECURE_JWT_SECRETS or len(jwt_secret) < 32:
        errors.append(
            "Insecure JWT_SECRET detected for production. Must be a cryptographically random secret of at least 32 characters."
        )

    # 3. CORS Invariants
    if not cfg.CORS_ORIGINS:
        errors.append("CORS_ORIGINS must specify at least one explicitly allowed origin in production.")
    elif "*" in cfg.CORS_ORIGINS and cfg.CORS_ALLOW_CREDENTIALS:
        errors.append("Wildcard CORS origin ('*') with credentials enabled is forbidden in production.")

    # 4. Storage Selection
    storage_provider = (cfg.DOCUMENT_STORAGE_PROVIDER or "").lower()
    if storage_provider == "cloudinary":
        missing_cloudinary = []
        if not cfg.CLOUDINARY_CLOUD_NAME:
            missing_cloudinary.append("CLOUDINARY_CLOUD_NAME")
        if not cfg.CLOUDINARY_API_KEY:
            missing_cloudinary.append("CLOUDINARY_API_KEY")
        if not cfg.CLOUDINARY_API_SECRET:
            missing_cloudinary.append("CLOUDINARY_API_SECRET")
        if missing_cloudinary:
            errors.append(
                f"Cloudinary storage provider selected but required credentials missing: {', '.join(missing_cloudinary)}."
            )

    # 5. External Provider Config Integrity (fail-closed if enabled without key)
    gemini_providers = [
        ("NLP_EXTRACTION_PROVIDER", cfg.NLP_EXTRACTION_PROVIDER),
        ("EXTRACTION_PROVIDER", cfg.EXTRACTION_PROVIDER),
        ("SUMMARY_PROVIDER", cfg.SUMMARY_PROVIDER),
        ("TRANSLATION_PROVIDER", cfg.TRANSLATION_PROVIDER),
    ]
    for name, val in gemini_providers:
        if (val or "").lower() == "gemini" and not cfg.GEMINI_API_KEY:
            errors.append(f"{name} is configured as 'gemini' but GEMINI_API_KEY is not set.")

    sarvam_providers = [
        ("ASR_PROVIDER", cfg.ASR_PROVIDER),
        ("OCR_PROVIDER", cfg.OCR_PROVIDER),
        ("TTS_PROVIDER", getattr(cfg, "TTS_PROVIDER", "mock")),
    ]
    for name, val in sarvam_providers:
        if (val or "").lower() == "sarvam" and not cfg.SARVAM_API_KEY:
            errors.append(f"{name} is configured as 'sarvam' but SARVAM_API_KEY is not set.")

    if cfg.LLM_FALLBACK_ENABLED and not cfg.GROQ_API_KEY:
        errors.append("LLM_FALLBACK_ENABLED is true but GROQ_API_KEY is not set.")

    return errors


def enforce_production_config(settings_obj: Settings | None = None) -> None:
    """
    Enforce production configuration invariants. Raises RuntimeError on any violation in production.
    In development/test, logs non-fatal warnings for insecure defaults.
    """
    import logging
    logger = logging.getLogger("medikiosk.config")
    cfg = settings_obj or settings

    errors = validate_production_config(cfg)
    if cfg.is_production:
        if errors:
            raise RuntimeError(
                "Production startup failed due to configuration errors:\n - " + "\n - ".join(errors)
            )
    else:
        for err in errors:
            logger.warning("Development configuration notice: %s", err)


settings = Settings()
