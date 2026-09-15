# MediKiosk Frontend Integration Guide (Step 1 Foundation)

## 1. Architecture Overview

MediKiosk frontend is structured as a lightweight Multi-Page Application (MPA) using vanilla HTML, CSS (`tokens.css`), and JavaScript.
To support robust backend integration without adding bloated client frameworks (React/Axios/Redux), Step 1 provides a clean, native foundation consisting of:

- **Centralized Configuration**: [config.js](file:///home/rushi/SIH047/frontend/src/scripts/config.js)
- **Scoped Session State**: [session.js](file:///home/rushi/SIH047/frontend/src/scripts/session.js)
- **Standardized API Client**: [api.js](file:///home/rushi/SIH047/frontend/src/scripts/api.js)

### Directory Layout
```
frontend/
├── backend_integration_audit.md   # Initial surface audit
├── integration_guide.md           # This architecture & usage guide
├── tests/
│   └── test_step1_foundation.js   # Automated mock unit test suite
└── src/
    ├── screens/                   # 14 HTML screen templates
    ├── styles/                    # Design tokens & CSS
    └── scripts/
        ├── config.js              # Base URL configuration & overrides
        ├── session.js             # sessionStorage workflow manager
        └── api.js                 # Vanilla fetch client with auth & error mapping
```

---

## 2. Shared Scripts Reference

Any screen needing backend connectivity includes the following tags in the `<head>`:
```html
<script src="../scripts/config.js"></script>
<script src="../scripts/session.js"></script>
<script src="../scripts/api.js"></script>
```

---

## 3. Configuration (`config.js`)

- **Default Base URL**: `http://127.0.0.1:8000` (FastAPI backend local address)
- **Runtime Overrides**:
  - `window.__MEDIKIOSK_CONFIG__.API_BASE_URL`
  - `window.MEDIKIOSK_API_BASE_URL`
- **Helper Methods**:
  - `MediKioskConfig.getApiBaseUrl()`: Returns sanitized base URL without trailing slash.
  - `MediKioskConfig.setApiBaseUrl(url)`: Dynamically updates the base URL if needed.

---

## 4. Session State Management (`session.js`)

MediKiosk is an active walk-up kiosk environment. State across screens is maintained in browser `sessionStorage` (scoped strictly to the current browser tab and erased on browser close).

### Storage Policy
| Category | Permitted Keys | Description |
|---|---|---|
| **Permitted** | `medikiosk_auth_token` | Active JWT access token for authenticated requests |
| **Permitted** | `medikiosk_patient_id` | UUID of the registered/identified patient |
| **Permitted** | `medikiosk_session_id` | UUID of the active kiosk intake session |
| **Permitted** | `medikiosk_interview_id` | UUID of the active AI clinical interview |
| **STRICTLY FORBIDDEN** | *None* | Passwords, API keys, clinical transcripts, OCR text, medical documents, JWT signing secrets, provider credentials. |

### Available Methods
- `MediKioskSession.setAuthToken(token)` / `getAuthToken()` / `clearAuthToken()`
- `MediKioskSession.setPatientId(id)` / `getPatientId()` / `clearPatientId()`
- `MediKioskSession.setSessionId(id)` / `getSessionId()` / `clearSessionId()`
- `MediKioskSession.setInterviewId(id)` / `getInterviewId()` / `clearInterviewId()`
- `MediKioskSession.clearWorkflowState()`: Resets all workflow identifiers upon completion, restart, or session timeout.
- `MediKioskSession.getWorkflowSummary()`: Inspects active workflow IDs without exposing token strings.

---

## 5. Shared API Client (`api.js`)

The API client provides a clean, modern `window.fetch` wrapper exposed globally as `MediKioskApi` (and aliased as `api` for convenience).

### Key Features
1. **Automatic Authorization**: Injects `Authorization: Bearer <token>` when a token exists in `sessionStorage`.
2. **Safe JSON Parsing**: Safely handles empty bodies (204 No Content) and non-JSON payloads without uncaught parse exceptions.
3. **Structured `ApiError`**: Normalizes HTTP errors into a predictable object with status flags (`isAuthError`, `isForbidden`, `isValidationError`, `isRateLimit`, `isServerError`, `isNetworkError`).
4. **Zero Sensitive Logging**: No authentication headers, JWT tokens, or clinical payloads are ever printed to the console.

### Common Usage Patterns for Future Screens

#### 1. GET Request
```javascript
try {
  const response = await MediKioskApi.get('/api/v1/patients/me');
  console.log('Patient loaded:', response.data.full_name);
} catch (err) {
  if (err.isAuthError) {
    window.location.href = 'screen1a-identity.html';
  } else {
    showErrorMessage(err.message);
  }
}
```

#### 2. POST JSON Request (Patient Registration Example)
```javascript
try {
  const payload = {
    phone_number: '+919876543210',
    name: 'Sunita Sharma',
    date_of_birth: '1985-07-20',
    gender: 'Female',
    preferred_language: 'en'
  };
  const response = await MediKioskApi.post('/api/patients', payload);
  
  // Save patient ID for subsequent workflow screens
  MediKioskSession.setPatientId(response.data.id);
} catch (err) {
  if (err.isConflict) {
    showErrorMessage('Patient with this phone number is already registered.');
  } else if (err.isValidationError) {
    showErrorMessage(err.message);
  } else {
    showErrorMessage('Registration failed. Please check network connectivity.');
  }
}
```

#### 3. Multipart Form / File Upload
```javascript
const formData = new FormData();
formData.append('document_type', 'prescription');
formData.append('file', fileInput.files[0]);

try {
  const response = await MediKioskApi.postForm('/api/documents/upload', formData);
  console.log('Document uploaded successfully');
} catch (err) {
  showErrorMessage(err.message);
}
```

#### 4. Kiosk Workflow Reset
When a patient prints their token or finishes their visit:
```javascript
MediKioskSession.clearWorkflowState();
window.location.href = 'home.html';
```

---

## 6. Step 2 Integration: Patient Registration & Encounter Session

### 1. Integrated Screens
- **[screen1a-identity.html](file:///home/rushi/SIH047/frontend/src/screens/screen1a-identity.html)**: Simulates ABHA QR card scan demographic extraction and executes `POST /api/patients` followed by `POST /api/sessions`.
- **[screen1a-manual-entry.html](file:///home/rushi/SIH047/frontend/src/screens/screen1a-manual-entry.html)**: Accepts mobile number via touch keypad and patient demographic inputs, verifies OTP, and executes `POST /api/patients` followed by `POST /api/sessions`.

### 2. Verified Backend Contract

#### Patient Registration Endpoint
- **Method**: `POST`
- **Path**: `/api/patients`
- **Request Body (`PatientCreate`)**:
  - `phone_number` (string, required): Phone number matching `^\+?[0-9\s\-]{8,20}$`
  - `name` (string, required): 1 to 255 characters
  - `date_of_birth` (string, required): Format `YYYY-MM-DD` (between 1900-01-01 and today)
  - `gender` (string, required): e.g., `"Female"`, `"Male"`, `"Other"`
  - `preferred_language` (string, optional): Active language code (`"en"`, `"hi"`, `"mr"`)
  - *Note: `extra="forbid"` is enforced by Pydantic; no extra fields permitted.*
- **Response Body (`PatientResponse`, HTTP 201)**:
  - `id` (integer): Auto-incremented primary key
  - `phone_number`, `name`, `date_of_birth`, `gender`, `preferred_language`
  - `created_at`, `updated_at` (ISO timestamps)

#### Session Establishment Endpoint
- **Method**: `POST`
- **Path**: `/api/sessions`
- **Request Body (`SessionCreateRequest`)**:
  - `patient_id` (integer, required): Patient primary key
  - `interview_id` (integer, optional): Optional interview ID (omitted during initial intake)
  - *Note: `extra="forbid"` is enforced; only `patient_id` is supplied.*
- **Response Body (`PatientSessionResponse`, HTTP 201)**:
  - `id` (integer): Encounter session ID
  - `patient_id` (integer): Linked patient ID
  - `status` (string): `"REGISTRATION"`
  - `next_action` (string): `"START_INTERVIEW"`
  - `started_at`, `last_activity_at`, `created_at`, `updated_at`

### 3. Session State Created
- `MediKioskSession.setPatientId(patientResponse.data.id)` → writes to `sessionStorage.medikiosk_patient_id`
- `MediKioskSession.setSessionId(sessionResponse.data.id)` → writes to `sessionStorage.medikiosk_session_id`
- **Privacy Invariant**: ZERO patient names, phone numbers, dates of birth, or clinical payloads are stored in `sessionStorage`.

### 4. Error Handling & Invariants
- **HTTP 409 Conflict**: Triggers user-friendly alert notifying that the patient is already registered. Button re-enables and invalid state is not stored.
- **HTTP 422 Validation Error**: Displays sanitized validation message (e.g. invalid date of birth or phone format).
- **Network / Server Failure**: Displays a friendly connectivity alert.
- **Double Submission Prevention**: In-flight requests lock submit buttons and disable repeat taps until completion or error.
- **Next Workflow Screen**: On successful registration and session creation, automatically navigates to `screen1b-consent.html`.

---

## 7. Step 3 Integration: Purpose-Specific Patient Consent

### 1. Integrated Screen
- **[screen1b-consent.html](file:///home/rushi/SIH047/frontend/src/screens/screen1b-consent.html)**: Replaced misleading blanket consent with granular, purpose-specific selection cards mapping 1-to-1 with backend consent rules.

### 2. Verified Backend Consent Contract

#### Grant Consent Endpoint
- **Method**: `POST`
- **Path**: `/api/patients/{patient_id}/consents`
- **Request Body (`ConsentCreateRequest`)**:
  - `purpose` (string enum, required): One of the six independent consent purposes.
  - `language_code` (string, optional, default: `"en"`): Patient language (`"en"`, `"hi"`, `"mr"`).
  - `consent_version` (string, optional, default: `"1.0"`): Policy revision identifier.
  - `collection_method` (string enum, optional, default: `"PATIENT_SELF"`): `"PATIENT_SELF"`, `"ASSISTED"`, or `"DOCTOR_ASSISTED"`.
  - `interview_id` (integer, optional): Scope constraint (omitted at intake).
  - `expires_at` (timestamp, optional): Explicit expiration (defaults to indefinite/superseded).
  - *Note: `extra="forbid"` is enforced; strictly only allowed fields permitted.*
- **Response Body (`ConsentResponse`, HTTP 201)**:
  - `id` (integer): Auto-incremented consent record ID
  - `patient_id` (integer): Linked patient ID
  - `purpose` (string): Granted purpose enum value
  - `status` (string): `"GRANTED"`
  - `collection_method`, `consent_version`, `language_code`, `granted_at`

#### Check Active Consent Endpoint
- **Method**: `GET`
- **Path**: `/api/patients/{patient_id}/consents/active/{purpose}`
- **Response Body (`ActiveConsentResponse`, HTTP 200)**:
  - `active` (boolean): `true`
  - `patient_id` (integer): Linked patient
  - `purpose` (string): Purpose checked
  - `consent` (`ConsentResponse`): Active underlying consent record

### 3. Six Independent Consent Purposes
| Purpose Enum | Kiosk UI Checkpoint | Initial Default | Role / Downstream Boundary |
|---|---|---|---|
| `CLINICAL_HISTORY` | Clinical History & Symptoms | **Checked (Mandatory)** | Unlocks Screen 2 AI interview workflow |
| `DOCUMENT_PROCESSING` | Medical Document Processing | Checked (Optional) | Required for Screen 3 OCR / prescription scans |
| `AI_SUMMARIZATION` | AI Clinical Summarization | Checked (Optional) | Required for Screen 4 AI clinical summary generation |
| `BILINGUAL_OUTPUT` | Bilingual Output & Translation | Checked (Optional) | Required for vernacular translation of notes |
| `DATA_SHARING` | Hospital HIS Data Sharing | Unchecked (Optional) | Required for FHIR export to AIIA hospital HIS |
| `ABHA_LINKAGE` | Ayushman Bharat (ABHA) Linkage | Unchecked (Optional) | Required for linking records to ABDM profile |

### 4. Authoritative State & Privacy Invariants
- **Backend Authority**: Frontend does **NOT** store consent records or legal text in browser `sessionStorage`. The database remains the single authoritative source of truth.
- **Fail-Closed Protection**: If `CLINICAL_HISTORY` is unchecked, the client refuses to proceed and alerts the user.
- **Purpose Isolation**: Only explicitly checked purposes are posted; other purposes are never silently granted.
- **Next Workflow Stage**: Upon successful granting of `CLINICAL_HISTORY` consent, navigation proceeds to `screen2-interview.html`.

---

## 8. Step 4 Integration: Clinical Interview & Adaptive Intake Engine

### 1. Integrated Screens
- **[screen2-interview.html](file:///home/rushi/SIH047/frontend/src/screens/screen2-interview.html)**: Welcome/launch screen from Step 1b consent. Connects interview creation, encounter attachment, consent verification, and interview start to the backend state machine.
- **[screen2a-standard.html](file:///home/rushi/SIH047/frontend/src/screens/screen2a-standard.html)**: Interactive clinical intake screen. Retrieves Stage 8 adaptive next questions, renders dynamic question text/categories, processes patient text responses through Stage 5/6 NLP, evaluates red flags, and manages terminal transitions.
- **[screen2b-ayush.html](file:///home/rushi/SIH047/frontend/src/screens/screen2b-ayush.html)**: Synchronizes interview mode to `AYUSH` via `PUT /api/interviews/{id}/mode` and prepares for Step 3 documents.

### 2. Verified Backend Interview Endpoints & Contracts

#### A. Interview Creation
- **Method**: `POST`
- **Path**: `/api/interviews`
- **Request Body (`InterviewCreate`, `extra="forbid"`)**:
  - `patient_id` (integer, required, > 0): ID of registered patient
  - `preferred_language` (string, optional): Language code (`"en"`, `"hi"`, `"mr"`)
- **Response Body (`InterviewResponse`, HTTP 201)**:
  - `id` (integer): Auto-incremented interview ID
  - `patient_id` (integer): Linked patient ID
  - `status` (string): `"NOT_STARTED"`
  - `mode` (string): `"GENERAL"`
  - `language_code` (string): Effective language code

#### B. Attach Interview to Encounter Session
- **Method**: `POST`
- **Path**: `/api/sessions/{session_id}/attach-interview`
- **Request Body (`SessionAttachInterviewRequest`, `extra="forbid"`)**:
  - `interview_id` (integer, required, > 0): ID of interview to bind to session
- **Response Body (`PatientSessionResponse`, HTTP 200)**:
  - `id` (integer): Encounter session ID
  - `interview_id` (integer): Attached interview ID
  - `status` (string): Updated derived session status

#### C. Start Interview (Enforces Consent)
- **Method**: `POST`
- **Path**: `/api/interviews/{interview_id}/start`
- **Request Body**: `{}`
- **Security Invariant**: Strictly requires active `CLINICAL_HISTORY` consent. If missing/revoked, returns `HTTP 403 Forbidden` (`ConsentRequiredException`).
- **Response Body (`InterviewResponse`, HTTP 200)**:
  - `id` (integer): Interview ID
  - `status` (string): `"IN_PROGRESS"`
  - `started_at` (timestamp): Start timestamp

#### D. Fetch Adaptive Next Question
- **Method**: `GET`
- **Path**: `/api/interviews/{interview_id}/next-question`
- **Response Body (`NextQuestionResponse`, HTTP 200)**:
  - `has_next` (boolean): `true` if more questions required
  - `is_complete` (boolean): `true` if clinical history collection is finished
  - `field_key` (string): Clinical ontology target field key
  - `section` (string): Category section (e.g. `"CHIEF_COMPLAINTS"`, `"HISTORY_OF_PRESENT_ILLNESS"`)
  - `display_name` (string): Human-readable question label
  - `description` (string): Detailed patient prompt text
  - `required` (boolean): Whether field is clinically required
  - `priority` (integer): Priority order index
  - `reason` (string): Selection reason / explanation
  - `requires_verification` (boolean, optional): Whether human verification flag is set

#### E. Process Patient Text Message
- **Method**: `POST`
- **Path**: `/api/interviews/{interview_id}/messages/process`
- **Request Body (`InterviewMessageCreate`, `extra="forbid"`)**:
  - `role` (string, required): `"PATIENT"`
  - `content` (string, required, 1-10000 chars): Message transcript or utterance text
  - `language` (string, optional): Language of utterance (`"en"`, `"hi"`, `"mr"`)
  - `confidence` (float, optional): ASR or confidence score
- **Response Body (`InterviewMessageProcessResponse`, HTTP 200)**:
  - `message` (`InterviewMessageResponse`): Persisted message record
  - `nlp_status` (string): Pipeline outcome (`"VALID"`, `"VALID_WITH_WARNINGS"`, etc.)
  - `integration_status` (string): Clinical data persistence status (`"APPLIED"`, `"SKIPPED"`, `"FAILED"`)
  - `applied_fields` (list of strings): Ontology field keys updated
  - `next_question` (`NextQuestionResponse` | `null`): Next adaptive question returned directly
  - `is_history_complete` (boolean): Whether all required history fields are collected

#### F. Evaluate Red Flags
- **Method**: `POST`
- **Path**: `/api/interviews/{interview_id}/red-flags/evaluate`
- **Response Body (`RedFlagEvaluationResponse`, HTTP 200)**:
  - `has_active_red_flags` (boolean): `true` if clinical red flag rules fired
  - `highest_severity` (string | null): `"CRITICAL"`, `"HIGH"`, `"MEDIUM"`, `"LOW"`
  - `red_flags` (list): Active red flag rule detections

#### G. Synchronize Interview Mode
- **Method**: `PUT`
- **Path**: `/api/interviews/{interview_id}/mode`
- **Request Body (`InterviewModeUpdate`, `extra="forbid"`)**:
  - `mode` (string, required): `"GENERAL"` | `"AYUSH"`
- **Response Body (`InterviewModeResponse`, HTTP 200)**:
  - `interview_id` (integer): Interview ID
  - `mode` (string): Updated mode

---

### 3. Session Identifiers & Storage Purity
- Only `auth_token`, `patient_id`, `session_id`, and `interview_id` are stored in browser `sessionStorage`.
- **Zero Storage Invariant**: Zero transcripts, questions, user answers, clinical data, or OCR extracts are ever written to browser `sessionStorage` or `localStorage`.

### 4. Double Submission & Loading States
- Upon submitting a message or starting an interview, response buttons and interactive option cards are immediately disabled (`disabled=true`, `opacity=0.6`, `pointer-events=none`).
- Status indicator pill transitions to `"AI: Processing answer..."` until the backend response completes or errors out, preventing duplicate network requests.

### 5. Error Handling & Consent Enforcement
- **HTTP 403 (Consent Required)**: Caught specifically to alert patient that `CLINICAL_HISTORY` consent is mandatory, then safely redirects back to `screen1b-consent.html`.
- **HTTP 401 / 404 / 409 / 422 / 429 / 500+ / Network Drops**: Safely handled using `ApiError` attributes and displayed in existing user-safe alert banners without exposing stack traces or API keys.

### 6. Known Limitations & What Remains for Next Step
- **Audio / Voice / MediaRecorder**: Deferred to a dedicated voice integration step. The microphone button toggles visual waveform states without sending live binary audio.
- **Case Summaries & Doctor Verification**: Step 4/5 screens remain simulated until their respective integration steps.

---

## 9. Step 5 Integration: Document Upload & Clinical OCR Processing

### 1. Integrated Screen
- **[screen3-documents.html](file:///home/rushi/SIH047/frontend/src/screens/screen3-documents.html)**: Integrated real file input, client-side validation, authoritative `DOCUMENT_PROCESSING` consent verification, multipart upload via `MediKioskApi.postForm`, synchronous OCR and extraction pipeline invocation, UI scan animation synchronization, and interactive timeline rendering.

### 2. Verified Backend Document APIs & Contracts

#### A. Document Upload
- **Method**: `POST`
- **Path**: `/api/interviews/{interview_id}/documents`
- **Content-Type**: `multipart/form-data` (boundary generated automatically by browser via `MediKioskApi.postForm`)
- **Request Form Data**:
  - `file` (`UploadFile`, required): Document binary
  - `document_type` (`DocumentType` enum, optional): `PRESCRIPTION`, `LAB_REPORT`, `DISCHARGE_SUMMARY`, `MEDICAL_RECORD`, or `OTHER`
- **Accepted MIME Types**: `application/pdf`, `image/jpeg`, `image/png`, `image/webp`
- **Maximum File Size**: 10 MB (`MAX_DOCUMENT_SIZE_MB = 10`)
- **Response Body (`MedicalDocumentResponse`, HTTP 201)**:
  - `id` (integer): Auto-incremented document ID
  - `interview_id` (integer): Linked interview ID
  - `patient_id` (integer): Linked patient ID
  - `original_filename` (string): Preserved safe filename
  - `content_type` (string): Validated MIME type
  - `file_size` (integer): Size in bytes
  - `document_type` (string): Assigned enum value
  - `processing_status` (string): Initial status `"UPLOADED"`
  - `uploaded_at` (timestamp): UTC upload timestamp

#### B. Document Processing (Synchronous OCR & Structured Extraction)
- **Method**: `POST`
- **Path**: `/api/interviews/{interview_id}/documents/{document_id}/process`
- **Request Body**: `{}`
- **Consent Pre-condition**: The backend strictly validates active `DOCUMENT_PROCESSING` consent for the interview's patient. If missing or revoked, returns `HTTP 403 Forbidden` (`ConsentRequiredException: Consent required: purpose DOCUMENT_PROCESSING...`).
- **Response Body (`MedicalDocumentExtractionResponse`, HTTP 200)**:
  - `id` (integer): Extraction record ID
  - `document_id` (integer): Document ID
  - `extraction_version` (integer): Incremental version number
  - `provider_name` (string): Underlying extraction provider
  - `extraction_status` (string): `"COMPLETED"` or `"FAILED"`
  - `structured_data` (`StructuredMedicalData` | `null`): Structured clinical entities (patient info, clinical notes, medications, abnormal labs, vitals, timeline events)
  - `confidence_summary` (`DocumentConfidenceSummary` | `null`): Aggregate confidence level (`"HIGH"`, `"MEDIUM"`, `"LOW"`, `"UNKNOWN"`) and verification requirement flag
  - `disclaimer` (string): "Extracted from uploaded document; requires clinical verification."

#### C. Document Listing & Status Retrieval
- **Method**: `GET`
- **Path**: `/api/interviews/{interview_id}/documents`
- **Response Body (`MedicalDocumentListResponse`, HTTP 200)**:
  - `interview_id` (integer): Linked interview
  - `total_documents` (integer): Total count of uploaded documents
  - `documents` (list of `MedicalDocumentResponse`): Array of documents with their current `processing_status` (`"UPLOADED"`, `"PROCESSING"`, `"COMPLETED"`, `"FAILED"`)

### 3. Document Category Mapping
| UI Category | Backend Enum Value | Description |
|---|---|---|
| Prescriptions | `PRESCRIPTION` | Outpatient prescription slips and medication orders |
| Lab Reports | `LAB_REPORT` | Pathology, biochemistry, hematology diagnostic reports |
| Discharge Summary | `DISCHARGE_SUMMARY` | Inpatient hospital discharge summaries |
| Medical Records | `MEDICAL_RECORD` | Clinical consultations, imaging reports, referral letters |
| Other | `OTHER` | Miscellaneous healthcare documents |

### 4. Authoritative Consent & Client Validation Rules
- **Consent Verification**: Before reading or uploading any file, the frontend verifies active consent via `GET /api/patients/{patient_id}/consents/active/DOCUMENT_PROCESSING`. If inactive, upload is aborted and a safe prompt directs the patient back to `screen1b-consent.html`.
- **Client-side File Validation**:
  - File presence check
  - MIME type check against whitelist (`application/pdf`, `image/jpeg`, `image/png`, `image/webp`)
  - File size check against 10 MB maximum
  - Safe error display in user alert banner `#documentErrorMsg`
- **Double Submission Guard**: During upload and processing, action buttons are disabled and a submission lock flag prevents accidental concurrent uploads.

### 5. Storage Purity & Security Invariants
- **Zero Document Storage**: Zero file blobs, base64 strings, raw OCR text, clinical extractions, medication lists, or lab values are stored in `sessionStorage` or `localStorage`.
- **Strict Identifier Isolation**: Only `auth_token`, `patient_id`, `session_id`, and `interview_id` are persisted in browser session.
- **Zero Sensitive Logging**: File contents, extracted clinical entities, patient names, and auth credentials are never logged to `console.log` or client telemetry.

### 6. Next Integration Stage
- **Step 6**: Case Summary Generation & Patient Confirmation (`screen4-summary.html`).

---

## 10. Step 6 Integration: Clinical Case Summary, Patient Confirmation & OPD Queue

### 1. Screen & Scope Overview
- **Screen File**: `frontend/src/screens/screen4-summary.html`
- **Scope**:
  - Connects patient review screen to backend summary endpoints (`POST /api/interviews/{id}/summary/generate`, `GET /api/interviews/{id}/summary`, `POST /api/interviews/{id}/summary/{summary_id}/bilingual`).
  - Implements the complete patient confirmation lifecycle (`POST /api/interviews/{id}/summary/{summary_id}/confirmation/start`, `POST /api/interviews/{id}/confirmations/{cid}/items/{item_id}/confirm`, `POST /api/interviews/{id}/confirmations/{cid}/items/{item_id}/flag`, `POST /api/interviews/{id}/confirmations/{cid}/complete`).
  - Connects final intake completion to the hospital OPD Queue allocation system (`POST /api/opd/queue/entries`).
  - Preserves calm design, claymorphic aesthetics, dual-view transition (Review -> Done Queue Token), and accessibility hints.

### 2. Backend API Contracts

#### A. Case Summary Generation & Retrieval
- **Generate**: `POST /api/interviews/{interview_id}/summary/generate`
  - Requires active `AI_SUMMARIZATION` consent (`GET /api/patients/{patient_id}/consents/active/AI_SUMMARIZATION`).
  - Returns `MedicalCaseSummaryResponse` with `summary_status: "DRAFT"`, structured sections (`chief_complaint`, `history_of_present_illness`, `ayush_profile`, `medication_history`, etc.), source grounding links, and mandatory clinical disclaimer.
- **Get Existing**: `GET /api/interviews/{interview_id}/summary`
  - Retrieves active draft or finalized summary for the interview.

#### B. Bilingual Summary Translation
- **Translate**: `POST /api/interviews/{interview_id}/summary/{summary_id}/bilingual`
  - Requires active `BILINGUAL_OUTPUT` consent.
  - Accepts `{"target_language_code": "hi" | "mr"}`.
  - Returns translated display labels and statement items for non-English locales.

#### C. Patient Confirmation Lifecycle
- **Start Confirmation**: `POST /api/interviews/{interview_id}/summary/{summary_id}/confirmation/start`
  - Creates confirmation session with individual reviewable statement items in `PENDING` state.
- **Confirm Item**: `POST /api/interviews/{interview_id}/confirmations/{confirmation_id}/items/{item_id}/confirm`
  - Transitions item response to `CONFIRMED`.
- **Flag Correction**: `POST /api/interviews/{interview_id}/confirmations/{confirmation_id}/items/{item_id}/flag`
  - Records patient correction note and sets response to `FLAGGED`.
- **Complete Confirmation**: `POST /api/interviews/{interview_id}/confirmations/{confirmation_id}/complete`
  - Completes the confirmation session, setting status to `CONFIRMED` or `FLAGGED`.

#### D. OPD Queue Token Allocation
- **Allocate Token**: `POST /api/opd/queue/entries`
  - Payload: `{"patient_id": <int>, "interview_id": <int>, "priority": "NORMAL"}`
  - Returns `OpdQueueEntryResponse` containing `token_number` (e.g. `24` -> `A-24`), queue position, and waiting area guidance.

### 3. Storage Purity & Security Invariants
- **Zero PHI in Storage**: Zero clinical summaries, statement texts, doctor correction notes, or queue tokens are stored in `sessionStorage` or `localStorage`.
- **Authoritative Consents**: `AI_SUMMARIZATION` and `BILINGUAL_OUTPUT` consents are validated authoritatively against the backend API before invoking AI services.
- **Zero Sensitive Logging**: Summaries, transcripts, corrections, and auth credentials are never logged to the browser console.



---

## Step 10: Doctor & Staff Dashboard Integration (`screen5-doctor-dashboard.html`)

### 1. Overview
The clinical doctor dashboard provides authenticated staff with a real-time patient intake queue, structured case sheet review, and clinician sign-off workflow. The frontend connects to the following endpoints via `MediKioskApi`:

### 2. Staff Authentication
- **Login**: `POST /api/auth/login`
  - Payload: `{"email": <str>, "password": <str>}`
  - On success: JWT stored via `MediKioskSession.setAuthToken()`. Topbar shows authenticated user email and role.
  - On failure: Login modal error inline (no page reload). Token never cached.
- **Identity Check**: `GET /api/auth/me`
  - Validates existing token on page load. Clears session on 401/403.
- **Sign Out**: Calls `MediKioskSession.clearAuthToken()` and resets dashboard.

### 3. OPD Queue
- **Load Queue**: `GET /api/opd/queue`
  - Returns `OpdQueueResponse.entries[]` with `status`, `priority`, `token_number`, `interview_id`.
  - `EMERGENCY`/`URGENT` priorities render as a pulsing badge.
  - Filter chips re-filter the in-memory list.
  - On 401/403: dashboard error banner shown, no redirect.

### 4. Clinical Case Sheet
- **Dashboard**: `GET /api/interviews/{interview_id}/dashboard`
  - Response shape: `{ patient, interview, latest_summary, readiness, red_flags, medications, contradictions, emergency_escalations, patient_confirmation, doctor_review, abnormal_values }`
  - Safety alert banner: shown when `emergency_escalations.has_active_escalation` or active `red_flags` exist, or `confidence.verification_required` is true.
  - Medication discrepancy callout: shown when `medications.discrepancy_count > 0` or `contradictions.has_contradictions`.
  - Mandatory clinical disclaimer text sourced from `latest_summary.disclaimer`.

### 5. Doctor Review Lifecycle
1. **Start Review**: `POST /api/interviews/{id}/summary/{summary_id}/doctor-review/start`
   - Only allowed for users with `role == "DOCTOR"`.
   - Returns review session with individual `items[]` in `PENDING` state.
2. **Verify Items**: `POST /api/interviews/{id}/doctor-reviews/{review_id}/items/{item_id}/verify`
   - Iterates all `PENDING` items automatically on sign-off.
3. **Complete Review**: `POST /api/interviews/{id}/doctor-reviews/{review_id}/complete`
   - Sets review `status` to `COMPLETED`. Backend reloaded authoritatively.

### 6. Storage Purity & Security Invariants
- **Zero PHI in Storage**: No patient demographics, clinical notes, summaries, or case data cached in `sessionStorage`.
- **Token Security**: JWT stored only in `sessionStorage` via `MediKioskSession`. Never logged.
- **Role Gate**: `btnApproveCase` action requires `currentUser.role === "DOCTOR"`. Non-doctor users see an error banner; no partial state changes occur.
- **Zero Sensitive Logging**: Auth credentials, JWT, PHI, and clinical data are never logged to the browser console.

---

## Step 8: OPD Queue & Emergency Escalation Workflow

Step 8 integrates the OPD Queue transitions, summary metrics, and Emergency Escalation desk into the clinical dashboard workflow (`screen5-doctor-dashboard.html`) and connects token generation from the patient kiosk flow (`screen4-summary.html`).

### 1. Actual Backend Contracts Discovered

#### A. OPD Queue Endpoints (`/api/opd/queue`)
| Endpoint | Method | Roles Permitted | Purpose |
|---|---|---|---|
| `/api/opd/queue/entries` | `POST` | `PATIENT`, `STAFF`, `DOCTOR`, `ADMIN` | Create queue entry and assign token (`patient_id`, `interview_id`) |
| `/api/opd/queue` | `GET` | `STAFF`, `DOCTOR`, `ADMIN` | List active OPD queue entries ordered by priority & token |
| `/api/opd/queue/summary` | `GET` | `STAFF`, `DOCTOR`, `ADMIN` | Aggregate counts: waiting, called, in_service, emergency, etc. |
| `/api/opd/queue/next` | `POST` | `STAFF`, `DOCTOR`, `ADMIN` | Atomically call next waiting patient (advances to `CALLED`) |
| `/api/opd/queue/entries/{id}/start` | `POST` | `STAFF`, `DOCTOR`, `ADMIN` | Begin consultation (`CALLED` -> `IN_SERVICE`) |
| `/api/opd/queue/entries/{id}/complete` | `POST` | `STAFF`, `DOCTOR`, `ADMIN` | Finish consultation (`IN_SERVICE` -> `COMPLETED`) |
| `/api/opd/queue/entries/{id}/return-to-waiting` | `POST` | `STAFF`, `DOCTOR`, `ADMIN` | Return unserved called patient back to `WAITING` |
| `/api/opd/queue/entries/{id}/escalate` | `POST` | `STAFF`, `DOCTOR`, `ADMIN` | Priority escalation (`NORMAL` -> `EMERGENCY` / `URGENT`) |
| `/api/opd/queue/entries/{id}/cancel` | `POST` | `STAFF`, `DOCTOR`, `ADMIN` | Cancel entry (`CANCELLED`) |

#### B. Emergency Escalation Endpoints (`/api/emergency` & `/api/interviews`)
| Endpoint | Method | Roles Permitted | Purpose |
|---|---|---|---|
| `/api/emergency/active` | `GET` | `STAFF`, `DOCTOR`, `ADMIN` | List active emergency escalations across hospital intake |
| `/api/emergency/{id}/acknowledge` | `POST` | `STAFF`, `DOCTOR`, `ADMIN` | Acknowledge active escalation (`ACTIVE` -> `ACKNOWLEDGED`) |
| `/api/emergency/{id}/triage` | `POST` | `STAFF`, `DOCTOR`, `ADMIN` | Clinical triage action (`ACKNOWLEDGED` -> `TRIAGED`) |
| `/api/emergency/{id}/resolve` | `POST` | `STAFF`, `DOCTOR`, `ADMIN` | Resolve escalation (`TRIAGED` -> `RESOLVED`) |
| `/api/emergency/{id}/cancel` | `POST` | `STAFF`, `DOCTOR`, `ADMIN` | Cancel escalation alert (`CANCELLED`) |
| `/api/interviews/{id}/emergency/escalate` | `POST` | `STAFF`, `DOCTOR`, `ADMIN` | Direct clinical emergency trigger for an interview |
| `/api/interviews/{id}/red-flags/{rf_id}/acknowledge` | `POST` | `STAFF`, `DOCTOR`, `ADMIN` | Acknowledge specific AI-detected red flag |
| `/api/interviews/{id}/red-flags/{rf_id}/resolve` | `POST` | `STAFF`, `DOCTOR`, `ADMIN` | Resolve specific AI-detected red flag |

### 2. Request / Response Schemas

- **Queue Entry Allocation**:
  - Request (`POST /api/opd/queue/entries`): `{ patient_id: number, interview_id?: number }`
  - Response (`OpdQueueEntryResponse`): `{ id, token_number, patient_id, interview_id, priority, priority_reason, status, position, created_at, called_at, service_started_at, completed_at }`
- **Queue Summary**:
  - Response (`OpdQueueSummaryResponse`): `{ queue_date, total_entries, waiting, called, in_service, completed, cancelled, normal, urgent, emergency }`
- **Queue Escalation**:
  - Request (`POST /api/opd/queue/entries/{id}/escalate`): `{ target_priority: "URGENT" | "EMERGENCY", reason: string, notes?: string }`
- **Emergency Escalation Lifecycle**:
  - Acknowledge (`POST /api/emergency/{id}/acknowledge`): `{ staff_id: string, notes?: string }`
  - Triage (`POST /api/emergency/{id}/triage`): `{ staff_id: string, triage_notes?: string }`
  - Resolve (`POST /api/emergency/{id}/resolve`): `{ staff_id: string, resolution_reason: string }`
  - Cancel (`POST /api/emergency/{id}/cancel`): `{ staff_id: string, cancellation_reason: string }`

### 3. Role / Authorization Rules (RBAC)

- **`PATIENT`**:
  - Allowed: Creating own OPD queue entry at kiosk via `POST /api/opd/queue/entries`.
  - Forbidden (403): Accessing queue listing, calling next patient, changing queue states, viewing active emergency desk, or acknowledging/resolving escalations.
- **`STAFF`**:
  - Allowed: Full queue operations (call next, start service, complete service, return to waiting, priority escalate, cancel), view emergency desk, acknowledge/triage/resolve escalations.
- **`DOCTOR`**:
  - Allowed: All clinical queue and emergency operations, doctor intake review completion, case sign-off.
- **`ADMIN`**: Full administrative access.

### 4. Lifecycle State Machines

#### A. OPD Queue Token Lifecycle
```
[Token Allocated] -> WAITING
                      |
           (POST /next or /call)
                      v
                    CALLED <---------\
                   /      \          | (POST /return-to-waiting)
(POST /start)     /        \         |
                 v          \--------/
             IN_SERVICE
                 |
(POST /complete) |
                 v
             COMPLETED
```
*(Any non-completed state can transition to `CANCELLED` via `POST /cancel`)*

#### B. Emergency Escalation Lifecycle
```
[Triggered / Active] -> ACTIVE
                          |
             (POST /acknowledge)
                          v
                    ACKNOWLEDGED
                          |
                  (POST /triage)
                          v
                       TRIAGED
                          |
                 (POST /resolve)
                          v
                       RESOLVED
```
*(Any active/acknowledged/triaged escalation can be cancelled via `POST /cancel`)*

### 5. Frontend Implementation Details (`screen5-doctor-dashboard.html`)
- **Queue Summary Bar**: Displays dynamic operational counts for Waiting, Called, In Service, and Emergency/Urgent cases.
- **Queue Action Bar**:
  - `btnCallNext`: Calls the next patient in priority order.
  - Contextual buttons per selected entry: `Start Consult`, `Complete Consult`, `Return to Waiting`, `Priority Escalate`, `Cancel Entry`.
- **Filter Chips**: Allows instant filtering by `All`, `Emergency / Urgent`, `Waiting`, and `In Service`.
- **Emergency Escalation Desk**:
  - Displays hospital-wide active emergencies above the clinical sheet.
  - Interactive buttons for staff/clinicians to Acknowledge, Triage, Resolve, or Cancel.
- **Safety Banner Red-Flag Actions**:
  - Clinicians can acknowledge or resolve specific interview red flags directly from the case sheet header.
  - Manual button to trigger clinical emergency escalation.
- **Authoritative Reload**:
  - The UI reloads authoritative state via `MediKioskApi` after every queue transition or escalation action.
  - Hardcoded or mock state is never used as authority.

### 6. Test Suite & Local Verification
- **Test File**: `frontend/tests/test_step8_queue_emergency.js`
- **Step 8 Tests**: 26 tests (all 26 passing)
- **Full Regression Suite (Steps 1–8)**: 164 tests (all 164 passing)
- **Storage Purity**: Verified zero PHI, queue tokens, red flags, or clinical payloads in `sessionStorage`/`localStorage`.
- **Security**: Verified zero bearer tokens, passwords, or patient health information printed to console.

---

## Step 9: ABHA & Interoperability Workflows (FHIR R4 & HIS Integration)

### 1. Backend Endpoint Contracts Discovered & Verified

#### A. ABHA / ABDM Patient Integration
| Endpoint | Method | Roles Permitted | Purpose |
|---|---|---|---|
| `/api/patients/{patient_id}/abha` | `GET` | `PATIENT`, `STAFF`, `DOCTOR`, `ADMIN` | Retrieve ABHA profile, ABHA address, verification status, and linkage state |

- **Request Schema**: Path parameter `patient_id` (numeric string or int).
- **Response Schema (`AbhaProfileResponse`)**:
  ```json
  {
    "patient_id": "pt-101",
    "abha_number": "14-1234-5678-9012",
    "abha_address": "rahul.sharma@abdm",
    "status": "ACTIVE",
    "linked": true,
    "verification_status": "VERIFIED",
    "environment": "MOCK",
    "linked_at": "2026-09-14T10:00:00Z",
    "raw_profile": {
      "first_name": "Rahul",
      "last_name": "Sharma",
      "gender": "M",
      "year_of_birth": 1985
    }
  }
  ```
- **Optionality & Non-Blocking Intake**:
  - ABHA registration is strictly optional.
  - Patients can register and complete interviews anonymously or with local OPD slips without ABHA.
  - No Aadhaar, OTP, demographic auth tokens, or ABDM secrets are stored in browser storage.

#### B. FHIR R4 Export & HIS Transmission
| Endpoint | Method | Roles Permitted | Purpose |
|---|---|---|---|
| `/api/interviews/{interview_id}/fhir/preview` | `GET` | `DOCTOR`, `STAFF`, `ADMIN` | Preview standardized FHIR R4 Bundle before hospital EMR transmission |
| `/api/interviews/{interview_id}/fhir/export` | `POST` | `DOCTOR`, `STAFF`, `ADMIN` | Transmit standardized FHIR R4 bundle to external Hospital Information System |
| `/api/interviews/{interview_id}/fhir/exports` | `GET` | `DOCTOR`, `STAFF`, `ADMIN` | Audit log of past FHIR export transmissions for encounter |

- **FHIR Preview Response**:
  ```json
  {
    "interview_id": "int-101",
    "bundle": {
      "resourceType": "Bundle",
      "id": "bundle-int-101",
      "type": "document",
      "timestamp": "2026-09-14T11:00:00Z",
      "entry": [
        { "resource": { "resourceType": "Composition", "id": "comp-1", "status": "final", "title": "OPD Clinical Intake Summary" } },
        { "resource": { "resourceType": "Patient", "id": "patient-1", "name": [{ "text": "Rahul Sharma" }] } },
        { "resource": { "resourceType": "Encounter", "id": "enc-1", "status": "finished" } },
        { "resource": { "resourceType": "Observation", "id": "obs-1", "code": { "text": "Systolic Blood Pressure" }, "valueQuantity": { "value": 130, "unit": "mmHg" } } }
      ]
    },
    "summary_version": 1,
    "is_valid": true
  }
  ```
- **FHIR Export Request Body (`FhirExportRequest`)**:
  ```json
  {
    "destination_system": "HOSPITAL_EMR",
    "transmission_notes": "Routine OPD consultation intake transmission"
  }
  ```
- **FHIR Export Response (`FhirExportResponse`)**:
  ```json
  {
    "export_id": "exp-001",
    "interview_id": "int-101",
    "destination_system": "HOSPITAL_EMR",
    "transmission_status": "TRANSMITTED",
    "external_reference": "HIS-REF-98765",
    "exported_at": "2026-09-14T11:05:00Z",
    "retry_count": 1
  }
  ```

### 2. Clinical Safety Gates & Prerequisites

1. **Consent Prerequisite (`DATA_SHARING`)**:
   - The backend enforces mandatory patient consent (`DATA_SHARING`) before any external transmission.
   - If consent is missing, `POST /api/interviews/{id}/fhir/export` returns `403 Forbidden` with detail: `"Patient has not granted mandatory DATA_SHARING consent for external EHR transmission."`
   - Patient consent granted on `screen4-summary.html` or `screen1b-consent.html` is required.
2. **Review Prerequisite (Clinician Sign-off)**:
   - Clinical summaries must be verified and signed off by an authorized clinician before transmission.
   - If the summary is unverified, the backend returns `400 Bad Request` with detail: `"Interview summary must be clinician-verified before FHIR export."`
3. **Gateway Error & Retry Handling**:
   - If the external HIS/EMR gateway is unreachable or returns a server error, the backend responds with `502 Bad Gateway`.
   - The system tracks `retry_count` and maintains an audit log in `GET /api/interviews/{id}/fhir/exports`.

### 3. Role-Based Access Control (RBAC)
- **`PATIENT`**:
  - Allowed: View own ABHA status (`GET /api/patients/{id}/abha`).
  - Blocked (`403 Forbidden`): FHIR Bundle preview (`GET .../fhir/preview`) and HIS export (`POST .../fhir/export`).
- **`DOCTOR`**:
  - Full access to review, verify, preview FHIR bundles, and trigger HIS transmissions.
- **`STAFF`**:
  - Permitted to view ABHA status, preview FHIR bundles, and trigger transmissions.
- **`ADMIN`**:
  - Unrestricted access across all endpoints.

### 4. Storage Purity & Console Security
- **Storage Purity**:
  - Zero FHIR bundles or observation payloads stored in `sessionStorage` or `localStorage`.
  - Zero ABHA OTPs, Aadhaar numbers, or demographic secrets stored in client storage.
  - Allowed storage keys strictly limited to session identifiers (`auth_token`, `patient_id`, `interview_id`, `session_id`).
- **Console Security**:
  - Zero auth tokens, doctor credentials, or patient PHI logged to browser console.

### 5. Frontend Implementation Details (`screen5-doctor-dashboard.html`)
- **Patient Header ABHA Badge**:
  - `activeAbhaBadge`: Dynamically fetches and renders ABHA linkage status (`ABHA: 14-XXXX-XXXX-9012 (Verified)` or `No ABHA Linked (Optional)`).
- **FHIR Preview Modal**:
  - `btnPreviewFhir`: Calls `GET /api/interviews/{id}/fhir/preview` and opens structured modal displaying JSON/Composition preview.
- **HIS Export Action**:
  - `btnExportHis`: Calls `POST /api/interviews/{id}/fhir/export`, showing a loading state, handling prerequisite validation errors (400/403/502), and rendering a success banner.
- **Export Status & Audit History**:
  - `hisExportStatusDisplay`: Displays active transmission status (`TRANSMITTED` / `FAILED` / `PENDING`) with external HIS reference code.
  - `fhirExportsList`: Renders history of previous export attempts with timestamps, destination, and retry counts.

### 6. Test Suite & Local Verification
- **Test File**: `frontend/tests/test_step9_interop_abha.js`
- **Step 9 Tests**: 26 tests (all 26 passing)
- **Full Regression Suite (Steps 1–9)**: 190 tests (all 190 passing across all suites)



