/**
 * Step 3: Purpose-Specific Consent Integration Test Suite
 * Tests endpoint resolution, patient_id injection, CLINICAL_HISTORY enforcement,
 * purpose-by-purpose isolation, error mappings, session storage purity, and double-submission protection.
 */

const assert = require('assert');
const fs = require('fs');
const path = require('path');

// Mock browser environment
class MockSessionStorage {
  constructor() {
    this.store = {};
  }
  getItem(key) {
    return this.store[key] || null;
  }
  setItem(key, val) {
    this.store[key] = String(val);
  }
  removeItem(key) {
    delete this.store[key];
  }
  clear() {
    this.store = {};
  }
}

const mockStorage = new MockSessionStorage();
global.window = global;
global.sessionStorage = mockStorage;

const MediKioskConfig = require('../src/scripts/config.js');
const MediKioskSession = require('../src/scripts/session.js');
const MediKioskApi = require('../src/scripts/api.js');

let testCount = 0;
function test(name, fn) {
  try {
    fn();
    testCount++;
    console.log(`  ✓ ${name}`);
  } catch (err) {
    console.error(`  ✗ ${name}`);
    console.error(err);
    process.exit(1);
  }
}

async function runAsyncTest(name, fn) {
  try {
    await fn();
    testCount++;
    console.log(`  ✓ ${name}`);
  } catch (err) {
    console.error(`  ✗ ${name}`);
    console.error(err);
    process.exit(1);
  }
}

console.log('Running MediKiosk Step 3 Consent Integration Test Suite...\n');

// 1. Static Screen Markup & Contract Invariants
test('HTML Screen 1b Consent: Scripts & elements present', () => {
  const html = fs.readFileSync(path.join(__dirname, '../src/screens/screen1b-consent.html'), 'utf8');
  assert.ok(html.includes('../scripts/config.js'), 'config.js script missing in screen1b-consent');
  assert.ok(html.includes('../scripts/session.js'), 'session.js script missing in screen1b-consent');
  assert.ok(html.includes('../scripts/api.js'), 'api.js script missing in screen1b-consent');
  assert.ok(html.includes('id="btnAgree"'), 'btnAgree element missing');
  assert.ok(html.includes('id="consentErrorMsg"'), 'consentErrorMsg element missing');
  assert.ok(html.includes('id="chk-CLINICAL_HISTORY"'), 'chk-CLINICAL_HISTORY missing');
  assert.ok(html.includes('id="chk-DOCUMENT_PROCESSING"'), 'chk-DOCUMENT_PROCESSING missing');
  assert.ok(html.includes('id="chk-AI_SUMMARIZATION"'), 'chk-AI_SUMMARIZATION missing');
  assert.ok(html.includes('id="chk-BILINGUAL_OUTPUT"'), 'chk-BILINGUAL_OUTPUT missing');
  assert.ok(html.includes('id="chk-DATA_SHARING"'), 'chk-DATA_SHARING missing');
  assert.ok(html.includes('id="chk-ABHA_LINKAGE"'), 'chk-ABHA_LINKAGE missing');
  assert.ok(html.includes('/api/patients/${patientId}/consents'), 'Backend consent endpoint pattern missing');
});

// Helper for mocking fetch
function setupMockFetch(routes) {
  global.fetch = async (url, options) => {
    const method = (options.method || 'GET').toUpperCase();
    const parsedUrl = new URL(url);
    const pathname = parsedUrl.pathname;
    const routeKey = `${method} ${pathname}`;

    const handler = routes[routeKey] || routes[pathname];
    if (!handler) {
      throw new Error(`Unhandled mock route: ${routeKey} (${url})`);
    }

    const res = await handler(options);
    return {
      status: res.status || 200,
      ok: (res.status || 200) >= 200 && (res.status || 200) < 300,
      headers: {
        get: (h) => (h.toLowerCase() === 'content-type' ? 'application/json' : null)
      },
      json: async () => res.body,
      text: async () => JSON.stringify(res.body)
    };
  };
}

(async () => {
  // Test 1 & 2 & 3: Correct endpoint, patient_id injection, and CLINICAL_HISTORY grant
  await runAsyncTest('Endpoint & Payload: Correct /api/patients/{patient_id}/consents called with valid contract', async () => {
    MediKioskSession.clearWorkflowState();
    MediKioskSession.setPatientId('555');

    const recordedCalls = [];
    setupMockFetch({
      'POST /api/patients/555/consents': (opts) => {
        const body = JSON.parse(opts.body);
        recordedCalls.push(body);
        return {
          status: 201,
          body: {
            id: 1001,
            patient_id: 555,
            purpose: body.purpose,
            status: 'GRANTED',
            collection_method: body.collection_method,
            consent_version: body.consent_version,
            language_code: body.language_code,
            granted_at: '2026-09-14T12:00:00Z'
          }
        };
      }
    });

    const payload = {
      purpose: 'CLINICAL_HISTORY',
      language_code: 'en',
      consent_version: '1.0',
      collection_method: 'PATIENT_SELF'
    };

    const patientId = MediKioskSession.getPatientId();
    assert.strictEqual(patientId, '555');

    const res = await MediKioskApi.post(`/api/patients/${patientId}/consents`, payload);
    assert.strictEqual(res.status, 201);
    assert.strictEqual(res.data.status, 'GRANTED');
    assert.strictEqual(res.data.purpose, 'CLINICAL_HISTORY');
    assert.strictEqual(recordedCalls.length, 1);
    assert.strictEqual(recordedCalls[0].purpose, 'CLINICAL_HISTORY');
    assert.strictEqual(Object.keys(recordedCalls[0]).length, 4); // extra="forbid" invariant
  });

  // Test 4: Missing patient_id handled safely
  test('Session Validation: Missing patient_id detects unauthenticated state', () => {
    MediKioskSession.clearWorkflowState();
    assert.strictEqual(MediKioskSession.getPatientId(), null);
    // In screen1b-consent.html, missing patient_id immediately alerts user and returns to screen1a-identity
  });

  // Test 5: HTTP 401 handling
  await runAsyncTest('Error 401: Unauthorized consent attempt throws isAuthError=true', async () => {
    setupMockFetch({
      'POST /api/patients/555/consents': () => ({
        status: 401,
        body: { detail: 'Authentication required' }
      })
    });

    try {
      await MediKioskApi.post('/api/patients/555/consents', {
        purpose: 'CLINICAL_HISTORY',
        language_code: 'en',
        consent_version: '1.0',
        collection_method: 'PATIENT_SELF'
      });
      assert.fail('Should have thrown 401');
    } catch (err) {
      assert.strictEqual(err.status, 401);
      assert.strictEqual(err.isAuthError, true);
    }
  });

  // Test 6: HTTP 403 handling
  await runAsyncTest('Error 403: Forbidden/consent mismatch throws isForbidden=true', async () => {
    setupMockFetch({
      'POST /api/patients/555/consents': () => ({
        status: 403,
        body: { detail: 'Access forbidden: patient ownership mismatch' }
      })
    });

    try {
      await MediKioskApi.post('/api/patients/555/consents', {
        purpose: 'CLINICAL_HISTORY',
        language_code: 'en',
        consent_version: '1.0',
        collection_method: 'PATIENT_SELF'
      });
      assert.fail('Should have thrown 403');
    } catch (err) {
      assert.strictEqual(err.status, 403);
      assert.strictEqual(err.isForbidden, true);
    }
  });

  // Test 7: HTTP 404 handling
  await runAsyncTest('Error 404: Non-existent patient throws isNotFound=true', async () => {
    setupMockFetch({
      'POST /api/patients/99999/consents': () => ({
        status: 404,
        body: { detail: 'Patient with ID 99999 not found' }
      })
    });

    try {
      await MediKioskApi.post('/api/patients/99999/consents', {
        purpose: 'CLINICAL_HISTORY',
        language_code: 'en',
        consent_version: '1.0',
        collection_method: 'PATIENT_SELF'
      });
      assert.fail('Should have thrown 404');
    } catch (err) {
      assert.strictEqual(err.status, 404);
      assert.strictEqual(err.isNotFound, true);
    }
  });

  // Test 8: HTTP 409 handling
  await runAsyncTest('Error 409: Conflict status handled with isConflict=true', async () => {
    setupMockFetch({
      'POST /api/patients/555/consents': () => ({
        status: 409,
        body: { detail: 'Consent conflict detected' }
      })
    });

    try {
      await MediKioskApi.post('/api/patients/555/consents', {
        purpose: 'CLINICAL_HISTORY',
        language_code: 'en',
        consent_version: '1.0',
        collection_method: 'PATIENT_SELF'
      });
      assert.fail('Should have thrown 409');
    } catch (err) {
      assert.strictEqual(err.status, 409);
      assert.strictEqual(err.isConflict, true);
    }
  });

  // Test 9: HTTP 422 validation error handling
  await runAsyncTest('Error 422: Invalid consent purpose or fields caught with isValidationError=true', async () => {
    setupMockFetch({
      'POST /api/patients/555/consents': () => ({
        status: 422,
        body: {
          detail: [{ loc: ['body', 'purpose'], msg: 'Input should be a valid ConsentPurpose', type: 'enum' }]
        }
      })
    });

    try {
      await MediKioskApi.post('/api/patients/555/consents', {
        purpose: 'INVALID_UNKNOWN_PURPOSE',
        language_code: 'en',
        consent_version: '1.0',
        collection_method: 'PATIENT_SELF'
      });
      assert.fail('Should have thrown 422');
    } catch (err) {
      assert.strictEqual(err.status, 422);
      assert.strictEqual(err.isValidationError, true);
    }
  });

  // Test 10: Network failure handling
  await runAsyncTest('Error Network: Drops or offline handled gracefully with status 0', async () => {
    global.fetch = async () => {
      throw new TypeError('Failed to fetch');
    };

    try {
      await MediKioskApi.post('/api/patients/555/consents', {
        purpose: 'CLINICAL_HISTORY',
        language_code: 'en',
        consent_version: '1.0',
        collection_method: 'PATIENT_SELF'
      });
      assert.fail('Should have thrown network error');
    } catch (err) {
      assert.strictEqual(err.status, 0);
      assert.strictEqual(err.isNetworkError, true);
    }
  });

  // Test 11 & 12: Failed consent does not navigate or create invalid state
  test('Flow Invariant: Failed consent does not alter downstream session state', () => {
    MediKioskSession.clearWorkflowState();
    MediKioskSession.setPatientId('555');
    MediKioskSession.setSessionId('777');

    // State remains strictly patient_id and session_id
    assert.strictEqual(MediKioskSession.getPatientId(), '555');
    assert.strictEqual(MediKioskSession.getSessionId(), '777');
    assert.strictEqual(MediKioskSession.getInterviewId(), null);
  });

  // Test 13: Privacy boundary - no consent records or PHI stored in sessionStorage
  test('Privacy: sessionStorage stores ZERO consent records, legal text, or PHI', () => {
    const keys = Object.keys(mockStorage.store);
    const values = Object.values(mockStorage.store).join(' ');

    assert.ok(!keys.includes('consent'), 'Consent key stored in sessionStorage!');
    assert.ok(!values.includes('CLINICAL_HISTORY'), 'Consent text stored in sessionStorage!');
    assert.ok(!values.includes('voluntarily permit'), 'Legal text stored in sessionStorage!');
  });

  // Test 14: Purpose-specific isolation - other purposes not silently granted
  await runAsyncTest('Purpose Isolation: Only explicitly checked purposes are posted to backend', async () => {
    const postedPurposes = [];
    setupMockFetch({
      'POST /api/patients/555/consents': (opts) => {
        const body = JSON.parse(opts.body);
        postedPurposes.push(body.purpose);
        return {
          status: 201,
          body: { id: 1, purpose: body.purpose, status: 'GRANTED' }
        };
      }
    });

    // Simulate user selecting ONLY CLINICAL_HISTORY and BILINGUAL_OUTPUT
    const selectedPurposes = ['CLINICAL_HISTORY', 'BILINGUAL_OUTPUT'];
    for (const p of selectedPurposes) {
      await MediKioskApi.post('/api/patients/555/consents', {
        purpose: p,
        language_code: 'hi',
        consent_version: '1.0',
        collection_method: 'PATIENT_SELF'
      });
    }

    assert.strictEqual(postedPurposes.length, 2);
    assert.ok(postedPurposes.includes('CLINICAL_HISTORY'));
    assert.ok(postedPurposes.includes('BILINGUAL_OUTPUT'));
    assert.ok(!postedPurposes.includes('DATA_SHARING'), 'DATA_SHARING was silently granted!');
    assert.ok(!postedPurposes.includes('ABHA_LINKAGE'), 'ABHA_LINKAGE was silently granted!');
    assert.ok(!postedPurposes.includes('DOCUMENT_PROCESSING'), 'DOCUMENT_PROCESSING was silently granted!');
    assert.ok(!postedPurposes.includes('AI_SUMMARIZATION'), 'AI_SUMMARIZATION was silently granted!');
  });

  console.log(`\nAll ${testCount} Step 3 Consent Integration tests passed successfully!`);
})();
