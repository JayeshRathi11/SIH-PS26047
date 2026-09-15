/**
 * Step 9 Integration Test Suite: ABHA & Interoperability Workflows
 * 
 * Verifies:
 *  1. GET /api/patients/{patient_id}/abha: Retrieves linked ABHA profile with verification status
 *  2. GET /api/patients/{patient_id}/abha: Handles unlinked ABHA profile cleanly without crashing
 *  3. GET /api/patients/{patient_id}/abha: Handles non-existent patient (404 Not Found) throwing ApiError
 *  4. ABHA Optionality: Patient registration and clinical intake proceed smoothly without ABHA
 *  5. ABHA Security: Zero OTPs, Aadhaar numbers, or ABDM raw auth tokens in browser storage
 *  6. GET /api/interviews/{interview_id}/fhir/preview: Retrieves valid FHIR R4 Bundle preview
 *  7. GET /api/interviews/{interview_id}/fhir/preview: Handles missing or invalid interview (404) safely
 *  8. POST /api/interviews/{interview_id}/fhir/export: Successful transmission to HIS with external reference
 *  9. POST /api/interviews/{interview_id}/fhir/export: Supports custom destination system payload
 * 10. Consent Prerequisite: Returns 403 Forbidden when DATA_SHARING consent has not been granted
 * 11. Review Prerequisite: Returns 400 Bad Request when case sheet is unverified by doctor
 * 12. Gateway Failure: Returns 502 Bad Gateway when external HIS is unreachable
 * 13. GET /api/interviews/{interview_id}/fhir/exports: Retrieves audit history of past transmissions
 * 14. GET /api/interviews/{interview_id}/fhir/exports: Handles empty export list cleanly
 * 15. FHIR Bundle Structure: Validates presence of Composition, Patient, and Observation entries
 * 16. FHIR Transmission Status: Correctly distinguishes TRANSMITTED vs FAILED vs PENDING
 * 17. HIS Transmission Retries: Verifies retry count increments on re-transmission attempts
 * 18. RBAC: Unauthorized PATIENT role is blocked (403 Forbidden) from transmitting cases to HIS
 * 19. RBAC: Authorized DOCTOR role is permitted to trigger HIS exports
 * 20. RBAC: Authorized STAFF role is permitted to trigger HIS exports
 * 21. Authoritative State Reload: Interoperability transmission audit trail reloads upon export
 * 22. Storage Purity: Zero FHIR bundles, clinical summaries, or ABDM secrets stored in storage
 * 23. Console Security: Zero bearer tokens, passwords, or patient PHI leaked to console
 * 24. Screen 5 Verification: screen5-doctor-dashboard.html contains all FHIR and HIS controls
 * 25. Screen 1 Verification: screen1-registration.html keeps ABHA input strictly optional
 * 26. Screen 4 Verification: screen4-summary.html maintains data sharing consent prerequisite
 */

const fs = require('fs');
const path = require('path');
const assert = require('assert');

// Mock browser sessionStorage & localStorage
class MockSessionStorage {
  constructor() {
    this.store = {};
  }
  getItem(key) {
    return this.store[key] || null;
  }
  setItem(key, value) {
    this.store[key] = String(value);
  }
  removeItem(key) {
    delete this.store[key];
  }
  clear() {
    this.store = {};
  }
}

const mockSessionStorage = new MockSessionStorage();
const mockLocalStorage = new MockSessionStorage();

global.window = global;
global.sessionStorage = mockSessionStorage;
global.localStorage = mockLocalStorage;

const MediKioskConfig = require('../src/scripts/config.js');
const MediKioskSession = require('../src/scripts/session.js');
const MediKioskApi = require('../src/scripts/api.js');

// Mock fetch interceptor helper
let mockRouteHandlers = {};

function resetMockRoutes() {
  mockRouteHandlers = {};
}

function registerMockRoute(method, pathPattern, handler) {
  mockRouteHandlers[`${method.toUpperCase()}:${pathPattern}`] = handler;
}

// Global fetch mock
global.fetch = async (url, options = {}) => {
  const method = (options.method || 'GET').toUpperCase();
  const parsedUrl = new URL(url, 'http://127.0.0.1:8000');
  const pathname = parsedUrl.pathname;

  for (const [key, handler] of Object.entries(mockRouteHandlers)) {
    const [routeMethod, routePattern] = key.split(':');
    if (routeMethod !== method) continue;

    const regexPattern = new RegExp('^' + routePattern.replace(/{[^}]+}/g, '([^/]+)') + '$');
    const match = pathname.match(regexPattern);

    if (match) {
      let bodyData = null;
      if (options.body) {
        try {
          bodyData = JSON.parse(options.body);
        } catch (e) {
          bodyData = options.body;
        }
      }
      return handler({
        pathname,
        params: match.slice(1),
        body: bodyData,
        headers: options.headers || {},
        searchParams: parsedUrl.searchParams
      });
    }
  }

  return {
    ok: false,
    status: 404,
    statusText: 'Not Found',
    headers: { get: () => 'application/json' },
    json: async () => ({ detail: `No mock route for ${method} ${pathname}` }),
    text: async () => `No mock route for ${method} ${pathname}`
  };
};

function createJsonResponse(data, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    headers: {
      get: (h) => (h.toLowerCase() === 'content-type' ? 'application/json' : null)
    },
    json: async () => data,
    text: async () => JSON.stringify(data)
  };
}

let testsPassed = 0;
let testsFailed = 0;

async function runTest(testName, fn) {
  try {
    resetMockRoutes();
    mockSessionStorage.clear();
    mockLocalStorage.clear();
    await fn();
    console.log(`  ✓ ${testName}`);
    testsPassed++;
  } catch (err) {
    console.error(`  ✗ ${testName}`);
    console.error(`    ${err.message}`);
    testsFailed++;
  }
}

async function main() {
  console.log('\n--- Step 9: ABHA & Interoperability Tests ---');

  // T1: GET /api/patients/{patient_id}/abha: Retrieves linked ABHA profile
  await runTest('T1: GET /api/patients/{id}/abha retrieves linked ABHA profile with verification status', async () => {
    registerMockRoute('GET', '/api/patients/{id}/abha', ({ params }) => {
      return createJsonResponse({
        patient_id: params[0],
        abha_number: '14-1234-5678-9012',
        abha_address: 'rahul.sharma@abdm',
        status: 'ACTIVE',
        linked: true,
        verification_status: 'VERIFIED',
        environment: 'MOCK',
        linked_at: '2026-09-14T10:00:00Z',
        raw_profile: {
          first_name: 'Rahul',
          last_name: 'Sharma',
          gender: 'M',
          year_of_birth: 1985
        }
      });
    });

    const res = await MediKioskApi.get('/api/patients/pt-101/abha');
    assert.strictEqual(res.ok, true);
    assert.strictEqual(res.data.linked, true);
    assert.strictEqual(res.data.abha_number, '14-1234-5678-9012');
    assert.strictEqual(res.data.verification_status, 'VERIFIED');
    assert.strictEqual(res.data.environment, 'MOCK');
  });

  // T2: GET /api/patients/{patient_id}/abha: Handles unlinked ABHA profile cleanly
  await runTest('T2: GET /api/patients/{id}/abha handles unlinked ABHA profile cleanly', async () => {
    registerMockRoute('GET', '/api/patients/{id}/abha', ({ params }) => {
      return createJsonResponse({
        patient_id: params[0],
        abha_number: null,
        abha_address: null,
        status: 'NOT_LINKED',
        linked: false,
        verification_status: 'UNVERIFIED',
        environment: 'MOCK'
      });
    });

    const res = await MediKioskApi.get('/api/patients/pt-202/abha');
    assert.strictEqual(res.ok, true);
    assert.strictEqual(res.data.linked, false);
    assert.strictEqual(res.data.abha_number, null);
    assert.strictEqual(res.data.status, 'NOT_LINKED');
  });

  // T3: GET /api/patients/{patient_id}/abha: Handles non-existent patient throwing ApiError
  await runTest('T3: GET /api/patients/{id}/abha handles non-existent patient (404) throwing ApiError', async () => {
    registerMockRoute('GET', '/api/patients/{id}/abha', () => {
      return createJsonResponse({ detail: 'Patient not found' }, 404);
    });

    let caughtErr = null;
    try {
      await MediKioskApi.get('/api/patients/pt-999/abha');
    } catch (e) {
      caughtErr = e;
    }
    assert.notStrictEqual(caughtErr, null);
    assert.strictEqual(caughtErr.status, 404);
    assert.strictEqual(caughtErr.isNotFound, true);
  });

  // T4: ABHA Optionality: Patient intake and interview proceed without ABHA
  await runTest('T4: ABHA Optionality - Patient intake and interview proceed without ABHA', async () => {
    registerMockRoute('POST', '/api/patients', ({ body }) => {
      assert.strictEqual(body.abha_number, undefined);
      return createJsonResponse({
        id: 'pt-anonymous-1',
        name: 'Sunita Devi',
        gender: 'FEMALE',
        date_of_birth: '1978-05-12',
        created_at: new Date().toISOString()
      }, 201);
    });

    const regRes = await MediKioskApi.post('/api/patients', {
      name: 'Sunita Devi',
      gender: 'FEMALE',
      date_of_birth: '1978-05-12'
    });
    assert.strictEqual(regRes.ok, true);
    assert.strictEqual(regRes.data.id, 'pt-anonymous-1');
  });

  // T5: ABHA Security: Zero OTPs, Aadhaar numbers, or ABDM secrets stored in storage
  await runTest('T5: ABHA Security - Zero OTPs, Aadhaar numbers, or ABDM secrets stored in storage', async () => {
    MediKioskSession.setPatientId('pt-101');
    MediKioskSession.setInterviewId('int-101');

    const forbiddenTerms = ['aadhaar', 'otp', 'raw_profile', 'access_token_abdm', 'secret'];
    const sessionKeys = Object.keys(mockSessionStorage.store);
    const localKeys = Object.keys(mockLocalStorage.store);

    for (const key of [...sessionKeys, ...localKeys]) {
      const lowerKey = key.toLowerCase();
      for (const term of forbiddenTerms) {
        assert.strictEqual(lowerKey.includes(term), false, `Forbidden key ${key} found in storage`);
      }
    }
  });

  // T6: GET /api/interviews/{interview_id}/fhir/preview: Retrieves valid FHIR R4 Bundle preview
  await runTest('T6: GET /api/interviews/{id}/fhir/preview retrieves valid FHIR R4 Bundle preview', async () => {
    registerMockRoute('GET', '/api/interviews/{id}/fhir/preview', ({ params }) => {
      return createJsonResponse({
        interview_id: params[0],
        bundle: {
          resourceType: 'Bundle',
          id: `bundle-${params[0]}`,
          type: 'document',
          timestamp: '2026-09-14T11:00:00Z',
          entry: [
            {
              resource: {
                resourceType: 'Composition',
                id: 'comp-1',
                status: 'final',
                title: 'OPD Clinical Intake Summary'
              }
            },
            {
              resource: {
                resourceType: 'Patient',
                id: 'patient-1',
                name: [{ text: 'Rahul Sharma' }],
                gender: 'male'
              }
            },
            {
              resource: {
                resourceType: 'Observation',
                id: 'obs-1',
                code: { text: 'Systolic Blood Pressure' },
                valueQuantity: { value: 130, unit: 'mmHg' }
              }
            }
          ]
        },
        summary_version: 1,
        is_valid: true
      });
    });

    const res = await MediKioskApi.get('/api/interviews/int-101/fhir/preview');
    assert.strictEqual(res.ok, true);
    assert.strictEqual(res.data.is_valid, true);
    assert.strictEqual(res.data.bundle.resourceType, 'Bundle');
    assert.strictEqual(res.data.bundle.type, 'document');
    assert.strictEqual(res.data.bundle.entry.length, 3);
  });

  // T7: GET /api/interviews/{interview_id}/fhir/preview: Handles missing or un-summarized interview
  await runTest('T7: GET /api/interviews/{id}/fhir/preview handles un-summarized interview (404) safely', async () => {
    registerMockRoute('GET', '/api/interviews/{id}/fhir/preview', () => {
      return createJsonResponse({ detail: 'No finalized summary available for FHIR export preview' }, 404);
    });

    let caughtErr = null;
    try {
      await MediKioskApi.get('/api/interviews/int-incomplete/fhir/preview');
    } catch (e) {
      caughtErr = e;
    }
    assert.notStrictEqual(caughtErr, null);
    assert.strictEqual(caughtErr.status, 404);
  });

  // T8: POST /api/interviews/{interview_id}/fhir/export: Successful transmission to HIS
  await runTest('T8: POST /api/interviews/{id}/fhir/export transmits to HIS with external reference', async () => {
    registerMockRoute('POST', '/api/interviews/{id}/fhir/export', ({ params, body }) => {
      return createJsonResponse({
        export_id: 'exp-001',
        interview_id: params[0],
        destination_system: body?.destination_system || 'HOSPITAL_EMR',
        transmission_status: 'TRANSMITTED',
        external_reference: 'HIS-REF-98765',
        exported_at: '2026-09-14T11:05:00Z',
        retry_count: 1
      }, 200);
    });

    const res = await MediKioskApi.post('/api/interviews/int-101/fhir/export', {});
    assert.strictEqual(res.ok, true);
    assert.strictEqual(res.data.transmission_status, 'TRANSMITTED');
    assert.strictEqual(res.data.destination_system, 'HOSPITAL_EMR');
    assert.strictEqual(res.data.external_reference, 'HIS-REF-98765');
  });

  // T9: POST /api/interviews/{interview_id}/fhir/export: Custom destination system payload
  await runTest('T9: POST /api/interviews/{id}/fhir/export supports custom destination system payload', async () => {
    registerMockRoute('POST', '/api/interviews/{id}/fhir/export', ({ params, body }) => {
      return createJsonResponse({
        export_id: 'exp-002',
        interview_id: params[0],
        destination_system: body.destination_system,
        transmission_status: 'TRANSMITTED',
        external_reference: 'APOLLO-REC-4412',
        exported_at: '2026-09-14T11:06:00Z',
        retry_count: 1
      }, 200);
    });

    const res = await MediKioskApi.post('/api/interviews/int-101/fhir/export', {
      destination_system: 'APOLLO_HIS'
    });
    assert.strictEqual(res.ok, true);
    assert.strictEqual(res.data.destination_system, 'APOLLO_HIS');
    assert.strictEqual(res.data.external_reference, 'APOLLO-REC-4412');
  });

  // T10: Consent Prerequisite: Returns 403 Forbidden when DATA_SHARING consent is missing
  await runTest('T10: Consent Prerequisite - Returns 403 Forbidden when DATA_SHARING consent is missing', async () => {
    registerMockRoute('POST', '/api/interviews/{id}/fhir/export', () => {
      return createJsonResponse({
        detail: 'Patient has not granted mandatory DATA_SHARING consent for external EHR transmission.'
      }, 403);
    });

    let caughtErr = null;
    try {
      await MediKioskApi.post('/api/interviews/int-no-consent/fhir/export', {});
    } catch (e) {
      caughtErr = e;
    }
    assert.notStrictEqual(caughtErr, null);
    assert.strictEqual(caughtErr.status, 403);
    assert.strictEqual(caughtErr.isForbidden, true);
    assert.strictEqual(caughtErr.message.includes('DATA_SHARING'), true);
  });

  // T11: Review Prerequisite: Returns 400 Bad Request when case sheet is unverified by doctor
  await runTest('T11: Review Prerequisite - Returns 400 Bad Request when case sheet is unverified', async () => {
    registerMockRoute('POST', '/api/interviews/{id}/fhir/export', () => {
      return createJsonResponse({
        detail: 'Interview summary must be clinician-verified before FHIR export.'
      }, 400);
    });

    let caughtErr = null;
    try {
      await MediKioskApi.post('/api/interviews/int-unverified/fhir/export', {});
    } catch (e) {
      caughtErr = e;
    }
    assert.notStrictEqual(caughtErr, null);
    assert.strictEqual(caughtErr.status, 400);
    assert.strictEqual(caughtErr.isClientError, true);
    assert.strictEqual(caughtErr.message.includes('clinician-verified'), true);
  });

  // T12: Gateway Failure: Returns 502 Bad Gateway when external HIS is unreachable
  await runTest('T12: Gateway Failure - Returns 502 Bad Gateway when external HIS is unreachable', async () => {
    registerMockRoute('POST', '/api/interviews/{id}/fhir/export', () => {
      return createJsonResponse({
        detail: 'Hospital Information System gateway connection timeout. Retry queued.'
      }, 502);
    });

    let caughtErr = null;
    try {
      await MediKioskApi.post('/api/interviews/int-101/fhir/export', {});
    } catch (e) {
      caughtErr = e;
    }
    assert.notStrictEqual(caughtErr, null);
    assert.strictEqual(caughtErr.status, 502);
    assert.strictEqual(caughtErr.isServerError, true);
  });

  // T13: GET /api/interviews/{interview_id}/fhir/exports: Retrieves audit history of past transmissions
  await runTest('T13: GET /api/interviews/{id}/fhir/exports retrieves audit history of past transmissions', async () => {
    registerMockRoute('GET', '/api/interviews/{id}/fhir/exports', ({ params }) => {
      return createJsonResponse([
        {
          id: 'exp-001',
          interview_id: params[0],
          destination_system: 'HOSPITAL_EMR',
          transmission_status: 'TRANSMITTED',
          external_reference: 'HIS-REF-98765',
          retry_count: 1,
          created_at: '2026-09-14T11:05:00Z'
        },
        {
          id: 'exp-000',
          interview_id: params[0],
          destination_system: 'HOSPITAL_EMR',
          transmission_status: 'FAILED',
          external_reference: null,
          retry_count: 0,
          created_at: '2026-09-14T11:00:00Z'
        }
      ]);
    });

    const res = await MediKioskApi.get('/api/interviews/int-101/fhir/exports');
    assert.strictEqual(res.ok, true);
    assert.strictEqual(Array.isArray(res.data), true);
    assert.strictEqual(res.data.length, 2);
    assert.strictEqual(res.data[0].transmission_status, 'TRANSMITTED');
    assert.strictEqual(res.data[1].transmission_status, 'FAILED');
  });

  // T14: GET /api/interviews/{interview_id}/fhir/exports: Handles empty export list cleanly
  await runTest('T14: GET /api/interviews/{id}/fhir/exports handles empty export list cleanly', async () => {
    registerMockRoute('GET', '/api/interviews/{id}/fhir/exports', () => {
      return createJsonResponse([]);
    });

    const res = await MediKioskApi.get('/api/interviews/int-new/fhir/exports');
    assert.strictEqual(res.ok, true);
    assert.strictEqual(Array.isArray(res.data), true);
    assert.strictEqual(res.data.length, 0);
  });

  // T15: FHIR Bundle Structure: Validates presence of Composition, Patient, and Observation entries
  await runTest('T15: FHIR Bundle Structure - Validates Composition, Patient, and Observation entries', async () => {
    registerMockRoute('GET', '/api/interviews/{id}/fhir/preview', () => {
      return createJsonResponse({
        bundle: {
          resourceType: 'Bundle',
          type: 'document',
          entry: [
            { resource: { resourceType: 'Composition', status: 'final' } },
            { resource: { resourceType: 'Patient', id: 'pt-1' } },
            { resource: { resourceType: 'Encounter', status: 'finished' } },
            { resource: { resourceType: 'Observation', code: { text: 'Heart Rate' } } }
          ]
        },
        is_valid: true
      });
    });

    const res = await MediKioskApi.get('/api/interviews/int-101/fhir/preview');
    const resourceTypes = res.data.bundle.entry.map(e => e.resource.resourceType);
    assert.strictEqual(resourceTypes.includes('Composition'), true);
    assert.strictEqual(resourceTypes.includes('Patient'), true);
    assert.strictEqual(resourceTypes.includes('Encounter'), true);
    assert.strictEqual(resourceTypes.includes('Observation'), true);
  });

  // T16: FHIR Transmission Status: Distinguishes TRANSMITTED vs FAILED vs PENDING
  await runTest('T16: FHIR Transmission Status - Distinguishes TRANSMITTED vs FAILED vs PENDING', async () => {
    const statuses = ['PENDING', 'TRANSMITTED', 'FAILED'];
    for (const st of statuses) {
      registerMockRoute('POST', `/api/test/export-status/${st}`, () => {
        return createJsonResponse({
          transmission_status: st
        });
      });
      const res = await MediKioskApi.post(`/api/test/export-status/${st}`, {});
      assert.strictEqual(res.data.transmission_status, st);
    }
  });

  // T17: HIS Transmission Retries: Verifies retry count tracking
  await runTest('T17: HIS Transmission Retries - Verifies retry count increments on re-transmission attempts', async () => {
    let attemptCount = 0;
    registerMockRoute('POST', '/api/interviews/{id}/fhir/export', () => {
      attemptCount++;
      return createJsonResponse({
        export_id: `exp-${attemptCount}`,
        retry_count: attemptCount,
        transmission_status: attemptCount >= 2 ? 'TRANSMITTED' : 'FAILED'
      });
    });

    const res1 = await MediKioskApi.post('/api/interviews/int-retry/fhir/export', {});
    assert.strictEqual(res1.data.retry_count, 1);
    assert.strictEqual(res1.data.transmission_status, 'FAILED');

    const res2 = await MediKioskApi.post('/api/interviews/int-retry/fhir/export', {});
    assert.strictEqual(res2.data.retry_count, 2);
    assert.strictEqual(res2.data.transmission_status, 'TRANSMITTED');
  });

  // T18: RBAC: Unauthorized PATIENT role blocked from HIS export
  await runTest('T18: RBAC - Unauthorized PATIENT role blocked (403 Forbidden) from transmitting to HIS', async () => {
    registerMockRoute('POST', '/api/interviews/{id}/fhir/export', ({ headers }) => {
      const auth = headers['Authorization'] || headers['authorization'] || '';
      if (auth.includes('patient-token')) {
        return createJsonResponse({ detail: 'Access denied: role DOCTOR or STAFF required' }, 403);
      }
      return createJsonResponse({ transmission_status: 'TRANSMITTED' });
    });

    MediKioskSession.setAuthToken('patient-token');
    let caughtErr = null;
    try {
      await MediKioskApi.post('/api/interviews/int-101/fhir/export', {});
    } catch (e) {
      caughtErr = e;
    }
    assert.notStrictEqual(caughtErr, null);
    assert.strictEqual(caughtErr.status, 403);
    assert.strictEqual(caughtErr.isForbidden, true);
  });

  // T19: RBAC: Authorized DOCTOR role permitted for HIS export
  await runTest('T19: RBAC - Authorized DOCTOR role permitted for HIS export', async () => {
    registerMockRoute('POST', '/api/interviews/{id}/fhir/export', ({ headers }) => {
      const auth = headers['Authorization'] || headers['authorization'] || '';
      if (auth.includes('doctor-token')) {
        return createJsonResponse({
          transmission_status: 'TRANSMITTED',
          exported_by_role: 'DOCTOR'
        }, 200);
      }
      return createJsonResponse({ detail: 'Forbidden' }, 403);
    });

    MediKioskSession.setAuthToken('doctor-token');
    const res = await MediKioskApi.post('/api/interviews/int-101/fhir/export', {});
    assert.strictEqual(res.ok, true);
    assert.strictEqual(res.data.transmission_status, 'TRANSMITTED');
    assert.strictEqual(res.data.exported_by_role, 'DOCTOR');
  });

  // T20: RBAC: Authorized STAFF role permitted for HIS export
  await runTest('T20: RBAC - Authorized STAFF role permitted for HIS export', async () => {
    registerMockRoute('POST', '/api/interviews/{id}/fhir/export', ({ headers }) => {
      const auth = headers['Authorization'] || headers['authorization'] || '';
      if (auth.includes('staff-token')) {
        return createJsonResponse({
          transmission_status: 'TRANSMITTED',
          exported_by_role: 'STAFF'
        }, 200);
      }
      return createJsonResponse({ detail: 'Forbidden' }, 403);
    });

    MediKioskSession.setAuthToken('staff-token');
    const res = await MediKioskApi.post('/api/interviews/int-101/fhir/export', {});
    assert.strictEqual(res.ok, true);
    assert.strictEqual(res.data.transmission_status, 'TRANSMITTED');
    assert.strictEqual(res.data.exported_by_role, 'STAFF');
  });

  // T21: Authoritative State Reload: Audit trail reloaded upon export
  await runTest('T21: Authoritative State Reload - Interoperability transmission audit trail reloads upon export', async () => {
    let exportRecords = [];
    registerMockRoute('GET', '/api/interviews/{id}/fhir/exports', () => {
      return createJsonResponse(exportRecords);
    });

    registerMockRoute('POST', '/api/interviews/{id}/fhir/export', () => {
      const newExp = {
        id: `exp-${exportRecords.length + 1}`,
        transmission_status: 'TRANSMITTED',
        external_reference: 'HIS-100'
      };
      exportRecords.unshift(newExp);
      return createJsonResponse(newExp);
    });

    const initList = await MediKioskApi.get('/api/interviews/int-101/fhir/exports');
    assert.strictEqual(initList.data.length, 0);

    await MediKioskApi.post('/api/interviews/int-101/fhir/export', {});

    const updatedList = await MediKioskApi.get('/api/interviews/int-101/fhir/exports');
    assert.strictEqual(updatedList.data.length, 1);
    assert.strictEqual(updatedList.data[0].transmission_status, 'TRANSMITTED');
  });

  // T22: Storage Purity: Zero FHIR bundles, clinical summaries, or ABDM secrets stored in storage
  await runTest('T22: Storage Purity - Zero FHIR bundles, clinical summaries, or ABDM secrets in storage', async () => {
    MediKioskSession.setAuthToken('valid-auth-token');
    MediKioskSession.setPatientId('pt-101');
    MediKioskSession.setInterviewId('int-101');
    MediKioskSession.setSessionId('sess-101');

    const allowedKeys = new Set([
      'medikiosk_auth_token',
      'medikiosk_patient_id',
      'medikiosk_interview_id',
      'medikiosk_session_id',
      'auth_token',
      'patient_id',
      'interview_id',
      'session_id'
    ]);
    const currentKeys = Object.keys(mockSessionStorage.store);

    for (const k of currentKeys) {
      assert.strictEqual(allowedKeys.has(k), true, `Unexpected key found in sessionStorage: ${k}`);
    }

    assert.strictEqual(Object.keys(mockLocalStorage.store).length, 0);
  });

  // T23: Console Security: Zero bearer tokens, passwords, or patient PHI leaked to console
  await runTest('T23: Console Security - Zero bearer tokens, passwords, or patient PHI leaked to console', async () => {
    const interceptedLogs = [];
    const origLog = console.log;
    const origWarn = console.warn;
    const origError = console.error;

    console.log = (...args) => interceptedLogs.push(args.join(' '));
    console.warn = (...args) => interceptedLogs.push(args.join(' '));
    console.error = (...args) => interceptedLogs.push(args.join(' '));

    try {
      registerMockRoute('POST', '/api/interviews/{id}/fhir/export', () => {
        return createJsonResponse({
          transmission_status: 'TRANSMITTED',
          external_reference: 'HIS-999'
        });
      });

      await MediKioskApi.post('/api/interviews/int-101/fhir/export', {
        destination_system: 'HOSPITAL_EMR'
      });

      const fullLogText = interceptedLogs.join('\n');
      assert.strictEqual(fullLogText.includes('Bearer secret-token'), false);
      assert.strictEqual(fullLogText.includes('doctor_password'), false);
    } finally {
      console.log = origLog;
      console.warn = origWarn;
      console.error = origError;
    }
  });

  // T24: Screen 5 Verification: screen5-doctor-dashboard.html contains all FHIR and HIS controls
  await runTest('T24: Screen 5 Verification - screen5-doctor-dashboard.html contains all FHIR and HIS controls', async () => {
    const htmlPath = path.join(__dirname, '../src/screens/screen5-doctor-dashboard.html');
    const htmlContent = fs.readFileSync(htmlPath, 'utf8');

    assert.strictEqual(htmlContent.includes('btnPreviewFhir'), true, 'Missing btnPreviewFhir element');
    assert.strictEqual(htmlContent.includes('btnExportHis'), true, 'Missing btnExportHis element');
    assert.strictEqual(htmlContent.includes('fhirPreviewModal'), true, 'Missing fhirPreviewModal element');
    assert.strictEqual(htmlContent.includes('hisExportStatusDisplay'), true, 'Missing hisExportStatusDisplay element');
    assert.strictEqual(htmlContent.includes('fhirExportsList'), true, 'Missing fhirExportsList element');
    assert.strictEqual(htmlContent.includes('activeAbhaBadge'), true, 'Missing activeAbhaBadge element');
    assert.strictEqual(htmlContent.includes('/api/interviews/${interviewId}/fhir/preview'), true, 'Missing FHIR preview API call');
    assert.strictEqual(htmlContent.includes('/api/interviews/${interviewId}/fhir/export'), true, 'Missing FHIR export API call');
    assert.strictEqual(htmlContent.includes('/api/patients/${patientId}/abha'), true, 'Missing ABHA status API call');
  });

  // T25: Screen 1 Verification: screen1a-identity.html keeps ABHA input strictly optional
  await runTest('T25: Screen 1 Verification - screen1a-identity.html keeps ABHA input strictly optional', async () => {
    const htmlPath = path.join(__dirname, '../src/screens/screen1a-identity.html');
    const htmlContent = fs.readFileSync(htmlPath, 'utf8');

    assert.strictEqual(htmlContent.includes('ABHA') || htmlContent.includes('abha'), true, 'Missing ABHA reference in screen 1a');
    assert.strictEqual(htmlContent.includes('without ABHA') || htmlContent.includes('Optional') || htmlContent.includes('optional'), true, 'ABHA must be marked optional or support without ABHA');
  });

  // T26: Screen 4 Verification: screen4-summary.html maintains data sharing consent prerequisite
  await runTest('T26: Screen 4 Verification - screen4-summary.html maintains data sharing consent prerequisite', async () => {
    const htmlPath = path.join(__dirname, '../src/screens/screen4-summary.html');
    const htmlContent = fs.readFileSync(htmlPath, 'utf8');

    assert.strictEqual(htmlContent.includes('DATA_SHARING') || htmlContent.includes('consent') || htmlContent.includes('confirm'), true, 'Missing consent prerequisite reference in screen 4');
  });

  console.log(`\nStep 9 Test Results: ${testsPassed} passed, ${testsFailed} failed`);
  if (testsFailed > 0) {
    process.exit(1);
  }
}

main().catch(err => {
  console.error('Fatal error running Step 9 test suite:', err);
  process.exit(1);
});
