# MediKiosk Clinical NLP Architecture (Stages 1–10)

## 1. Overview and Design Principles

The MediKiosk Clinical NLP subsystem transforms unstructured patient conversational input (spoken voice or written text) into structured, safe, ontology-mapped clinical history data for electronic health records and clinician decision-support kiosks.

### Core Architectural Invariants
1. **The Clinical Ontology is the Sole Source of Truth:**
   Clinical fields and completion rules are strictly bounded by `ClinicalOntologyField`. No dynamically fabricated fields or arbitrary clinical concepts are created.
2. **No Autonomous Diagnosis or Treatment Guidance:**
   The NLP subsystem is strictly an **information gathering and structuring system**. It never infers medical diagnoses, does not prescribe treatments, and does not perform autonomous clinical triage.
3. **Determinism over Stochasticity:**
   Validation, ontology mapping, clinical data persistence, and adaptive question selection are completely deterministic, reproducible, and verifiable.
4. **Safety & Verification Hierarchy:**
   Uncertain, unverified, or warning-triggering extractions are flagged for human clinician review (`NEEDS_VERIFICATION`) and never silently treated as verified truth.
5. **Doctor-Entered & Verified Data Immutability:**
   Data verified or entered by clinicians (`source='DOCTOR'` or `verification_status='VERIFIED'`) is strictly immutable to automated overwrites.

---

## 2. Pipeline Stages Summary (Stages 1–10)

| Stage | Name | Location | Responsibility |
|---|---|---|---|
| **Stage 1** | Text Preprocessing | `app/nlp/preprocessing/` | Deterministic normalization of patient text without stripping clinical terms, dosages, units, or negations. |
| **Stage 2** | Clinical Extraction | `app/nlp/extraction/` | Entity extraction with strict assertion statuses (`AFFIRMED`, `DENIED`, `SUSPECTED`). |
| **Stage 3** | Ontology Mapping | `app/nlp/ontology/` | Deterministic mapping of extracted facts to canonical `OntologyFieldKey` fields. |
| **Stage 4** | Validation & Safety | `app/nlp/validation/` | Rule-based gating: blocks hallucinated fields, ungrounded entities, and invalid assertions. |
| **Stage 5** | Pipeline Orchestrator | `app/nlp/pipeline/` | Pure stateless orchestrator executing Stages 1 -> 2 -> 3 -> 4. Emits `ClinicalNLPPipelineResult`. |
| **Stage 6** | Clinical Data Integration | `app/services/nlp_integration_service.py` | State boundary responsible for safely applying Stage 5 results to `InterviewClinicalData`. |
| **Stage 7** | Message Flow Integration | `app/services/interview_nlp_flow_service.py` | Integrates live patient text messages into the active interview session flow. |
| **Stage 8** | Adaptive Question Engine | `app/services/adaptive_question_service.py` | Deterministically selects next missing ontology field based on chief complaint context. |
| **Stage 9** | Voice / ASR Integration | `app/nlp/asr/` & `app/services/voice_nlp_flow_service.py` | Accepts voice audio, performs speech-to-text via `ASRProvider`, and chains Stages 5, 6, and 8. |
| **Stage 10** | End-to-End Hardening | `app/services/test_stage10_e2e_nlp_workflow.py` | End-to-end integration testing, boundary enforcement, and regression hardening. |

---

## 3. End-to-End Workflow Architecture

### A. Text Workflow
```
Patient Text Input
      │
      ▼
Interview Validation (must be IN_PROGRESS; active CLINICAL_HISTORY consent)
      │
      ▼
Message Persistence (stores original utterance in interview_messages)
      │
      ▼
Stage 5 ClinicalNLPPipeline
  ├── 1. Normalizer (strip harmless noise, preserve clinical tokens)
  ├── 2. Information Extraction (symptoms, duration, medications, allergies, assertion status)
  ├── 3. Ontology Mapping (maps to chief_complaint, hpi_*, etc.)
  └── 4. Safety Validation (gates invalid/ungrounded entities)
      │
      ▼
Stage 6 NLPIntegrationService
  ├── Gated by PipelineStatus (SKIPPED if INVALID or STAGE_FAILURE)
  ├── Protects DOCTOR and VERIFIED records from overwrite
  ├── Preserves DENIED and SUSPECTED assertions explicitly
  ├── Preserves NEEDS_VERIFICATION if warnings exist
  └── Synchronizes downstream hooks (medications, red-flag evaluation)
      │
      ▼
Stage 8 AdaptiveQuestionEngine
  ├── Classifies complaint context (CARDIORESPIRATORY, NEUROLOGICAL, etc.)
  ├── Evaluates remaining missing required ontology fields
  └── Returns localized question text and completion status
```

### B. Voice Workflow
```
Patient Audio Upload (WAV, MP3, WebM, M4A, OGG)
      │
      ▼
Format & Size Validation (< MAX_AUDIO_SIZE_MB; in-memory buffer)
      │
      ▼
ASR Provider Abstraction (MockASRProvider or SarvamASRProvider)
  ├── Transcribes audio in interview language
  └── Preserves numeric confidence score (HIGH, MEDIUM, LOW, UNKNOWN)
      │
      ▼
Low-Confidence Gating (< 0.60 forces requires_human_verification=True)
      │
      ▼
Chains into Message Persistence → Stage 5 → Stage 6 → Stage 8
```

---

## 4. Architectural Boundaries and Interfaces

### Document OCR vs. Conversational NLP Separation
- **Conversational NLP:** Operates on patient/clinician dialogue via text or audio utterances to collect history during an active interview session.
- **Document Processing:** Operates on uploaded files (prescriptions, lab reports, discharge summaries) via OCR, document extraction, and timeline generation.
- Both streams converge safely in downstream clinical-data structures and the Multi-Source Contradiction Engine, but the OCR pipeline is never merged into the conversational ASR/NLP pipeline.

### Red-Flag Safety Boundary
- NLP extraction gathers facts and symptoms (e.g. "severe chest pain radiating to left arm").
- It **never makes diagnostic triage decisions**.
- When Stage 6 writes clinical data, it triggers `red_flag_service.evaluate_interview_clinical_data()` which runs dedicated rule-based clinical safety algorithms.

### Medication Boundary
- NLP extracts medication entities (name, dosage, unit, frequency, route).
- It **never makes drug-drug interaction or contraindication judgments**.
- Extracted medications sync to `InterviewMedicationItem` for verification and comparison.

### Contradiction Engine Boundary
- When NLP writes clinical data, differences between patient-reported history and document-extracted records are detected by the Multi-Source Contradiction Engine.
- The NLP layer never autonomously decides which source is "correct". Discrepancies are surfaced for doctor review.

---

## 5. Confidence Classification & Verification Rules

Confidence is an operational reliability metric, not a measure of medical certainty.

- **`HIGH`** ($\ge 0.85$): Highly reliable provider extraction.
- **`MEDIUM`** ($0.60 \le \text{score} < 0.85$): Standard extraction.
- **`LOW`** ($< 0.60$): Automatically flags `requires_human_verification = True`.
- **`UNKNOWN`** (`None`): Provider did not return a score. Treated as unverified context without fabricating numeric values.

---

## 6. Provider Abstractions (Mock vs. Real)

| Provider Type | Abstract Interface | Mock Implementation | Real Implementation | Configuration Key |
|---|---|---|---|---|
| **ASR (Speech-to-Text)** | `ASRProvider` | `MockASRProvider` | `SarvamASRProvider` | `ASR_PROVIDER=sarvam`, `SARVAM_API_KEY` |
| **Clinical Extraction** | `ClinicalFactExtractionProvider` | `DeterministicMockExtractionProvider` | `GeminiClinicalFactExtractionProvider` | `NLP_EXTRACTION_PROVIDER=gemini`, `GEMINI_API_KEY` |
| **Case Summarization** | `CaseSummaryProvider` | `MockCaseSummaryProvider` | `GeminiCaseSummaryProvider` | `SUMMARY_PROVIDER=gemini`, `GEMINI_API_KEY` |
| **Summary Translation** | `TranslationProvider` | `MockTranslationProvider` | `GeminiTranslationProvider` | `TRANSLATION_PROVIDER=gemini`, `GEMINI_API_KEY` |
| **Document OCR** | `OCRProvider` | `MockOCRProvider` | Separate pipeline | `OCR_PROVIDER` |

### Provider Configuration & Invariants
- **Default Behavior:** In development and automated test runs, all provider factories (`get_nlp_extraction_provider()`, `get_asr_provider()`, `get_case_summary_provider()`, `get_translation_provider()`) default strictly to their deterministic mock implementations (`mock`).
- **Real Provider Activation:** To activate real providers, configure the corresponding provider selection variable and credentials in `backend/.env`:
  ```bash
  NLP_EXTRACTION_PROVIDER=gemini
  SUMMARY_PROVIDER=gemini
  TRANSLATION_PROVIDER=gemini
  ASR_PROVIDER=sarvam

  GEMINI_API_KEY=your_google_gemini_api_key
  GEMINI_MODEL_NAME=gemini-2.5-flash
  GEMINI_TIMEOUT_SECONDS=15

  SARVAM_API_KEY=your_sarvam_api_key
  SARVAM_MODEL_NAME=saaras:v3
  SARVAM_TIMEOUT_SECONDS=15
  ```
- **Error Sanitization:** All provider integrations sanitize error messages to ensure API keys and authorization headers are never logged or returned in responses (`[REDACTED]`).
- **No Direct Clinical Writes:** Real Gemini output is untrusted input. It must flow through Pydantic schema validation -> Stage 4 clinical safety validation -> Stage 6 clinical data integration. It can never directly alter database records or overwrite doctor-verified clinical data.
- **ASR Confidence Policy:** `SarvamASRProvider` preserves confidence scores only if returned by the API. If absent, `confidence=None` (`UNKNOWN`) is recorded, triggering clinician review if necessary.

---

## 7. Running Tests

### Automated Deterministic Regression Suite (166 Tests)
Automated unit tests use deterministic mocks and mocked HTTP requests; they make zero external network requests and consume zero paid credits.

```bash
# Stages 1–5 Pure NLP Tests (77 tests)
PYTHONPATH=backend python3 -m unittest discover -s backend/app/nlp -p "test_*.py"

# Stage 6 Integration Tests (12 tests)
PYTHONPATH=backend python3 -m unittest -v app.services.test_nlp_integration_service

# Stage 7 Message Flow Tests (12 tests)
PYTHONPATH=backend python3 -m unittest -v app.services.test_interview_nlp_flow_service

# Stage 8 Adaptive Question Tests (15 tests)
PYTHONPATH=backend python3 -m unittest -v app.services.test_adaptive_question_service

# Stage 9 Voice / ASR Tests (15 tests)
PYTHONPATH=backend python3 -m unittest -v app.services.test_voice_nlp_flow_service

# Stage 10 End-to-End Hardening & Validation Tests (13 tests)
PYTHONPATH=backend python3 -m unittest -v app.services.test_stage10_e2e_nlp_workflow

# Step 11 Real Provider Unit Tests (22 tests)
PYTHONPATH=backend python3 -m unittest -v app.services.test_real_providers_unit
```

### Manual Isolated Smoke Testing (Live APIs)
When live credentials are configured in `backend/.env`, verify external connectivity using the isolated smoke-test script:

```bash
PYTHONPATH=backend python3 backend/scripts/smoke_test_real_providers.py
```
*(If credentials are not configured, this script safely outputs `NOT RUN — credentials unavailable` without erroring or leaking secrets).*

---

## 8. Real Provider Live Smoke Verification Status (Step 13)

| Provider | Contract Verified | Unit Tested | Live Smoke Tested | Verification Status |
|---|---|---|---|---|
| **Google Gemini** (`gemini-2.5-flash`) | YES | YES (22 tests) | NO | **NOT RUN — credentials unavailable** |
| **Sarvam AI** (`saaras:v3`) | YES | YES (22 tests) | NO | **NOT RUN — credentials unavailable** |

### Unavailability / Reason Details
- **Gemini (`GEMINI_API_KEY`):** Live smoke testing was not run because `GEMINI_API_KEY` is not configured in `backend/.env` or the runtime environment. The provider contract, REST endpoints (`v1beta/models/gemini-2.5-flash:generateContent`), structured JSON generation schema, and Pydantic validation have been unit-tested and verified with deterministic mocks.
- **Sarvam AI (`SARVAM_API_KEY`):** Live smoke testing was not run because `SARVAM_API_KEY` is not configured in `backend/.env` or the runtime environment. The provider contract, REST endpoint (`https://api.sarvam.ai/speech-to-text`), multipart audio form upload, BCP-47 language codes, and confidence handling (`confidence=None` / `UNKNOWN`) have been unit-tested and verified with deterministic mocks.
- **Credential Safety & Isolation:** Smoke tests never touch the clinical database (`Patient`, `Interview`, `InterviewClinicalData`), make zero database writes, and redact any API keys or tokens (`[REDACTED]`) in all error traces.

---

## 9. End-to-End Medical Document Processing Pipeline (Step 14)

### Architectural Separation
The MediKiosk backend maintains strict architectural separation between conversational clinical NLP and medical document processing:
- **Conversational NLP Pipeline (Stages 1–13):** Patient Text / Voice ➔ ASR ➔ Normalizer ➔ Fact Extraction ➔ Ontology Mapping ➔ Validation ➔ Clinical Data Integration ➔ Adaptive Next-Question Engine.
- **Medical Document Pipeline (Step 14):** Document Upload ➔ Storage ➔ OCR ➔ Structured Medical Extraction ➔ Schema Validation ➔ Timeline Synchronization ➔ Abnormal Lab Value Evaluation ➔ Medication History Synchronization ➔ Contradiction Engine Evaluation.
- **Invariant:** Document OCR text is never routed through Stage 5 conversational NLP.

### Document Lifecycle & State Machine
```
           [Upload]
              │
              ▼
          UPLOADED
              │ (validate & consent check)
              ▼
          PROCESSING
         ┌────┴────┐
 (Fatal Failure) (Success)
         │         │
         ▼         ▼
       FAILED   COMPLETED
         ▲
         │ (retry/reprocess)
```
- **Allowed Transitions:**
  - `UPLOADED` ➔ `PROCESSING`
  - `PROCESSING` ➔ `COMPLETED`
  - `PROCESSING` ➔ `FAILED`
  - `FAILED` ➔ `PROCESSING` (Retry)
  - `COMPLETED` ➔ `PROCESSING` (Reprocess)

### Fatal vs Non-Fatal Error Isolation
- **Fatal Boundaries (Halt processing ➔ FAILED):**
  1. Missing or revoked `DOCUMENT_PROCESSING` consent (HTTP 403 / `ConsentRequiredException`).
  2. Document or interview ownership mismatch / cross-patient violation.
  3. Storage retrieval failure or empty document content.
  4. OCR provider crash or empty OCR text.
  5. Medical extraction provider crash.
  6. Schema validation failure against `StructuredMedicalData` (HTTP 422).
- **Non-Fatal Boundaries (Logged warnings, extraction & document remain COMPLETED):**
  1. Confidence evaluation failure (confidence defaults to `UNKNOWN`).
  2. Timeline event generation failure.
  3. Abnormal lab value evaluation failure.
  4. Medication history synchronization failure.
  5. Multi-source contradiction engine evaluation failure.

### Idempotency & Duplicate Prevention
- **Timeline Events:** Atomic reconciliation deletes prior events associated with `document_id` before inserting fresh events.
- **Abnormal Lab Values:** Atomic reconciliation deletes prior investigation results associated with `document_id` before inserting fresh results.
- **Medication History:** Deletes prior records matching `extraction_id` before inserting fresh records.
- **Contradictions:** Checks candidate keys against existing records and skips already detected conflicts without creating duplicates.

### Provider Behavior & Limitations
- **Mock OCR Provider:** Deterministic synthetic text extraction supporting PDF and images for test suites.
- **Real OCR Provider:** Provider abstraction in place; real provider requires external cloud/engine credentials.
- **Handwriting Accuracy Notice:** High handwriting accuracy is not claimed without real provider integration and production testing against clinical handwriting benchmarks.

### Running Document Pipeline Tests (20 Scenarios)
```bash
PYTHONPATH=backend python3 -m unittest -v app.services.test_document_processing_pipeline
```

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
