# MediKiosk Frontend ↔ Backend Integration Audit Report

**Date**: 2026-09-14  
**Scope**: Complete Static Frontend Inspection & Backend API Alignment Audit (Step 25 Baseline)  
**Target Environment**: Plain HTML + CSS (Tailwind Tokens), Vanilla JavaScript (No React/Vite conversion)  
**Status**: INSPECTION ONLY — Zero Code Modifications Applied to Frontend or Backend

---

## 1. Executive Summary

A comprehensive architectural and code-level audit was conducted across the entire `frontend/` directory (14 HTML screens and 1 CSS design token file) and the completed MediKiosk `backend/` (18 FastAPI routers, 161 API operations, and Step 25 hardened database/security services).

### Key Architectural Findings:
1. **No Existing API Integration Layer**: The frontend currently contains **ZERO** `fetch()`, `XMLHttpRequest`, or `axios` network requests, **ZERO** standalone `.js` runtime script files, and **ZERO** API endpoint references. All interaction logic is embedded as inline `<script>` tags executing DOM class toggles, client-side timers (`setTimeout`), and localized text swaps.
2. **Missing Form & Upload Primitives**: There is **not a single `<form>` element** across all 14 screens, nor is there any `<input type="file">` control in `screen3-documents.html`. Document scanning and OCR extractions are purely animated CSS/timer simulations.
3. **Simulated Audio Controls**: The voice microphone buttons and sound bars are animated CSS visual demonstrations; no `MediaRecorder` or Web Audio API code exists to record or stream patient audio.
4. **Complete Absence of Authentication**: The clinician portal (`screen5-doctor-dashboard.html`) is completely unprotected. There is no login UI, no JWT storage, and no RBAC validation, whereas the backend strictly enforces JWT Bearer tokens with `DOCTOR`, `STAFF`, and `ADMIN` role checks.
5. **Statutory Consent Disconnect**: The frontend collects a single holistic consent statement, whereas the backend strictly fail-closes across a 6-purpose statutory consent matrix (`CLINICAL_HISTORY`, `DOCUMENT_PROCESSING`, `AI_SUMMARIZATION`, `BILINGUAL_OUTPUT`, `DATA_SHARING`, `ABHA_LINKAGE`).

---

## 2. Frontend Structure & Screen Inventory

### File Structure:
```
frontend/
├── backend_integration_audit.md        <-- This audit report
└── src/
    ├── screens/
    │   ├── home.html                   (Welcome & language selector)
    │   ├── index.html                  (Auto-redirect to home.html)
    │   ├── qa-launcher.html            (Developer & QA test navigation hub)
    │   ├── screen1a-identity.html      (Identity intake mode: scan/manual/new)
    │   ├── screen1a-manual-entry.html  (On-screen keypad for mobile/ABHA + OTP mock)
    │   ├── screen1b-consent.html       (DPDP care consent statement & decline modal)
    │   ├── screen2-ai-states.html      (Interactive AI state machine demo)
    │   ├── screen2-interview.html      (Step 1 -> Step 2 transition interstitial)
    │   ├── screen2-red-flag.html       (Urgent clinical red-flag triage alert)
    │   ├── screen2a-standard.html      (SOCRATES chest pain interview & voice card)
    │   ├── screen2b-ayush.html         (AYUSH Dashavidha Pariksha / Agni interview)
    │   ├── screen3-documents.html      (Document scanning simulation & timeline)
    │   ├── screen4-summary.html        (4-point summary review & Token A-24 generation)
    │   └── screen5-doctor-dashboard.html (Doctor OPD queue & clinical case file review)
    └── styles/
        ├── tailwind.config.js          (Theme color & typography definitions)
        └── tokens.css                  (CSS custom properties, typography, buttons, clay cards)
```

- **HTML Screens**: 14
- **CSS Files**: 1 (`styles/tokens.css`)
- **JavaScript Runtime Files**: 0 (only `styles/tailwind.config.js` for build config)
- **Forms**: 0
- **File Upload Inputs**: 0
- **Audio Capture Code**: 0

---

## 3. JavaScript & Network Audit

| Parameter | Current Status | Details |
| :--- | :--- | :--- |
| **Standalone JS Files** | None | All scripts are inline `<script>` tags within HTML documents |
| **API Calls (`fetch`/`XHR`)** | None | 0 network requests executed |
| **Hardcoded Backend URLs** | None | No `http://localhost:8000` or `/api/` paths referenced |
| **Storage Usage** | `localStorage` only | Used strictly for `medikiosk_lang` ('en', 'hi', 'mr') |
| **Authentication/JWT** | None | No JWT parsing, storage, or `Authorization` header generation |
| **Simulated Delays** | Active | `setTimeout` used in identity scan (1.5s), OCR (1.4s), and toast (4s) |

---

## 4. Frontend → Backend API Mapping Matrix

| Screen File | User Action / Trigger | Data Captured | Target Backend Endpoint | Current Status |
| :--- | :--- | :--- | :--- | :--- |
| **`home.html`** | Language selection chip | `lang` ('en', 'hi', 'mr') | `GET /api/languages` | NOT INTEGRATED |
| **`home.html`** | "Begin" button (`#btnBegin`) | None (Kiosk start) | `POST /api/sessions` | NOT INTEGRATED |
| **`screen1a-identity.html`** | QR scan simulation | Mock ABHA ID | `GET /api/patients/{id}/abha` or `POST /api/patients` | NOT INTEGRATED |
| **`screen1a-identity.html`** | "Staff Help" button | Kiosk assistance alert | `POST /api/emergency/escalate` | NOT INTEGRATED |
| **`screen1a-manual-entry.html`** | Numeric touch keypad | 10-digit phone / 14-digit ABHA | `POST /api/patients` | NOT INTEGRATED |
| **`screen1a-manual-entry.html`** | OTP confirm button | 4-digit OTP (mock) | *No backend OTP endpoint (direct registration)* | NOT INTEGRATED |
| **`screen1b-consent.html`** | "I Agree & Continue" button | Blanket care consent | `POST /api/patients/{id}/consents` (6 purposes) | NOT INTEGRATED |
| **`screen1b-consent.html`** | "Ask Staff for Help" button | Consent declined / assist | `POST /api/sessions/{id}/cancel` | NOT INTEGRATED |
| **`screen2-interview.html`** | "Start Interview" button | None (Interview init) | `POST /api/interviews` & `POST /api/sessions/{id}/attach-interview` | NOT INTEGRATED |
| **`screen2a-standard.html`** | Select SOCRATES chest pain option | Option value ("pressure", "sharp", etc.) | `POST /api/interviews/{id}/messages` | NOT INTEGRATED |
| **`screen2a-standard.html`** | Mic button voice answer | Voice audio stream | `POST /api/interviews/{id}/messages/audio` | NOT INTEGRATED |
| **`screen2a-standard.html`** | "Next Question" button | Navigation | `GET /api/interviews/{id}/next-question` | NOT INTEGRATED |
| **`screen2b-ayush.html`** | Select Agni digestion option | Agni type ("manda", "tikshna", etc.) | `PUT /api/interviews/{id}/clinical-data/{field_key}` | NOT INTEGRATED |
| **`screen2-red-flag.html`** | "Immediate Attendant" / "Wheelchair" | Emergency trigger | `POST /api/interviews/{id}/emergency/escalate` | NOT INTEGRATED |
| **`screen2-red-flag.html`** | "Staff Attended • Proceed" | Emergency resolution | `POST /api/emergency/{id}/resolve` | NOT INTEGRATED |
| **`screen3-documents.html`** | "Upload from Device" / "Scan Camera" | File bytes (PDF/PNG/JPG) | `POST /api/interviews/{id}/documents` | NOT INTEGRATED |
| **`screen3-documents.html`** | Trigger OCR processing | Document ID | `POST /api/interviews/{id}/documents/{id}/process` | NOT INTEGRATED |
| **`screen3-documents.html`** | Past Records Timeline | Display past history | `GET /api/interviews/{id}/timeline` | NOT INTEGRATED |
| **`screen3-documents.html`** | Lab Abnormal Flag | Highlight elevated labs | `GET /api/interviews/{id}/abnormal-values` | NOT INTEGRATED |
| **`screen4-summary.html`** | Review Summary | Display parsed complaints | `GET /api/interviews/{id}/bilingual-summary` | NOT INTEGRATED |
| **`screen4-summary.html`** | "Something's wrong" overlay | Correction intent | `POST /api/interviews/{id}/confirmations/{id}/items/{item_id}/flag` | NOT INTEGRATED |
| **`screen4-summary.html`** | "Yes, this is correct" button | Patient confirmation | `POST /api/interviews/{id}/confirmations` & `POST /api/interviews/{id}/complete` | NOT INTEGRATED |
| **`screen4-summary.html`** | Token card generation | Request OPD Queue token | `POST /api/opd/queue/entries` | NOT INTEGRATED |
| **`screen5-doctor-dashboard.html`** | OPD Queue list display | Department queue | `GET /api/opd/queue` | NOT INTEGRATED |
| **`screen5-doctor-dashboard.html`** | "Call Next Patient" | Desk claim | `POST /api/opd/queue/next` | NOT INTEGRATED |
| **`screen5-doctor-dashboard.html`** | View active patient case sheet | Patient encounter data | `GET /api/interviews/{id}/dashboard` | NOT INTEGRATED |
| **`screen5-doctor-dashboard.html`** | "Resolve Conflict" button | Medication dosage fix | `POST /api/contradictions/{id}/verify` or `PUT /api/interviews/{id}/medications/{id}/verify` | NOT INTEGRATED |
| **`screen5-doctor-dashboard.html`** | "Verify & Approve Intake File" | Doctor clinical verification | `POST /api/interviews/{id}/doctor-reviews/{id}/complete` | NOT INTEGRATED |
| **`screen5-doctor-dashboard.html`** | Digital Record Transmission | Hospital HIS / ABDM push | `POST /api/interviews/{id}/fhir/export` | NOT INTEGRATED |

---

## 5. Architectural & Schema Mismatches

### CRITICAL MISMATCHES:
1. **Missing Authentication & Authorization Layer (CRITICAL)**:
   - **Backend**: Strict RBAC requiring `Authorization: Bearer <jwt_token>`. Endpoints for queue management, dashboard access, doctor reviews, and analytics return `HTTP 401 Unauthorized` or `HTTP 403 Forbidden` if unauthenticated.
   - **Frontend**: Zero login screens, zero password/credential inputs, zero token storage. `screen5-doctor-dashboard.html` renders directly as an unauthenticated static file.
2. **Missing Document File Input Elements (CRITICAL)**:
   - **Backend**: `POST /api/interviews/{id}/documents` expects `multipart/form-data` with `file: UploadFile` and `document_type: str`.
   - **Frontend**: `screen3-documents.html` has **no `<input type="file">`**. Clicking the upload card only triggers an internal JavaScript timer that unhides hardcoded static HTML text.
3. **Missing Audio Capture Pipeline (CRITICAL)**:
   - **Backend**: `POST /api/interviews/{id}/messages/audio` expects an audio file upload (`.wav`, `.webm`, `.mp3`) for transcription via Sarvam/Whisper ASR.
   - **Frontend**: The microphone buttons toggle CSS keyframe animations for waveform bars. There is no `navigator.mediaDevices.getUserMedia()` or `MediaRecorder` implementation.
4. **Consent Purpose Matrix Discrepancy (CRITICAL)**:
   - **Backend**: Enforces 6 discrete statutory purposes (`CLINICAL_HISTORY`, `DOCUMENT_PROCESSING`, `AI_SUMMARIZATION`, `BILINGUAL_OUTPUT`, `DATA_SHARING`, `ABHA_LINKAGE`). Operations fail-close with `403 Forbidden (CONSENT_REQUIRED)` if the specific purpose is not granted.
   - **Frontend**: `screen1b-consent.html` displays a single blanket paragraph with one button ("I Agree & Continue"), missing the 6 discrete consent records.
5. **No Cross-Page State Persistence (CRITICAL)**:
   - **Backend**: Every operation is scoped by IDs (`patient_id`, `interview_id`, `session_id`).
   - **Frontend**: Multi-page HTML layout navigates via `window.location.href`. Navigating between screens resets in-memory JavaScript variables. Without saving active session IDs in `sessionStorage` or URL parameters, downstream screens cannot associate requests with an active patient or encounter.

### HIGH MISMATCHES:
1. **Static vs. Dynamic AI Interview Flow (HIGH)**:
   - **Backend**: Supports dynamic conversational triage with adaptive follow-ups via `GET /api/interviews/{id}/next-question` and `POST /api/interviews/{id}/messages`.
   - **Frontend**: Screens `screen2a-standard.html` and `screen2b-ayush.html` have hardcoded static questions (chest pain and Agni) with fixed navigation.
2. **OPD Queue Token Generation (HIGH)**:
   - **Backend**: `POST /api/opd/queue/entries` atomically generates sequential daily integers (`1, 2, 3...`) with row-level locks and priority scheduling.
   - **Frontend**: `screen4-summary.html` displays a static string `"A-24"`.
3. **Emergency Escalation Hook (HIGH)**:
   - **Backend**: Has an active emergency incident table with status lifecycle (`PENDING` -> `ACKNOWLEDGED` -> `RESOLVED`), reason, and desk notification.
   - **Frontend**: `screen2-red-flag.html` triggers browser `alert()` popups.

### MEDIUM MISMATCHES:
1. **Language Preference Synchronization (MEDIUM)**:
   - Frontend sets `localStorage.getItem('medikiosk_lang')`, but never issues `PUT /api/interviews/{id}/language` to update the backend interview record.
2. **Contradiction Resolution Action (MEDIUM)**:
   - Frontend replaces DOM text on click; backend requires `POST /api/contradictions/{id}/verify` or medication verification endpoints.

---

## 6. Missing Frontend Functionality & Unmapped Screens

### Backend Features Missing Frontend UI:
1. **Doctor / Staff Login Screen**: No interface exists to input email/password or receive JWT.
2. **Operational Analytics Portal**: No screens exist for `/api/analytics/overview`, `/api/analytics/funnel`, `/api/analytics/throughput`, or `/api/analytics/red-flags`.
3. **Emergency Nursing Station Console**: No UI exists for nurses to view `GET /api/emergency/active`, acknowledge incidents, or dispatch staff.
4. **Adaptive Accessibility Settings**: No UI exists to view or update patient accessibility preferences (`/api/patients/{id}/accessibility`).
5. **FHIR / ABDM Export Controls**: No UI button exists on the doctor screen to trigger or download `POST /api/interviews/{id}/fhir/export`.

### Frontend Controls with NO Backend Mapping:
1. **Simulated OTP Keypad**: `screen1a-manual-entry.html` includes a 4-digit OTP entry screen. The backend registers patients directly via phone number without an SMS gateway.
2. **Stat ECG Order Button**: `screen5-doctor-dashboard.html` has an "Order Stat ECG" button, which falls under hospital ordering systems (CPOE) rather than intake check-in.

---

## 7. Local Development Configuration

- **Frontend Hosting**: Plain static HTML + CSS. Can be served using any local static file server:
  - Python: `python3 -m http.server 3000 --directory frontend/src`
  - Node: `npx serve frontend/src -p 3000`
- **Backend Service**: FastAPI running on `http://127.0.0.1:8000`.
- **CORS Configuration**: `backend/app/main.py` already includes `http://localhost:3000` in `cors_origins` with `allow_credentials=True`.
- **Navigation Scheme**: Multi-page relative linking (`href="screen1a-identity.html"`, `href="../styles/tokens.css"`).

---

## 8. Recommended Phased Integration Roadmap

To maintain data integrity and follow the actual clinical patient journey, frontend-backend integration should proceed in 16 discrete phases:

1. **Phase 1: Kiosk State Management & API Helper Layer**
   - Create a shared `api.js` client utility managing base URL, request headers, error handling, and `sessionStorage` (storing `active_patient_id`, `active_interview_id`, `active_session_id`, `auth_token`).
2. **Phase 2: Authentication & Doctor Login**
   - Add a lightweight clinician login modal/page to authenticate doctors and store JWT tokens before loading `screen5-doctor-dashboard.html`.
3. **Phase 3: Patient Intake & Registration (`home.html` & `screen1a-*.html`)**
   - Connect manual keypad / scan buttons to `POST /api/patients` and initialize encounter `POST /api/sessions`.
4. **Phase 4: Multi-Purpose Consent Granting (`screen1b-consent.html`)**
   - Submit the 6 statutory consent records via `POST /api/patients/{id}/consents`.
5. **Phase 5: Encounter & Interview Initialization (`screen2-interview.html`)**
   - Call `POST /api/interviews` and link via `POST /api/sessions/{id}/attach-interview`.
6. **Phase 6: Clinical Interview Flow (`screen2a-standard.html`)**
   - Post answers to `POST /api/interviews/{id}/messages` and fetch dynamic next questions via `GET /api/interviews/{id}/next-question`.
7. **Phase 7: AYUSH Clinical Intake (`screen2b-ayush.html`)**
   - Post Ayurvedic constitution and digestion answers to `PUT /api/interviews/{id}/clinical-data/{field_key}`.
8. **Phase 8: Audio / Voice Turn Capture (Mic Controls)**
   - Add browser `MediaRecorder` in vanilla JS to capture microphone input and upload audio to `POST /api/interviews/{id}/messages/audio`.
9. **Phase 9: Emergency Escalation Integration (`screen2-red-flag.html`)**
   - Wire emergency buttons to `POST /api/interviews/{id}/emergency/escalate`.
10. **Phase 10: Document File Ingestion & OCR (`screen3-documents.html`)**
    - Add real `<input type="file">` controls, submit `FormData` to `POST /api/interviews/{id}/documents`, and trigger OCR via `POST /api/interviews/{id}/documents/{id}/process`.
11. **Phase 11: Clinical Timeline & Abnormal Value Rendering (`screen3-documents.html`)**
    - Populate timeline cards dynamically from `GET /api/interviews/{id}/timeline` and flags from `GET /api/interviews/{id}/abnormal-values`.
12. **Phase 12: Case Summary Generation & Bilingual Display (`screen4-summary.html`)**
    - Render summary from `GET /api/interviews/{id}/bilingual-summary`.
13. **Phase 13: Patient Confirmation & Correction Flow (`screen4-summary.html`)**
    - Submit confirmation via `POST /api/interviews/{id}/confirmations` and complete interview via `POST /api/interviews/{id}/complete`.
14. **Phase 14: Atomic OPD Queue Token Allocation (`screen4-summary.html`)**
    - Call `POST /api/opd/queue/entries` to generate and display the true sequential queue token.
15. **Phase 15: Doctor Dashboard Queue & Clinical Review (`screen5-doctor-dashboard.html`)**
    - Fetch active queue (`GET /api/opd/queue`), call next patient (`POST /api/opd/queue/next`), fetch case sheet (`GET /api/interviews/{id}/dashboard`), resolve contradictions (`POST /api/contradictions/{id}/verify`), and complete review (`POST /api/interviews/{id}/doctor-reviews/{id}/complete`).
16. **Phase 16: FHIR Export & Operational Analytics**
    - Trigger `POST /api/interviews/{id}/fhir/export` on verified case files and provide an administrative analytics view.
