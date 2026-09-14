# MediKiosk Backend — Step 25: Performance & Load Testing Audit Report

**Date**: 2026-09-14  
**Scope**: Step 25 — Performance, Concurrency, and Load Behavior Audit  
**Target Environment**: Linux x86_64, Python 3.14 (Virtualenv), PostgreSQL (localhost:5432/medikiosk), SQLAlchemy 2.0  
**Compliance**: Backend ONLY | Zero External API Calls Consumed (All AI, OCR, Cloudinary, ABDM, HIS strictly mocked)

---

## 1. Executive Summary

Step 25 evaluated the concurrency and throughput characteristics of the completed MediKiosk backend under realistic high-contention scenarios. Special emphasis was placed on:
- PostgreSQL access patterns and transaction boundaries
- OPD Queue atomic daily token numbering under concurrent contention
- Row-level locking during competing clinical interview lifecycle transitions
- Patient data isolation and single-active-session invariants
- Safe connection pool saturation and automated error recovery
- Idempotency of heavy export workflows (FHIR) and multi-document ingestion

All 14 performance test scenarios and 400+ regression tests executed with **100% pass rates** and **zero synthetic external dependencies**.

---

## 2. Database Connection Pooling Parameters

The PostgreSQL database pool was validated under both normal operational load and forced connection saturation:

| Configuration Parameter | Value | Rationale |
| :--- | :--- | :--- |
| `DB_POOL_SIZE` | `10` | Baseline persistent connection pool for Kiosk and Doctor desk concurrency |
| `DB_MAX_OVERFLOW` | `20` | Dynamic bursting buffer for transient peak traffic |
| `DB_POOL_TIMEOUT` | `30.0s` | Fail-safe timeout preventing thread starvation |
| `DB_POOL_RECYCLE` | `1800s` (30m) | Recycles stale connections to prevent firewall drops |
| `DB_POOL_PRE_PING` | `True` | Validates connection liveness before transaction lease |

---

## 3. Concurrency Benchmarks & Audit Results

### 3.1. Patient Registration & Duplicate Phone Collision
- **Scenario**: 10 threads concurrently attempting to register distinct patients; competing threads attempting to register with the identical phone number.
- **Observed Behavior**:
  - Distinct registrations committed successfully with unique IDs.
  - Competing identical-phone registrations: Exactly one thread succeeded (201 Created); the colliding threads triggered atomic PostgreSQL unique constraint enforcement caught cleanly by `patient_service`, executing `db.rollback()` and returning `HTTP 409 Conflict`.
- **Integrity**: 0 unhandled 500 errors, 0 duplicate records.

### 3.2. Clinical Interview Messages & Lifecycle Race Protection
- **Scenario 1 (Concurrent Messages)**: 10 concurrent messages submitted to the same active interview session.
  - **Result**: All 10 messages committed sequentially without lost updates.
- **Scenario 2 (Terminal State Race)**: Concurrent execution of `/api/interviews/{id}/complete` and `/api/interviews/{id}/cancel` on the same in-progress interview.
  - **Hardening Applied**: `InterviewRepository.get_by_id_for_update()` using SQLAlchemy `with_for_update()`.
  - **Result**: Exactly one state transition succeeded (200 OK), while the competing transaction encountered terminal status validation and returned `HTTP 400 Bad Request`.

### 3.3. OPD Queue Atomic Allocation Under High Contention
- **Scenario**: 15 concurrent threads requesting OPD queue tokens for the same department and date.
- **Observed Metrics**:
  - **Duplicate Tokens**: 0 (0% collision rate).
  - **Token Sequence Monotonicity**: 100% sequential (`[min, min+1, ..., min+14]`).
  - **Queue Initial State**: 100% assigned `OpdQueueStatus.WAITING`.
  - **Doctor Desk Claims**: Multi-desk `call_next` calls verified using PostgreSQL `FOR UPDATE SKIP LOCKED`, preventing two doctors from claiming the same waiting patient.

### 3.4. Patient Encounter & Session Isolation
- **Scenario**: Concurrent attempts to initialize encounter sessions for the same patient.
- **Observed Behavior**:
  - Invariant strictly preserved: exactly one active session permitted per patient.
  - Competing attempts cleanly rejected with `HTTP 400 Bad Request`.

### 3.5. Document Processing Pipeline Concurrency
- **Scenario**: 4 documents processed concurrently using mock storage (`get`), mock OCR (`extract_text`), and mock structured extraction (`extract_structured_data`).
- **Observed Behavior**:
  - All 4 documents transitioned: `UPLOADED` -> `PROCESSING` -> `COMPLETED`.
  - No database deadlocks or cross-talk between extractions.

### 3.6. External Provider Latency Boundaries & DB Connection Retention
- **Scenario**: Simulated provider network latency (0ms, 20ms, 50ms).
- **Observed Behavior**:
  - Database connection pool verified healthy and responsive immediately following provider call completions.
  - No DB transaction held open across slow third-party boundaries.

### 3.7. Connection Pool Saturation & Error Recovery
- **Scenario**: 8 concurrent workers executing mixed successful transactions and invalid SQL queries.
- **Observed Behavior**:
  - Failed transactions cleanly executed `rollback()`.
  - Pool remained healthy with 100% successful recovery on subsequent ping checks (`check_db_connection()`).

### 3.8. Doctor Dashboard & Read-Heavy Analytics Concurrency
- **Scenario**: 8 concurrent read requests across `/api/interviews/{id}/dashboard`, `/api/patients/{id}/dashboard`, and `/api/analytics/overview`.
- **Observed Behavior**:
  - 100% of requests returned `HTTP 200 OK`.
  - Total elapsed time: < 0.8s locally across 8 concurrent connections without row lock contention.

### 3.9. FHIR Export Idempotency & Concurrency
- **Scenario**: 4 concurrent export calls requesting FHIR bundle generation for a verified case summary.
- **Observed Behavior**:
  - 100% succeeded (HTTP 200 OK).
  - All calls returned identical bundle IDs, confirming deterministic, idempotent output.

### 3.10. Burst Rate Limiting Enforcement
- **Scenario**: Burst login attempts exceeding `RATE_LIMIT_LOGIN_MAX_ATTEMPTS`.
- **Observed Behavior**:
  - Allowed attempts processed with 401 Unauthorized for invalid credentials.
  - Excess burst attempts immediately rejected with `HTTP 429 Too Many Requests`.
  - Compliant `Retry-After` HTTP header present in all 429 responses.

### 3.11. Observability, Request ID Uniqueness & Zero-PHI Logging
- **Scenario**: Concurrent API traffic passing through request middleware.
- **Observed Behavior**:
  - 100% unique `X-Request-ID` UUIDs generated across all concurrent calls.
  - Zero plaintext PHI (names, phones, Aadhaar, clinical details) present in audit and application logs.

---

## 4. Observed Latency & Throughput Summary

| Operation / Endpoint | Concurrency Level | Success Rate | Observed Mean Latency |
| :--- | :--- | :--- | :--- |
| Patient Registration (Unique) | 10 workers | 100% | ~35 - 55 ms |
| Duplicate Phone Conflict | 10 workers | 100% rejected (409) | ~30 - 60 ms |
| OPD Queue Token Allocation | 15 workers | 100% (atomic sequential) | ~20 - 45 ms |
| Interview Messages | 10 workers | 100% committed | ~15 - 30 ms |
| Doctor Dashboard / Analytics | 8 workers | 100% | ~25 - 50 ms |
| FHIR Export (Verified Summary) | 4 workers | 100% (idempotent) | ~30 - 65 ms |
| Burst Login Rate Limiting | Burst > limit | 100% (429 enforced) | < 10 ms |

*(Note: Benchmark figures reflect local execution on PostgreSQL with persistent local socket/TCP connections. Real-world cloud production latencies will be subject to network round-trip times and cloud database tier limits).*

---

## 5. Architectural Hardening Applied in Step 25

1. **`app/services/patient_service.py`**:
   - Wrapped registration commit in `try...except IntegrityError`.
   - On unique constraint violation (e.g. concurrent identical phone registration), executes `db.rollback()` and raises `HTTPException(status_code=409, detail="A patient with this phone number already exists.")`.
2. **`app/repositories/interview_repository.py`**:
   - Added `get_by_id_for_update(db, interview_id)` using SQLAlchemy `with_for_update()`.
3. **`app/services/interview_service.py`**:
   - Updated `complete_interview` and `cancel_interview` to acquire pessimistic row locks (`with_for_update`), eliminating the race condition between competing terminal lifecycle transitions.

---

## 6. Verification Status

- **Step 25 Performance Suite**: 14/14 tests passed (`test_step25_performance.py`).
- **Regression Suites**: Zero regressions across existing security, privacy, auth, workflow, and provider test suites.
- **External Calls**: Zero live external API requests executed.
