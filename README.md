# MediKiosk - Smart AYUSH Clinical Triage & Kiosk System (SIH-PS26047)

MediKiosk is an intelligent, multi-lingual, privacy-first healthcare kiosk and clinician triage workstation designed for the National AYUSH Mission. It bridges patient intake, adaptive accessibility, standardized AYUSH clinical documentation (AFI & NAMASTE), and real-time clinician oversight.

---

## 🌟 Newly Implemented Features & Architecture

### 1. Modern Claymorphic Light Ayurveda Frontend (`frontend/src/modern/`)
- **1:1 Visual Fidelity with Authentic Ayurvedic Palette**:
  - Kora Khadi (`#F7F4EB` unbleached canvas), Shweta White (`#FCFAF6` elevated clay), Haritaki Gold (`#C8922A` primary action), Manjistha Red (`#B5402E` emergency triage), and Herbal Green (`#2E6B39` verified status).
  - Pillowy claymorphism with 28px card corners, 20px button radii, double specular highlights, and tactile press depression (`transform: scale(0.97) translateY(2px)`).
- **Complete 11-Screen Modern Suite**:
  - **Screen 0 (`WelcomeScreen.jsx`)**: Multilingual portal (`EN`, `हिन्दी`, `मराठी`) with 4-step journey cards and Hospital Sahayak status.
  - **Screen 1a (`IdentityScreen.jsx` & `ManualEntryScreen.jsx`)**: ABHA QR scan simulation, Mobile OTP, and tactile on-screen numeric keypad (`ClayKeypad.jsx`).
  - **Screen 1b (`ConsentScreen.jsx`)**: DPDP Act 2023 3-clause granular consent with bilingual Web Audio TTS readout (`AudioContext.jsx`).
  - **Screen 2 (`StandardInterviewScreen.jsx` & `AyushParikshaScreen.jsx`)**: Dr. Charaka AI conversational assistant, severity slider, interactive SVG anatomical body map (`ClayBodyMap.jsx`), and Ashtavidha Pariksha matrix.
  - **Screen 2c (`RedFlagAlertScreen.jsx`)**: Manjistha red alert theme, casualty diversion to Room 001, emergency audio siren, and hospital staff dispatch.
  - **Screen 3 (`DocumentScanScreen.jsx`)**: Camera & prescription upload with Sarvam Vision OCR extraction preview cards.
  - **Screen 4 (`PatientSummaryScreen.jsx`)**: Thermal receipt consultation slip, QR code receipt, print action, and Self-Copy modal (WhatsApp/SMS).
  - **Screen 5 (`DoctorDashboardScreen.jsx`)**: Live triage queue sidebar, 8-section AYUSH case sheet editor, red-flag audit widget, AFI/NAMASTE herb autocomplete, and FHIR R4 Bundle export.
  - **Screen 6 (`AnalyticsDashboardScreen.jsx`)**: OPD census telemetry, department distributions, and AI safety precision rates.
- **Non-Destructive Coexistence & Instant Rollback (`frontend/src/legacy/`)**:
  - Untouched legacy frontend preserved 100% intact in `frontend/src/legacy/`.
  - Seamless toggle via query param (`?ui=legacy` vs `?ui=modern`) and floating on-screen developer badge.
- **Developer / QA Screen Launcher (`QaLauncherModal.jsx`)**:
  - Accessible via `Ctrl+Shift+Q` to jump directly into any screen state or inject test patient scenarios.

### 2. Legacy Frontend Architecture (React + Vite + Tailwind CSS)
Located in `frontend/src/legacy/`:
- **Dual-Mode Single Page Application (`AppLegacy.jsx`)**:
  - **रोगी कियोस्क / Patient Kiosk**: 5-step patient registration, DPDP consent, clinical intake, prior record upload, and confirmation.
  - **डॉक्टर वर्कस्टेशन / Doctor Workstation**: Real-time triage dashboard with prioritized OPD queue, 8-section case sheet editor, and contradiction review.
- **Adaptive Accessibility Friction Hook (`useAdaptiveFriction.js`)**:
  - Automatically calculates user interaction friction based on hesitation, silence, and confusion phrases.
  - Dynamically steps down input complexity:
    - **Level 0 (Normal)**: Conversational voice prompts with microphone waveform.
    - **Level 1 (Moderate)**: Spoken/guided multiple-choice symptom pills.
    - **Level 2 (High Friction / Low Literacy)**: 2D Anatomical Body Map (`BodyMapPicker.jsx`) and visual touch cards.
- **2D Interactive Anatomical Body Map (`BodyMapPicker.jsx`)**:
  - Anterior and Posterior body views with clickable anatomical zones (Head, Chest, Abdomen, Joints, Spine, etc.) mapping directly to clinical symptoms.
- **Patient Self-Copy & Digital Receipt Modal (`SelfCopyModal.jsx`)**:
  - Post-consultation digital receipt modal generating:
    - QR Code for instant patient smartphone scan.
    - Simulated SMS dispatch with consultation link.
    - Printable OPD token slip.
- **Clinician-in-the-Loop Red Flag Audit (`RedFlagAuditWidget.jsx`)**:
  - Doctor binary evaluation ("Valid Clinical Alert" / "False Alarm") with optional audit notes logging directly to the backend.
- **8-Section AYUSH Case Sheet (`CaseSheetEditor.jsx`)**:
  - Covers Chief Complaints, History of Present Illness (HPI), Ashtavidha Pariksha (Nadi, Mutra, Mala, Jihva, Shabda, Sparsha, Drik, Akriti), Past History, Medication History with AFI & NAMASTE normalization tags, Allergies, Diagnosis, and Treatment Plan (Chikitsa Sutra).
- **Multi-Source Contradiction Banner**:
  - Surfaces discrepancies between patient voice intake, prior OCR prescriptions, and discharge summaries (e.g. conflicting medication dosages).

### 2. Delta Backend Enhancements (FastAPI)
- **Emergency Contact Phone**:
  - Added `emergency_contact_phone` to `Patient` model, schema, and repository (`backend/app/models/patient.py`, `backend/app/schemas/patient.py`).
- **Weighted Doctor Queue Priority Formula**:
  - Dynamic formula: `(is_red_flag * 1000) + (patient_age >= 65 ? 50 : 0) + (wait_time_minutes * 1.5)`.
  - Implemented in `backend/app/services/opd_queue_service.py` and exposed in `OpdQueueEntryResponse`. Red flags jump to the top, followed by waiting seniors.
- **Clinician Feedback on Algorithmic Red Flags**:
  - `POST /api/interviews/{interview_id}/red-flags/{red_flag_id}/feedback` logging to `clinician_red_flag_feedbacks` table (`backend/app/models/clinician_feedback.py`).
- **AYUSH Entity Normalizer (AFI & NAMASTE)**:
  - `POST /api/ayush/normalize` powered by `AyushEntityNormalizer` with classical formulation catalogs (Ashwagandharishta, Triphala, Sitopaladi, Giloy, etc.) and RapidFuzz matching.
- **Zero-Retention TTL Watchdog**:
  - `POST /api/sessions/watchdog/purge` identifying sessions idle >15 minutes, securely wiping physical/cloud storage assets, setting storage reference to `[PURGED_ZERO_RETENTION]`, and canceling abandoned sessions.
- **Patient Record Self-Copy Endpoints**:
  - `GET /api/interviews/{id}/self-copy/receipt` (digital token & QR payload).
  - `POST /api/interviews/{id}/self-copy/sms` (SMS dispatch simulation).
- **Returning Patient Phone Lookup Flow**:
  - `GET /api/patients/by-phone/{phone_number}` resolving 409 Conflict dead-ends and automatically resuming or creating patient encounter sessions.

---

## 🚀 Running the Project Locally

### 1. Backend Server (FastAPI)
```bash
# Navigate to backend directory
cd backend

# Run uvicorn development server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
- API is live at: `http://127.0.0.1:8000`
- Interactive OpenAPI Docs: `http://127.0.0.1:8000/docs`

### 2. Frontend Application (React + Vite + Tailwind)
```bash
# Navigate to frontend directory
cd frontend

# Install dependencies (first time only)
npm install

# Start Vite dev server
npm run dev
```
- Web Application is live at: `http://127.0.0.1:5173/`
- Production bundle can be built with: `npm run build`

---

## REAL AI PROVIDERS

### 1. Default Mode & Configuration
- **Deterministic Mock Providers are the default** across all 6 backend services:
  - Speech-to-Text (ASR): `ASR_PROVIDER=mock`
  - Document OCR: `OCR_PROVIDER=mock`
  - Conversational NLP Fact Extraction: `NLP_EXTRACTION_PROVIDER=mock`
  - Medical Document Extraction: `EXTRACTION_PROVIDER=mock`
  - Clinical Case Summary: `SUMMARY_PROVIDER=mock`
  - Bilingual Clinical Summary Translation: `TRANSLATION_PROVIDER=mock`
- **Real providers require explicit environment configuration** in `backend/.env`.
- **Strict Provider Selection:** If a real provider mode is specified (`gemini` or `sarvam`) without credentials, the system raises a strict `ProviderConfigError`. It **never silently falls back to mock mode**.

### 2. Service-to-Provider Mapping
- **Sarvam AI (`SARVAM_API_KEY`):**
  - **Speech-to-Text (ASR):** Powered by Sarvam `saaras:v3` REST endpoint (`https://api.sarvam.ai/speech-to-text`). Supports Indian regional languages (Hindi, Marathi, Telugu, Tamil, etc.). Preserves provider-reported confidence score or flags `UNKNOWN`.
  - **Document OCR:** Powered by Sarvam Document OCR REST endpoint (`https://api.sarvam.ai/document-ocr`). Enforces supported MIME types (`application/pdf`, `image/jpeg`, `image/png`, `image/webp`) before network calls.
- **Google Gemini (`GEMINI_API_KEY`):**
  - **Conversational Clinical Fact Extraction:** Model `gemini-2.5-flash` with structured JSON output enforcement (`temperature=0.0`).
  - **Medical Document Extraction:** Model `gemini-2.5-flash` extracting structured entities from OCR text with Pydantic validation against `StructuredMedicalData`.
  - **Clinical Case Summary:** Model `gemini-2.5-flash` generating structured 8-section clinical case summaries with strict source grounding.
  - **Bilingual Summary Translation:** Model `gemini-2.5-flash` translating clinical summaries to regional languages (Hindi, Marathi) preserving medical tokens and IDs.

### 3. Safety, Retry Policy & Credentials Isolation
- **Zero External Network Calls in Normal Test Suites:** All automated unit and integration tests strictly use deterministic mocks and mocked HTTP sessions. No external API credits or credentials are required to run the automated regression suite.
- **Selective Transient Retries:** Bounded retries (max 2 retries) are strictly applied only to transient network errors (socket timeouts, connection resets, HTTP 502/503/504/429). Client errors (400, 401, 403, 422) and schema validation errors fail immediately without retry.
- **Credential & Payload Sanitization:** API keys and sensitive tokens are automatically redacted (`[REDACTED]`) from all exception messages, logs, and tracebacks.
- **Live Verification Notice:** Live third-party provider execution has **not** been verified unless valid, funded production credentials (`GEMINI_API_KEY`, `SARVAM_API_KEY`) are actively supplied in the local environment.

### 4. Running Provider Smoke Tests
To run isolated live provider smoke verification (manual script, zero database mutations, purely synthetic test payloads):
```bash
# Dry run or live smoke run (with credentials configured in environment)
PYTHONPATH=backend python3 backend/scripts/smoke_test_real_providers.py
```

---

## REAL GEMINI INTEGRATION

### 1. Overview
The MediKiosk backend supports live integration with Google Gemini via its official REST API (`https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`).
All real Gemini provider interactions remain strictly behind the existing provider abstractions:
- **Clinical Fact Extraction**: `GeminiClinicalFactExtractionProvider` (`NLP_EXTRACTION_PROVIDER=gemini`)
- **Medical Document Extraction**: `GeminiMedicalDocumentExtractionProvider` (`EXTRACTION_PROVIDER=gemini`)
- **Clinical Case Summary**: `GeminiCaseSummaryProvider` (`SUMMARY_PROVIDER=gemini`)
- **Bilingual Translation**: `GeminiTranslationProvider` (`TRANSLATION_PROVIDER=gemini`)

All real calls pass through deterministic structured JSON generation (`responseMimeType: "application/json"`, `temperature: 0.0`), strict Pydantic validation, and clinical safety gates. Real mode does NOT bypass clinical consent, RBAC, doctor verification, or source grounding.

### 2. Environment Variables

| Variable | Description | Required in Real Mode | Default |
|---|---|---|---|
| `GEMINI_API_KEY` | Google Gemini API key (read from environment only) | **Yes** | `None` |
| `GEMINI_MODEL` | Gemini model name (supports `gemini-2.5-flash`, `gemini-1.5-flash`, `gemini-1.5-pro`) | Optional | `gemini-2.5-flash` |
| `GEMINI_MODEL_NAME` | Backward-compatibility alias for `GEMINI_MODEL` | Optional | `gemini-2.5-flash` |
| `GEMINI_TIMEOUT_SECONDS` | Network timeout for Gemini REST calls in seconds | Optional | `15` |
| `NLP_EXTRACTION_PROVIDER` | Fact extraction provider (`mock` or `gemini`) | No | `mock` |
| `EXTRACTION_PROVIDER` | Document extraction provider (`mock` or `gemini`) | No | `mock` |
| `SUMMARY_PROVIDER` | Summary generation provider (`mock` or `gemini`) | No | `mock` |
| `TRANSLATION_PROVIDER` | Summary translation provider (`mock` or `gemini`) | No | `mock` |

### 3. Mock Mode vs. Real Mode
- **Mock Mode (Default):**
  When `GEMINI_API_KEY` is not provided or provider flags are set to `mock`, all services utilize deterministic, locally executed mock implementations. Zero external network calls are made and no API credentials are required.
- **Real Mode:**
  Activated by setting one or more provider variables (`NLP_EXTRACTION_PROVIDER=gemini`, `EXTRACTION_PROVIDER=gemini`, `SUMMARY_PROVIDER=gemini`, `TRANSLATION_PROVIDER=gemini`) and providing `GEMINI_API_KEY`.
- **Fail-Closed Configuration:**
  If a provider is set to `gemini` but `GEMINI_API_KEY` is missing or empty, the provider factory immediately raises `ProviderConfigError`. The system **never silently falls back** to mock data when real mode is configured.

### 4. Local Configuration
To configure Gemini locally, set the environment variables in your environment or add them to your untracked `backend/.env` file:
```bash
# In backend/.env:
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
GEMINI_TIMEOUT_SECONDS=15

# Enable real Gemini for desired services:
NLP_EXTRACTION_PROVIDER=gemini
EXTRACTION_PROVIDER=gemini
SUMMARY_PROVIDER=gemini
TRANSLATION_PROVIDER=gemini
```

> [!CAUTION]
> **Secret Protection Warning:**
> NEVER commit real API keys, credentials, or secrets to version control. Keep `.env` listed in `.gitignore`. All error handlers and loggers automatically redact API keys as `[REDACTED]`.

> [!WARNING]
> **Usage & Cost Notice:**
> Real Gemini API calls dispatch live HTTPS requests to Google Generative Language endpoints. Real API calls consume provider quota and may incur usage costs depending on your Google Cloud billing setup.

### 5. Running the Dedicated Live Smoke Test
A dedicated integration test suite tests live Gemini endpoints with minimal payloads without mutating any database records:
```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend/app/services/test_gemini_live_smoke.py
```
- **If `GEMINI_API_KEY` is absent:** The test cleanly skips without failing the test suite.
- **If `GEMINI_API_KEY` is present:** The test executes minimal live calls across clinical extraction, document extraction, summary generation, and translation, verifying Pydantic schema validation while strictly suppressing credentials and PHI from logs and stdout.

---

## REAL SARVAM INTEGRATION

### 1. Overview
The MediKiosk backend supports live integration with Sarvam AI via its official REST endpoints:
- **Speech-to-Text (ASR)**: `SarvamASRProvider` (`ASR_PROVIDER=sarvam`) communicating via multipart/form-data to `https://api.sarvam.ai/speech-to-text`.
- **Document OCR**: `SarvamOCRProvider` (`OCR_PROVIDER=sarvam`) communicating via multipart/form-data to `https://api.sarvam.ai/document-ocr`.

Both providers preserve all existing clinical safety boundaries, consent verification (`CLINICAL_HISTORY` for ASR, `DOCUMENT_PROCESSING` for OCR), RBAC access controls, MIME validation, source grounding, and doctor verification gates.

### 2. Environment Variables

| Variable | Description | Required in Real Mode | Default |
|---|---|---|---|
| `SARVAM_API_KEY` | Sarvam AI API subscription key (read from environment only) | **Yes** | `None` |
| `SARVAM_MODEL` | ASR model name (e.g., `saaras:v3`) | Optional | `saaras:v3` |
| `SARVAM_MODEL_NAME` | Backward-compatibility alias for `SARVAM_MODEL` | Optional | `saaras:v3` |
| `SARVAM_TIMEOUT_SECONDS` | Network timeout for Sarvam REST requests in seconds | Optional | `15` |
| `ASR_PROVIDER` | Speech-to-Text provider (`mock` or `sarvam`) | No | `mock` |
| `OCR_PROVIDER` | Document OCR provider (`mock` or `sarvam`) | No | `mock` |

### 3. Mock Mode vs. Real Mode
- **Mock Mode (Default):**
  When `SARVAM_API_KEY` is not provided or provider flags are set to `mock`, the system uses local deterministic mocks (`MockASRProvider`, `MockOCRProvider`). No external network requests are dispatched and no API credits are used.
- **Real Mode:**
  Activated by setting `ASR_PROVIDER=sarvam` or `OCR_PROVIDER=sarvam` along with a valid `SARVAM_API_KEY`.
- **Fail-Closed Configuration:**
  If a provider is set to `sarvam` but `SARVAM_API_KEY` is missing or empty, provider factories immediately raise `ProviderConfigError` / `ASRConfigError`. The system **never silently falls back** to mock data.

### 4. Language Support & Confidence Handling
- **Language Support:**
  Supports Indian regional languages including English (`en` / `en-IN`), Hindi (`hi` / `hi-IN`), Marathi (`mr` / `mr-IN`), Telugu (`te` / `te-IN`), Tamil (`ta` / `ta-IN`), Kannada (`kn` / `kn-IN`), Bengali (`bn` / `bn-IN`), Gujarati (`gu` / `gu-IN`), Punjabi (`pa` / `pa-IN`), Odia (`od` / `od-IN`), and Malayalam (`ml` / `ml-IN`).
  If an unsupported language is requested, the provider raises `ASRResponseError` / `ProviderResponseError` rather than silently switching.
- **Confidence Handling:**
  Transparently passes provider-supplied confidence scores in `[0.0, 1.0]` into `ASRResult` / `OCRResult`. When confidence is unsupplied, it preserves `None` (`UNKNOWN`). The system never fabricates artificial confidence scores.

### 5. Local Configuration
To configure Sarvam AI locally, set the environment variables in your environment or add them to your untracked `backend/.env` file:
```bash
# In backend/.env:
SARVAM_API_KEY=your_sarvam_api_key_here
SARVAM_MODEL=saaras:v3
SARVAM_TIMEOUT_SECONDS=15

# Enable real Sarvam for desired services:
ASR_PROVIDER=sarvam
OCR_PROVIDER=sarvam
```

> [!CAUTION]
> **Secret Protection Warning:**
> NEVER commit real API keys, credentials, or subscription keys to version control. All exception messages and logs automatically redact Sarvam keys as `[REDACTED]`.

> [!WARNING]
> **Usage & Cost Notice:**
> Real Sarvam API calls dispatch live HTTPS requests to Sarvam AI production endpoints. Outbound requests consume provider API quota and may incur usage costs according to your Sarvam AI plan.

### 6. Running the Dedicated Live Smoke Test
A dedicated integration test suite tests live Sarvam ASR and OCR endpoints using minimal synthetic fixtures (1-second synthetic WAV audio, 1x1 synthetic PNG image) without mutating database records:
```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend/app/services/test_sarvam_live_smoke.py
```
- **If `SARVAM_API_KEY` is absent:** The test cleanly skips without failing the test suite.
- **If `SARVAM_API_KEY` is present:** The test executes minimal live calls verifying `ASRResult`, `OCRResult`, language handling, confidence preservation, and end-to-end provider chains (ASR → NLP fact extraction; OCR → Document extraction).

---

## PRIVACY / CONSENT SECURITY MODEL

### 1. Purpose-Specific Consent Architecture
Under the MediKiosk security and clinical governance model, patient consent is strictly granular, purpose-bound, and managed at the database boundary:

- **`CLINICAL_HISTORY`**:
  Required to initiate clinical interview sessions, ingest patient text messages, stream spoken voice utterances, execute the NLP extraction pipeline, and read or mutate structured clinical data.
- **`DOCUMENT_PROCESSING`**:
  Required to upload medical records, trigger OCR text recognition, execute clinical document entity extraction, and query document processing status.
- **`AI_SUMMARIZATION`**:
  Required to invoke LLM-based clinical case summarization, read generated case summaries, submit patient layperson confirmations, and record doctor clinical reviews.
- **`BILINGUAL_OUTPUT`**:
  Required to translate medical case summaries into regional languages (e.g., Hindi, Marathi) for patient comprehension.
- **`DATA_SHARING`**:
  Required to transmit clinical summaries or FHIR bundles to external Hospital Information Systems (HIS). Evaluated as Gate 1 prior to clinician verification checks.
- **`ABHA_LINKAGE`**:
  Required to search, verify, initiate OTPs, and link Ayushman Bharat Health Accounts (ABHA).

No consent purpose can cross-authorize another purpose. For example, `CLINICAL_HISTORY` consent cannot authorize document processing, and `AI_SUMMARIZATION` consent cannot authorize external data transmission.

### 2. Fail-Closed Enforcement Semantics
All protected clinical operations enforce fail-closed security semantics:
- **Zero-Bypass Policy**: Bypasses (such as conditional checks when no consents exist) are strictly forbidden. If active, valid, purpose-matching consent is not present, the operation immediately halts and raises `ConsentRequiredException` (HTTP 403 Forbidden).
- **Transactional Atomicity**: Consent checks execute at the entry boundary before any downstream AI/NLP providers, database mutations, or storage writes take place. If consent is absent or invalid, zero artifacts are persisted and zero third-party network calls are dispatched.
- **Temporal Validity**: Expired consents (`expires_at < now()`) and revoked consents are automatically treated as invalid.

### 3. Revocability, Versioning & Historical Immutability
- **Immediate Effect**: Consent revocation takes effect immediately, blocking all subsequent protected operations.
- **Version Superseding**: When a patient grants a newer version of consent for an existing purpose, the prior active consent is marked `SUPERSEDED` rather than modified in place.
- **Preservation of Clinical Encounters**: In compliance with clinical medico-legal standards, revoking consent prevents future data processing but does not delete or alter historical clinical records or prior audit trail entries.

### 4. Server-Side Multi-Tenant & Cross-Patient Isolation
All endpoints enforce multi-tenant patient boundary isolation server-side:
- Access to interviews, case summaries, clinical documents, medication histories, and timeline events is filtered strictly by authenticated patient identity.
- Any attempt to access or modify resources belonging to another patient (e.g., Patient A accessing Patient B's interview or summary) is rejected with HTTP 404 (Not Found) or HTTP 400 (Bad Request), preventing cross-patient data leakage.

### 5. Append-Only Privacy Audit Trail & Sensitive Data Sanitization
- Every consent lifecycle transition (`CONSENT_GRANTED`, `CONSENT_REVOKED`, `CONSENT_SUPERSEDED`), data access (`CLINICAL_DATA_READ`, `SUMMARY_READ`), and authorization failure (`CONSENT_VERIFICATION_FAILED`) is logged to the `privacy_audit_logs` table.
- **Data Minimization**: Audit logs store only non-sensitive operational metadata (e.g., purpose, action, timestamp, client IP).
- **Sensitive Data Exclusion**: Audit logs NEVER record raw speech/audio bytes, raw OCR text, document contents, clinical summary bodies, patient passwords, API credentials, or ABHA OTP tokens.

### 6. Regulatory Alignment (DPDP Act 2023 & ABDM)
- **Digital Personal Data Protection (DPDP) Act 2023**: Implements explicit purpose specification, verifiable consent notices, clear withdrawal mechanisms, and strict data minimization.
- **Ayushman Bharat Digital Mission (ABDM)**: Conforms to ABDM Electronic Consent Management guidelines, guaranteeing patient autonomy over health record digitization, linkage, and interoperability.

---

## AUTHENTICATION & ROLE-BASED ACCESS CONTROL (RBAC)

### 1. Architectural Model & Security Chain
The MediKiosk backend enforces an additive, defense-in-depth security chain for all protected operations:

```
Request → Authentication (JWT) → Authenticated User → Role Verification → Resource Ownership (IDOR Prevention) → Clinical Consent Verification → Business Logic
```

Authentication and role enforcement act as the outer perimeter gate, while clinical consent gates (`PrivacyConsentService`) and multi-tenant patient ownership continue to operate as inner domain gates. Authenticating or holding an administrative role does **not** bypass consent requirements or patient isolation boundaries.

### 2. Supported Roles
The system defines four mutually exclusive system roles (`UserRole`):

| Role | Target Persona | Permissions & Scope |
|---|---|---|
| `PATIENT` | Self-service kiosk / mobile user | Restricted strictly to resources matching their linked `patient_id`. Cannot access clinical verification or administrative endpoints. |
| `DOCTOR` | Attending / Reviewing Clinician | Authorized to perform clinical review, verify structured clinical facts, sign off on case summaries, trigger HIS/FHIR exports, and manage emergency incidents. |
| `STAFF` | Nursing & Kiosk Attendant Staff | Authorized to triage/acknowledge emergency events, monitor kiosk activity, and trigger HIS/FHIR synchronization. |
| `ADMIN` | System Administrator | Authorized to provision and manage user accounts (`POST /api/auth/register`). Subject to standard consent and ownership rules for clinical data. |

### 3. Key Invariants & Security Protections
- **Password Security**: Passwords are encrypted using salted `bcrypt` hashes. Passwords exceeding 72 bytes are rejected prior to hashing to prevent truncation vulnerabilities.
- **Credential & Secret Protection**:
  - `password_hash` is never exposed in response schemas, logs, or serialization models.
  - JWT tokens are signed using `HS256` with a secret loaded exclusively from the environment (`JWT_SECRET`). Hardcoded fallback secrets are forbidden.
  - JWT claims contain zero Protected Health Information (PHI): only standard claims (`sub`, `role`, `exp`, `iat`) are encoded.
- **Timing & Oracle Attack Resistance**: Authentication failure responses (invalid password vs. non-existent user) return uniform 401 Unauthorized responses with identical error messages to prevent account enumeration.
- **Direct Object Reference (IDOR) Protection**: When a `PATIENT` user attempts to access or query resources associated with a different patient, the API responds with HTTP 404 (Not Found) rather than 403 (Forbidden) to prevent resource existence enumeration.
- **Administrative Account Creation**: Public self-registration for privileged roles (`DOCTOR`, `STAFF`, `ADMIN`) is disabled. The user registration endpoint (`POST /api/auth/register`) strictly requires an authenticated `ADMIN` identity.

### 4. API Endpoint Authorization Matrix

| Endpoint / Workflow | Method & Path | Authorization Requirement |
|---|---|---|
| **User Login** | `POST /api/auth/login` | Public (Anonymous) |
| **Current User Info** | `GET /api/auth/me` | Authenticated (`PATIENT`, `DOCTOR`, `STAFF`, `ADMIN`) |
| **User Provisioning** | `POST /api/auth/register` | `ADMIN` Role Required |
| **Doctor Review Lifecycle** | `POST/PUT /api/interviews/{id}/review/*` | `DOCTOR` Role Required |
| **FHIR / HIS Data Export** | `POST /api/fhir/*` | `DOCTOR` or `STAFF` Role + `DATA_SHARING` Consent |
| **Emergency Lifecycle** | `POST /api/emergency/{id}/*` | `DOCTOR` or `STAFF` Role Required |
| **Emergency Consultation Read** | `GET /api/interviews/{id}/emergency` | Authenticated User |
| **Patient Emergency Status** | `GET /api/patients/{id}/emergency/status` | Authenticated User + Resource Ownership Check |

---

## API SECURITY & REQUEST VALIDATION

### 1. Architectural Model & Defense-in-Depth Layering
MediKiosk implements a strict 5-tier defense-in-depth security chain for all incoming requests:

```
1. Network & Transport Perimeter
   (Security Headers Middleware, Restricted CORS, In-Memory Rate Limiting)
                 ↓
2. Request Validation & Boundary Constraints
   (Pydantic v2 strict schemas with extra="forbid", bounded strings, path gt=0, pagination limits)
                 ↓
3. Authentication & RBAC Perimeter
   (JWT decode via HS256, timing-safe credential verification, role-based endpoint guards)
                 ↓
4. Patient Tenant & Resource Ownership Isolation
   (IDOR prevention: cross-patient queries by PATIENT role return HTTP 404 Not Found)
                 ↓
5. Purpose-Specific Clinical Consent
   (Fail-closed ConsentService verifying active, unexpired, non-revoked purpose consent)
                 ↓
6. Clinical Operation & Audit Logging
   (Append-only immutable privacy audit trail with sensitive credential/token exclusion)
```

No outer layer may replace, weaken, or bypass any inner layer. An administrator or doctor cannot bypass patient consent, and authentication does not grant cross-tenant access.

### 2. Rate Limiting Architecture & In-Memory State Guarantees
- **Sliding-Window Rate Limiter:** Protects authentication endpoints (`POST /api/auth/login`) against brute-force credential stuffing and password-guessing attacks.
- **Configurable Thresholds:** Configured via `RATE_LIMIT_LOGIN_MAX_ATTEMPTS` (default: 5) and `RATE_LIMIT_LOGIN_WINDOW_SECONDS` (default: 60s).
- **Client Identification:** Evaluates client IP using `X-Forwarded-For` when available behind reverse proxies, falling back to direct connection IP.
- **HTTP 429 & Retry-After:** Once the threshold is exceeded, the endpoint immediately halts with `HTTP 429 Too Many Requests` and supplies a compliant `Retry-After: <seconds>` HTTP response header indicating wait time until window expiry.
- **Memory Boundedness:** The in-memory limiter tracks sliding windows with a hard capacity ceiling (10,000 active keys). When capacity is approached, an automated TTL sweep purges expired keys to prevent unbounded memory growth and heap starvation.
- **Test Isolation:** Exposes an atomic `.reset()` method allowing test suites to clear rate-limiting state deterministically without side effects.

### 3. Schema Hardening & Mass-Assignment Prevention
- **Strict Extra Attributes Rejection (`extra="forbid"`):** All Pydantic request models across the API enforce `model_config = ConfigDict(extra="forbid")`. Any request containing unmodeled, extraneous, or forged attributes (e.g., `role`, `is_active`, `is_admin`, `patient_id`, `verified`) is immediately rejected with `HTTP 422 Unprocessable Content`.
- **Privilege Escalation Barriers:**
  - Self-registration cannot inject administrative roles (`POST /api/auth/register` requires `ADMIN` role).
  - Clinical data mutation (`PUT /api/interviews/{id}/clinical-data/{field_key}`) forbids `PATIENT` role from setting `verification_status="VERIFIED"` or setting `source="DOCTOR"`.
  - Doctor reviews and medication verifications strictly require `DOCTOR` role via `require_roles(UserRole.DOCTOR)`.

### 4. Parameter Validation & Bounded Limits
- **Path Parameter Range Validation:** All integer entity identifiers (`patient_id`, `interview_id`, `document_id`, `medication_id`, etc.) enforce `Path(..., gt=0)`. Negative or zero IDs are rejected by FastAPI at the routing perimeter with HTTP 422.
- **Strict Pagination Bounds:** List and query endpoints enforce strict pagination limits:
  - `limit`: `Query(50, ge=1, le=100)` — clients cannot request unbounded or negative page sizes.
  - `offset`: `Query(0, ge=0)` — negative page offsets are strictly rejected.
- **Temporal & Semantic Date Validations:**
  - Patient `date_of_birth`: Pydantic field validators reject dates in the future and dates earlier than `1900-01-01`.
  - Analytics date ranges: Query endpoints validate that `start_date <= end_date` and max range <= 366 days, rejecting inverted dates with HTTP 422.
- **String Length Enforcements:** All text inputs across interview messages (max 10,000 chars), clinical data values (max 5,000 chars), patient names (max 255 chars), notes (max 1,000 chars), and phone numbers (8–20 chars regex) enforce rigorous minimum and maximum string bounds to prevent memory pressure.

### 5. Secure File Upload Handling
- **Multi-Stage MIME & Content Validation:** Document upload (`POST /api/interviews/{id}/documents`) enforces safe upload mechanics:
  - Supported MIME types strictly restricted to `application/pdf`, `image/jpeg`, `image/png`, and `image/webp`. Unsupported types return `HTTP 415 Unsupported Media Type`.
  - Zero-byte / empty files return `HTTP 400 Bad Request`.
- **File Size Upper Bound & Memory DOS Protection:** Upload streaming uses a bounded buffer (`read(max_bytes + 1)`) capping payloads at 10 MB (`MAX_FILE_SIZE_BYTES`). OOM denial-of-service is prevented without loading unbounded files into memory.
- **Path Traversal & Filename Sanitization:** Raw client filenames are sanitized using regex extraction of alphanumeric and safe extension characters, stripping path separators (`/`, `\`, `..`). Files are stored on disk using non-enumerable UUIDv4 filenames (`<uuid>.<ext>`), preventing directory traversal and local file inclusion.

### 6. Error Sanitization & Information Leakage Prevention
- **Pydantic Validation Error Redaction:** The custom `RequestValidationError` handler inspects validation errors and automatically redacts input values for sensitive fields (`password`, `secret`, `token`, `key`, `credentials`) to `"[REDACTED]"`. Plaintext credentials never appear in error payloads.
- **Reflected Payload Truncation:** Large string inputs causing validation failures are automatically truncated to 100 characters with `... [TRUNCATED]`, preventing reflected payload memory consumption and logging abuse.
- **Production Exception Sanitization:** A catch-all unhandled `Exception` handler intercepts non-HTTP exceptions, logs full stack traces server-side to internal diagnostics, and returns a generic JSON response (`{"error": "INTERNAL_SERVER_ERROR", "message": "An unexpected internal server error occurred."}`) with HTTP 500. Internal database queries, table names, file system paths, and third-party stack traces are never exposed to clients.

### 7. Security Headers & CORS Policy
- **Defensive HTTP Security Headers:** The `SecurityHeadersMiddleware` automatically injects defensive headers into every HTTP response:
  - `X-Content-Type-Options: nosniff` — prevents MIME type sniffing.
  - `X-Frame-Options: DENY` — prevents clickjacking by forbidding embedding in iframes.
  - `Referrer-Policy: strict-origin-when-cross-origin` — protects URL referrers on cross-origin requests.
  - `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'` — restricts kiosk framing and resource loading.
  - `X-XSS-Protection: 0` — disables legacy browser XSS filters that introduce security holes.
- **Defensive CORS Policy:** Built on `CORSMiddleware` with explicit origin whitelist (`CORS_ORIGINS`). If credentials are enabled (`CORS_ALLOW_CREDENTIALS=true`), wildcard origins (`*`) are disallowed and replaced with explicit origins to prevent credential leakage.

### 8. Operational Considerations in Multi-Process/Clustered Deployments
- **Process-Local State Notice:** The default `InMemoryRateLimiter` is process-local. When deploying across multiple ASGI worker processes (e.g. Uvicorn with multiple workers) or horizontally autoscaled containers behind an external load balancer, rate-limiting counters are tracked per worker instance.
- **Production Redis/Memcached Upgrade Path:** For clustered or distributed deployments requiring globally shared rate-limiting state, the `InMemoryRateLimiter` interface can be swapped for a distributed Redis-backed sliding window or token bucket implementation using the identical dependency interface (`rate_limit_login`).

---

## OBSERVABILITY & OPERATIONAL MONITORING

### 1. Standardized Correlation IDs (`X-Request-ID`)
The MediKiosk backend enforces end-to-end request correlation across all incoming and outgoing HTTP interactions:
- **Generation:** If an incoming request does not supply an `X-Request-ID` header, the `RequestObservabilityMiddleware` automatically generates a cryptographically secure UUIDv4 identifier.
- **Validation & Sanitization:** If an `X-Request-ID` is provided by the client, it is validated against strict criteria:
  - Maximum length: 64 characters.
  - Safe character set: `^[a-zA-Z0-9_\-]+$`.
  - Any oversized ID or ID containing forbidden characters (whitespace, semicolons, path separators, SQL injection tokens, or script tags) is sanitized and replaced with a fresh UUIDv4.
- **Propagation & Downstream Context:**
  - The sanitized correlation ID is bound to Python's `contextvars.ContextVar` (`request_id_ctx_var`) and `request.state.request_id`, making it accessible across synchronous and asynchronous operations without passing `request` objects into core domain services.
  - The `X-Request-ID` header is attached to **all** outgoing HTTP responses across every status code (200 OK, 400 Bad Request, 403 Forbidden, 404 Not Found, 422 Unprocessable Entity, 500 Internal Server Error).
  - Exception responses (422 validation errors, 500 internal errors, 403 consent errors) include `request_id` directly in their JSON response bodies for immediate frontend and client diagnostics.

### 2. Privacy-Safe Request Logging Middleware
The ASGI `RequestObservabilityMiddleware` records request execution details with strict data minimization:
- **Logged Information:** HTTP method, normalized URL path (excluding query parameters), HTTP status code, precise duration in milliseconds (`time.perf_counter()`), and authenticated user ID and role when present on request state.
- **Strict Exclusions:**
  - `Authorization` headers, Bearer tokens, and JWT strings are NEVER logged.
  - Request and response JSON/form bodies are NEVER captured in request logs.
  - Query parameters (which might inadvertently contain tokens or patient search terms) are excluded from the path.
  - Session cookies, credentials, and API keys are completely omitted.
  - Clinical narratives, patient names, phone numbers, and Protected Health Information (PHI) are strictly excluded.

### 3. Structured Operational Event Logging
Operational events are emitted through a centralized structured logger (`medikiosk.observability`) using standardized JSON format:
```json
{
  "timestamp": "2026-09-14T10:30:00.123456+00:00",
  "event": "pipeline_stage_completed",
  "request_id": "c6a2b8e4-18f2-4e67-91a1-9a7b71321045",
  "stage": "case_summary",
  "status": "success",
  "duration_ms": 312.45,
  "interview_id": 42
}
```
- **Standardized Core Fields:**
  - `timestamp`: ISO-8601 UTC timestamp.
  - `event`: Event identifier (e.g., `request_completed`, `pipeline_stage_completed`, `pipeline_stage_failed`, `his_export_success`).
  - `request_id`: Active correlation ID linked to the initiating HTTP request.
  - `stage`: Name of the pipeline stage if applicable (`voice_asr`, `interview_nlp`, `document_ocr`, `medical_extraction`, `case_summary`, `translation`, `his_export`).
  - `status`: Outcome indicator (`success` or `failure`).
  - `duration_ms`: Execution time in milliseconds rounded to 2 decimal places.
  - `error_category`: Categorized operational failure classification when an error occurs.
- **Allowed Operational Metadata:** Only non-sensitive technical identifiers are permitted (e.g., `interview_id`, `document_id`, `export_id`, `adapter`).

### 4. Operational Error Categorization
To enable immediate diagnostic filtering without exposing underlying stack traces or clinical content, exceptions are automatically categorized:
- **`validation_failure`**: Request body or query parameters violate schema constraints (e.g., Pydantic `ValidationError`, `ValueError`, HTTP 400/422).
- **`authentication_failure`**: Invalid credentials, expired JWT, or missing authorization tokens (HTTP 401).
- **`authorization_failure`**: Role permissions denied or access to unauthorized patient resources (HTTP 403, `PermissionError`).
- **`consent_failure`**: Missing, revoked, or expired purpose-specific clinical consent (`ConsentRequiredException`).
- **`provider_config_failure`**: Missing configuration, unsupported AI mode, or invalid settings (`ProviderConfigError`).
- **`provider_auth_failure`**: Third-party AI provider rejected API credentials (`ProviderAuthError`).
- **`provider_network_failure`**: Third-party connection reset, socket timeout, or DNS failure (`ProviderNetworkError`).
- **`provider_response_failure`**: Third-party provider returned 5xx, malformed JSON, or unparseable response (`ProviderResponseError`, `ProviderProcessingError`).
- **`database_failure`**: Database query, connection pool, or relational constraint error.
- **`unexpected_internal_failure`**: Unhandled runtime exceptions.

### 5. Health & Diagnostic Endpoints
The backend provides dedicated endpoints for container orchestration, load balancers, and monitoring systems:
- **`GET /health` (Liveness Probe):**
  - Lightweight endpoint verifying ASGI application responsiveness.
  - Returns `{"status": "healthy", "service": "MediKiosk Backend"}` with HTTP 200.
- **`GET /health/db` (Readiness Probe):**
  - Executes a lightweight database query (`SELECT 1`).
  - Returns sanitized status (`{"connected": true, "detail": "Database connection successful"}`).
  - **Leak Prevention:** Suppresses all connection strings, hostnames, ports, and database credentials on failure, returning generic failure detail (`"Database connection failed"`).
- **`GET /health/status` (Operational Configuration Summary):**
  - Reports service status and active provider configuration modes (`"mock"` vs `"configured"`) across all 8 external integrations (`asr`, `ocr`, `nlp`, `extraction`, `summary`, `translation`, `abdm`, `his`).
  - **Zero Network Calls & Zero Secrets:** Reads only in-memory settings. Makes NO external HTTP or API calls and strictly never exposes API keys or credential values.
- **`GET /health/metrics` (Operational Performance Snapshot):**
  - Returns an in-process snapshot of request throughput, status code distributions, provider call counts, and pipeline stage timings.

### 6. Pipeline Latency & Failure Point Monitoring
Each stage in the clinical ingestion and processing pipeline is individually instrumented with duration timing, success/failure counting, and operational event logging:
- **Instrumented Stages:**
  - `voice_asr`: Speech-to-text utterance transcription.
  - `interview_nlp`: Conversational clinical fact extraction.
  - `document_ocr`: Document optical character recognition.
  - `medical_extraction`: Structured medical entity extraction from document text.
  - `document_orchestration`: End-to-end document processing lifecycle.
  - `case_summary`: LLM-generated clinical case summary synthesis.
  - `translation`: Regional language clinical summary translation.
  - `his_export`: External Hospital Information System / FHIR transmission.
- When any pipeline stage fails, the exact failure point is recorded in `pipeline_stages` metrics along with the categorized reason (e.g. `provider_network_failure`), allowing operations teams to pinpoint pipeline degradation instantly.

### 7. In-Process Thread-Safe Performance Metrics
- **Thread Safety:** Implemented via `OperationalMetrics` using `threading.Lock` to guarantee atomic counter and duration increments under multi-threaded concurrency.
- **Strict Bounded Cardinality:**
  - HTTP requests are grouped strictly by `(method, status_class)` (e.g. `POST_2xx`, `GET_4xx`, `POST_5xx`), yielding a bounded set of under 30 possible keys.
  - Provider calls are grouped by fixed provider name and operation (e.g. `gemini_summary`, `sarvam_asr`).
  - Pipeline stages are tracked by a fixed enum of known stage names.
  - **Zero Cardinality Explosion:** No dynamic URLs, query parameters, patient IDs, timestamps, or client IPs are ever used as metric keys.
- **Snapshot Schema:**
  - `http_requests`: `total`, `success`, `failed`, `avg_duration_ms`, and `by_method_and_status`.
  - `providers`: `calls` and `failures`.
  - `pipeline_stages`: per-stage `count`, `success`, `failure`, `avg_duration_ms`, and `failures_by_category`.

### 8. Zero-PHI Privacy Guarantees for Monitoring
- **Automated Metadata Key Filtering:** The `log_operational_event` helper enforces an immutable blacklist of forbidden keys (`FORBIDDEN_METADATA_KEYS`):
  - Passwords, hashes, secrets, JWTs, API keys, credentials.
  - Audio files, raw speech utterances, binary buffers.
  - Raw OCR text, clinical notes, document content.
  - Conversational transcripts and NLP extraction entities.
  - Case summaries, diagnoses, prescriptions, medications.
  - Patient names, dates of birth, phone numbers, email addresses, ABHA IDs, OTPs.
- **Architectural Separation:**
  - **Clinical & Consent Audit Logs:** Managed exclusively by `PrivacyAuditLog` in the relational database to record patient consent lifecycle and medico-legal audit trails under DPDP Act / ABDM requirements.
  - **Operational Observability:** Managed by `medikiosk.observability` and `OperationalMetrics` to monitor system performance, latency, and provider reliability with zero clinical data exposure.

---

## END-TO-END BACKEND WORKFLOW

### 1. Primary Patient Journey & Stage Transitions
The MediKiosk backend delivers a fully integrated, deterministic patient flow from kiosk onboarding through external hospital transmission:

1. **Patient Registration & Onboarding:**
   - Registration creates a `Patient` record with demographic identifiers.
   - Credentials establish an authenticated `AppUser` account (`UserRole.PATIENT`).
2. **Consent Acquisition (Gate 1):**
   - The patient explicitly grants purpose-specific consent (`CLINICAL_HISTORY`).
   - A `PatientSession` is instantiated in `REGISTRATION` state.
3. **Adaptive Clinical Interview:**
   - Interview begins (`InterviewStatus.IN_PROGRESS`), attaching to the active session (`SessionStatus.INTERVIEW`).
   - Patient conversational inputs (text or speech utterances) pass through the Stage 5/6 NLP pipeline (`interview_nlp_flow_service`), extracting clinical entities into the structured clinical ontology (`InterviewClinicalData`).
   - Adaptive questioning dynamically presents the next high-priority clinical question until history collection is complete.
4. **Medical Document Ingestion & Multimodal Extraction:**
   - Patient grants `DOCUMENT_PROCESSING` consent.
   - Medical documents (prescriptions, lab panels, discharge summaries) are securely uploaded via `StorageService`.
   - The end-to-end document processing pipeline (`document_processing_service`) coordinates OCR, clinical entity extraction (`MedicalDocumentExtraction`), timeline synchronization (`MedicalTimelineEvent`), abnormal lab evaluation, and medication history synchronization (`MedicationHistory`).
   - The multi-source contradiction engine flags clinical discrepancies between patient statements and laboratory/prescription evidence.
   - Reprocessing is strictly idempotent—re-running document extraction refreshes downstream clinical records without duplication.
5. **Case Summary Synthesis & Versioning:**
   - Patient grants `AI_SUMMARIZATION` consent.
   - The summary synthesis pipeline (`medical_case_summary_service`) aggregates interview ontology data, document extractions, timeline events, and active contradictions into versioned summaries (`MedicalCaseSummary`, version 1, 2, ...).
   - The session advances to `SUMMARY_READY`.
6. **Patient Summary Confirmation:**
   - The patient reviews discrete clinical summary items via the confirmation workflow (`patient_summary_confirmation_service`).
   - The session enters `PATIENT_CONFIRMATION` while review is underway.
   - Patient item-by-item confirmation or correction flags transition confirmation to `CONFIRMED` or `FLAGGED`.
7. **Doctor Review & Verification (Gate 2):**
   - An authenticated doctor (`UserRole.DOCTOR`) opens the clinical dashboard and initiates verification (`doctor_verification_service`).
   - The session enters `DOCTOR_REVIEW`.
   - The doctor reviews, verifies, edits, or flags individual clinical assertions.
   - Upon completing review, the summary status advances to `VERIFIED`.
8. **FHIR R4 Bundle Generation & HIS Export (Gate 3):**
   - Pre-flight preview generates a compliant FHIR R4 Document Bundle (`his_export_service.generate_preview`).
   - Transmitting to the external Hospital Information System (`export_to_his`) enforces three strict gates:
     - **Gate 1 (Consent):** Active `DATA_SHARING` consent must be granted.
     - **Gate 2 (Doctor Verification):** Summary must be verified by an authenticated doctor.
     - **Gate 3 (Idempotency):** Previous successful transmissions return the existing record without duplicate external calls.
9. **Session Completion:**
   - The session reaches terminal `COMPLETED` state with UTC completion timestamp.
   - Terminal session protection prevents completed sessions from returning to active states or being cancelled.

### 2. Five-Layer Security & Authorization Chain
Every request traversing the MediKiosk backend is validated across five sequential, non-bypassable security barriers:
```
1. Authentication       -> Cryptographic JWT token validation & revocation check
2. Role-Based Access    -> Strict RBAC boundary (PATIENT, DOCTOR, STAFF, ADMIN)
3. Patient Ownership    -> IDOR isolation ensuring patients only access their own data
4. Purpose Consent      -> Fail-closed consent enforcement per clinical operation
5. Clinical Verification-> Doctor sign-off required prior to external transmission
```

### 3. Purpose-Specific Fail-Closed Consent Matrix
Clinical operations strictly require purpose-specific patient consent before processing:

| Consent Purpose | Operations Protected | Failure Consequence |
|---|---|---|
| `CLINICAL_HISTORY` | Interview creation, speech processing, clinical data capture | 403 Forbidden (`CONSENT_REQUIRED`) |
| `DOCUMENT_PROCESSING` | Document OCR, structured clinical extraction, downstream sync | 403 Forbidden (`CONSENT_REQUIRED`) |
| `AI_SUMMARIZATION` | LLM case summary generation, summary retrieval | 403 Forbidden (`CONSENT_REQUIRED`) |
| `BILINGUAL_OUTPUT` | Regional language summary synthesis and translation | 403 Forbidden (`CONSENT_REQUIRED`) |
| `DATA_SHARING` | FHIR R4 Bundle preview and HIS / EMR transmission | 403 Forbidden (`CONSENT_REQUIRED`) |
| `ABHA_LINKAGE` | ABDM M1/M2/M3 profile query and linkage | 403 Forbidden (`CONSENT_REQUIRED`) |

### 4. Emergency Escalation Path
- When critical clinical red flags are detected during an interview (e.g. acute chest pain, anaphylaxis, severe respiratory distress), the emergency pipeline immediately activates:
  - An `EmergencyEscalation` is created in `ACTIVE` status with `CRITICAL` severity.
  - The patient's OPD queue entry priority is automatically promoted to `EMERGENCY`.
  - The session status resolver immediately derives `SessionStatus.EMERGENCY`.
  - Emergency processing bypasses non-urgent workflows—it does not block on document processing, case summaries, or patient confirmation.
  - Authorized medical staff can triage, acknowledge, and resolve escalations through dedicated endpoints.

### 5. Multi-Tenant IDOR Protection
- Cross-patient isolation guarantees zero data leakage across tenant boundaries:
  - Patient A cannot view or mutate Patient B's interviews, documents, summaries, timeline events, or medications.
  - Unauthorized cross-patient access attempts return HTTP 404 (`Not Found`) rather than 403, preventing attackers from confirming resource existence.
  - Granting consent with another patient's interview ID is rejected with HTTP 400.
  - All timeline, medication, and clinical history queries strictly filter by authenticated patient ID.

---

## LLM PROVIDER FAILOVER

### 1. Architectural Overview
MediKiosk implements a controlled, single-hop fallback mechanism for text and structured LLM workloads:
```
Primary Provider:   Google Gemini (gemini-flash-lite-latest / gemini-2.5-flash)
                          │
         [Eligible Transient Availability Failure?]
              ├── No  ──> Raise Provider Error immediately
              └── Yes ──> Controlled Fallback to Groq (openai/gpt-oss-120b)
                               │
                [Identical Pydantic Validation & Safety Gate]
                     ├── Failed ──> Raise Validation/Provider Error
                     └── Passed ──> Output to Downstream Service
```

### 2. Supported Failover Operations
1. **Conversational Clinical Fact Extraction:** `GeminiClinicalFactExtractionProvider` → `GroqClinicalFactExtractionProvider`
2. **Medical Document Extraction:** `GeminiMedicalDocumentExtractionProvider` → `GroqMedicalDocumentExtractionProvider`
3. **Clinical Case Summary Generation:** `GeminiCaseSummaryProvider` → `GroqCaseSummaryProvider`
4. **Bilingual Summary Translation:** `GeminiTranslationProvider` → `GroqTranslationProvider`

*Note: Speech-to-Text (ASR) and Document OCR remain exclusively handled by the Sarvam AI provider suite and are not subject to LLM failover.*

### 3. Explicit Configuration & Safe Defaults
- **Disabled by Default:** Failover is strictly deactivated unless explicitly enabled via environment variable:
  ```bash
  LLM_FALLBACK_ENABLED=true
  GROQ_API_KEY=gsk_your_groq_api_key_here
  GROQ_MODEL=openai/gpt-oss-120b
  GROQ_TIMEOUT_SECONDS=15
  ```
- If `LLM_FALLBACK_ENABLED=false` or `GROQ_API_KEY` is omitted, Gemini failures remain normal provider failures with zero change in system behavior.

### 4. Failure Eligibility Policy
- **Eligible Failover Conditions (Transient Provider Availability Failures Only):**
  - Socket / HTTP network timeouts (`ProviderNetworkError`)
  - Connection dropouts and network resets (`ProviderNetworkError`)
  - HTTP 429 Rate Limiting / Quota Exhaustion (`ProviderProcessingError`)
  - HTTP 500, 502, 503, 504 Provider Outages / High Demand (`ProviderProcessingError`)
- **Strictly Ineligible Failover Conditions (Must NEVER Trigger Failover):**
  - Authentication errors / Invalid API keys (HTTP 401, 403)
  - Configuration errors (Missing credentials or unconfigured provider)
  - Malformed application requests / Client errors (HTTP 400, 422)
  - Pydantic schema validation failures
  - Clinical safety, red flag, or source-grounding rejections
  - Patient consent or role-based access control (RBAC) denials

### 5. Validation & Safety Invariants
- **Identical Authoritative Gate:** Groq output is never trusted implicitly. All responses are strictly validated through MediKiosk's authoritative Pydantic schemas (`ExtractedClinicalFacts`, `StructuredMedicalData`, `StructuredCaseSummary`, bilingual translation schema).
- **Single-Attempt Limit:** At most one failover attempt is made (`Gemini → Groq`). No cascading fallback loops.
- **Fail-Closed Behavior:** If both Gemini and Groq fail, the operation halts safely without partial state or corrupting the database.
- **Quota & Cost Notice:** Groq API calls consume Groq account quota and may incur usage charges when failover is active. Never commit API keys to version control.

---

## RENDER DEPLOYMENT READINESS

The MediKiosk FastAPI backend is engineered and hardened for deployment as a Native Web Service on Render (Python runtime, non-containerized).

### 1. Build and Startup Commands

| Lifecycle Step | Command | Context / Working Directory |
|---|---|---|
| **Build Command** | `pip install -r requirements.txt` | `backend` (or Root with `pip install -r backend/requirements.txt`) |
| **Database Migration Command** | `alembic upgrade head` | `backend` (executed in Render pre-deploy or release phase) |
| **Start Command** | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` | `backend` |

> [!NOTE]
> Render automatically assigns the `PORT` environment variable. The application binds to `0.0.0.0` and listens dynamically on `$PORT` without requiring static port mappings or containerization.

### 2. Required Production Environment Variables

In production (`ENVIRONMENT=production`), the application enforces strict fail-fast validation on startup. If any critical production variable is missing or insecure, startup halts immediately with clear operational diagnostics.

| Variable | Requirement Level | Description | Example / Recommendation |
|---|---|---|---|
| `ENVIRONMENT` | **Required** | Sets runtime mode (`production`) | `production` |
| `DATABASE_URL` | **Required** | PostgreSQL connection URL | `postgresql+psycopg://user:pass@host:5432/dbname` (Render `postgres://` URLs are automatically normalized) |
| `JWT_SECRET` | **Required** | High-entropy signing secret (>= 32 chars) | Generated via `python3 -c "import secrets; print(secrets.token_hex(64))"` |
| `CORS_ORIGINS` | **Required** | Explicit comma-delimited allowed origins | `https://medikiosk.example.com,https://dashboard.example.com` (Wildcards forbidden with credentials) |
| `CORS_ALLOW_CREDENTIALS` | Optional | Controls Access-Control-Allow-Credentials | `true` |

### 3. Production PostgreSQL & Connection Pooling

MediKiosk utilizes SQLAlchemy with the `psycopg` (v3) driver and includes built-in connection pool tuning:

| Variable | Default | Purpose |
|---|---|---|
| `DB_POOL_SIZE` | `5` | Steady-state connection pool size |
| `DB_MAX_OVERFLOW` | `10` | Maximum temporary connections above pool size |
| `DB_POOL_TIMEOUT` | `30` | Seconds to wait before timing out on pool exhaustion |
| `DB_POOL_RECYCLE` | `1800` | Seconds after which connections are re-established |
| `DB_POOL_PRE_PING` | `true` | Verifies connection liveness before checkout |

> [!IMPORTANT]
> **Render URL Compatibility:**
> Render provides PostgreSQL connection strings prefixed with `postgres://`. MediKiosk automatically detects and normalizes these to `postgresql+psycopg://`, ensuring seamless driver compatibility without manual string manipulation.

### 4. Database Migrations (Alembic)

All schema migrations are strictly version-controlled in `backend/alembic/versions` in a linear chain.
- To apply migrations in production:
  ```bash
  cd backend && alembic upgrade head
  ```
- To inspect migration SQL without execution:
  ```bash
  cd backend && alembic upgrade head --sql
  ```

### 5. Document Storage Configuration (Cloudinary)

In serverless or containerized cloud deployments like Render, the local filesystem is ephemeral. MediKiosk supports Cloudinary for persistent, encrypted document storage:
- To enable Cloudinary in production:
  ```bash
  DOCUMENT_STORAGE_PROVIDER=cloudinary
  CLOUDINARY_CLOUD_NAME=your_cloud_name
  CLOUDINARY_API_KEY=your_api_key
  CLOUDINARY_API_SECRET=your_api_secret
  CLOUDINARY_FOLDER=medikiosk_documents
  ```
- If `DOCUMENT_STORAGE_PROVIDER=local`, documents are kept in `uploads/` (safe for local development and integration tests).

### 6. External AI & Integration Providers

External AI and health integration providers remain completely optional and fail-closed:
- **Mock Mode (Default):** If provider variables remain `mock`, the backend functions deterministically without external credentials or network dependencies.
- **Enabling Gemini:** Set `NLP_EXTRACTION_PROVIDER=gemini`, `EXTRACTION_PROVIDER=gemini`, `SUMMARY_PROVIDER=gemini`, and provide `GEMINI_API_KEY`.
- **Enabling Sarvam:** Set `ASR_PROVIDER=sarvam`, `OCR_PROVIDER=sarvam`, and provide `SARVAM_API_KEY`.
- **Enabling LLM Failover:** Set `LLM_FALLBACK_ENABLED=true` and provide `GROQ_API_KEY`.
- **Health Checks:** The `/health/status` endpoint reports configuration states (`configured` vs `mock`) without dispatching live external API calls or leaking credentials.

### 7. Security Hardening & Zero-PHI Invariants

- **Zero PHI in Logs:** Structured operational logs strictly redact patient identifiers, phone numbers, transcripts, clinical text, passwords, and tokens.
- **Error Sanitization:** Unhandled exceptions return generic `INTERNAL_SERVER_ERROR` with a tracking `X-Request-ID`. Database tracebacks and provider responses are never exposed to clients.
- **Health Redaction:** `/health`, `/health/db`, `/health/status`, and `/health/metrics` never expose secrets, passwords, or raw connection strings.
