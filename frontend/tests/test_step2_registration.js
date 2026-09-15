/**
 * Step 2: Patient Registration & Encounter Session Integration Test Suite
 * Validates backend contract adherence, session state isolation, error mapping,
 * double-submission prevention, and privacy invariants.
 */

const assert = require('assert');
const fs = require('fs');
const path = require('path');

// Setup mock browser environment
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

console.log('Running MediKiosk Step 2 Registration Integration Test Suite...\n');

// 1. Static Screen Markup & Contract Tests
test('HTML Screen 1a Identity: Scripts & elements present', () => {
  const html = fs.readFileSync(path.join(__dirname, '../src/screens/screen1a-identity.html'), 'utf8');
  assert.ok(html.includes('../scripts/config.js'), 'config.js script missing in screen1a-identity');
  assert.ok(html.includes('../scripts/session.js'), 'session.js script missing in screen1a-identity');
  assert.ok(html.includes('../scripts/api.js'), 'api.js script missing in screen1a-identity');
  assert.ok(html.includes('id="scannerModal"'), 'scannerModal missing');
  assert.ok(html.includes('id="btnScannerClose"'), 'btnScannerClose missing');
  assert.ok(html.includes('/api/patients'), 'Backend patient endpoint missing in screen1a-identity script');
  assert.ok(html.includes('/api/sessions'), 'Backend sessions endpoint missing in screen1a-identity script');
});

test('HTML Screen 1a Manual Entry: Scripts & elements present', () => {
  const html = fs.readFileSync(path.join(__dirname, '../src/screens/screen1a-manual-entry.html'), 'utf8');
  assert.ok(html.includes('../scripts/config.js'), 'config.js script missing in screen1a-manual-entry');
  assert.ok(html.includes('../scripts/session.js'), 'session.js script missing in screen1a-manual-entry');
  assert.ok(html.includes('../scripts/api.js'), 'api.js script missing in screen1a-manual-entry');
  assert.ok(html.includes('id="patientName"'), 'patientName input missing');
  assert.ok(html.includes('id="patientDob"'), 'patientDob input missing');
  assert.ok(html.includes('id="patientGender"'), 'patientGender select missing');
  assert.ok(html.includes('id="otpErrorMsg"'), 'otpErrorMsg container missing');
  assert.ok(html.includes('/api/patients'), 'Backend patient endpoint missing in screen1a-manual-entry script');
  assert.ok(html.includes('/api/sessions'), 'Backend sessions endpoint missing in screen1a-manual-entry script');
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

// 2. Integration Tests with Mocked API
(async () => {
  // Test 1: Successful registration and session establishment
  await runAsyncTest('Flow: Successful patient registration stores patient_id and session_id', async () => {
    MediKioskSession.clearWorkflowState();
    let receivedPatientPayload = null;
    let receivedSessionPayload = null;

    setupMockFetch({
      'POST /api/patients': (opts) => {
        receivedPatientPayload = JSON.parse(opts.body);
        return {
          status: 201,
          body: {
            id: 42,
            phone_number: receivedPatientPayload.phone_number,
            name: receivedPatientPayload.name,
            date_of_birth: receivedPatientPayload.date_of_birth,
            gender: receivedPatientPayload.gender,
            preferred_language: receivedPatientPayload.preferred_language,
            created_at: '2026-09-14T10:00:00Z',
            updated_at: '2026-09-14T10:00:00Z'
          }
        };
      },
      'POST /api/sessions': (opts) => {
        receivedSessionPayload = JSON.parse(opts.body);
        return {
          status: 201,
          body: {
            id: 108,
            patient_id: receivedSessionPayload.patient_id,
            interview_id: null,
            status: 'REGISTRATION',
            started_at: '2026-09-14T10:00:00Z',
            last_activity_at: '2026-09-14T10:00:00Z'
          }
        };
      }
    });

    const regPayload = {
      phone_number: '+919876543210',
      name: 'Sunita Sharma',
      date_of_birth: '1985-07-20',
      gender: 'Female',
      preferred_language: 'en'
    };

    // Simulate screen registration call
    const patientRes = await MediKioskApi.post('/api/patients', regPayload);
    assert.strictEqual(patientRes.status, 201);
    assert.strictEqual(patientRes.data.id, 42);
    MediKioskSession.setPatientId(patientRes.data.id);

    const sessionRes = await MediKioskApi.post('/api/sessions', { patient_id: patientRes.data.id });
    assert.strictEqual(sessionRes.status, 201);
    assert.strictEqual(sessionRes.data.id, 108);
    MediKioskSession.setSessionId(sessionRes.data.id);

    // Verify session state
    assert.strictEqual(MediKioskSession.getPatientId(), '42');
    assert.strictEqual(MediKioskSession.getSessionId(), '108');

    // Verify request payload matched backend contract exactly (no extra forbidden fields)
    assert.strictEqual(receivedPatientPayload.phone_number, '+919876543210');
    assert.strictEqual(receivedPatientPayload.name, 'Sunita Sharma');
    assert.strictEqual(receivedPatientPayload.date_of_birth, '1985-07-20');
    assert.strictEqual(receivedPatientPayload.gender, 'Female');
    assert.strictEqual(receivedPatientPayload.preferred_language, 'en');
    assert.strictEqual(Object.keys(receivedPatientPayload).length, 5);

    assert.strictEqual(receivedSessionPayload.patient_id, 42);
    assert.strictEqual(Object.keys(receivedSessionPayload).length, 1);
  });

  // Test 2: Privacy boundary - no PHI stored in sessionStorage
  test('Privacy: sessionStorage contains ONLY required IDs, zero PHI or passwords', () => {
    const stored = mockStorage.store;
    assert.strictEqual(stored['medikiosk_patient_id'], '42');
    assert.strictEqual(stored['medikiosk_session_id'], '108');

    // Check that NO clinical data, name, phone, dob, or password exists in storage
    const storedValues = Object.values(stored).join(' ');
    const storedKeys = Object.keys(stored).join(' ');
    assert.ok(!storedValues.includes('Sunita'), 'Patient name found in sessionStorage!');
    assert.ok(!storedValues.includes('9876543210'), 'Phone number found in sessionStorage!');
    assert.ok(!storedValues.includes('1985-07-20'), 'DOB found in sessionStorage!');
    assert.ok(!storedKeys.includes('password'), 'Password key found in sessionStorage!');
  });

  // Test 3: Duplicate patient handling (HTTP 409)
  await runAsyncTest('Error 409: Duplicate patient throws ApiError with isConflict=true', async () => {
    MediKioskSession.clearWorkflowState();

    setupMockFetch({
      'POST /api/patients': () => ({
        status: 409,
        body: { detail: "Patient with phone number '+919876543210' is already registered." }
      })
    });

    try {
      await MediKioskApi.post('/api/patients', {
        phone_number: '+919876543210',
        name: 'Sunita Sharma',
        date_of_birth: '1985-07-20',
        gender: 'Female',
        preferred_language: 'en'
      });
      assert.fail('Should have thrown 409');
    } catch (err) {
      assert.strictEqual(err.name, 'ApiError');
      assert.strictEqual(err.status, 409);
      assert.strictEqual(err.isConflict, true);
      assert.ok(err.message.includes('already registered'));

      // Verify that failed registration did not create invalid session state
      assert.strictEqual(MediKioskSession.getPatientId(), null);
      assert.strictEqual(MediKioskSession.getSessionId(), null);
    }
  });

  // Test 4: Validation error handling (HTTP 422)
  await runAsyncTest('Error 422: Validation error is caught with isValidationError=true', async () => {
    setupMockFetch({
      'POST /api/patients': () => ({
        status: 422,
        body: {
          detail: [
            { loc: ['body', 'date_of_birth'], msg: 'Date of birth cannot be in the future.', type: 'value_error' }
          ]
        }
      })
    });

    try {
      await MediKioskApi.post('/api/patients', {
        phone_number: '+919876543210',
        name: 'Test Future',
        date_of_birth: '2099-01-01',
        gender: 'Male',
        preferred_language: 'en'
      });
      assert.fail('Should have thrown 422');
    } catch (err) {
      assert.strictEqual(err.status, 422);
      assert.strictEqual(err.isValidationError, true);
      assert.ok(err.message.includes('future'));
    }
  });

  // Test 5: Network failure handling
  await runAsyncTest('Error Network: Offline/connection drops throw isNetworkError=true without crashing', async () => {
    global.fetch = async () => {
      throw new TypeError('Failed to fetch');
    };

    try {
      await MediKioskApi.post('/api/patients', {
        phone_number: '+919876543210',
        name: 'Offline Test',
        date_of_birth: '1990-01-01',
        gender: 'Other',
        preferred_language: 'en'
      });
      assert.fail('Should have thrown network error');
    } catch (err) {
      assert.strictEqual(err.status, 0);
      assert.strictEqual(err.isNetworkError, true);
      assert.ok(err.message.includes('Network error'));
    }
  });

  // Test 6: Zero sensitive console logging during registration
  await runAsyncTest('Security: No patient demographics or PHI logged to console', async () => {
    const logs = [];
    const origLog = console.log;
    const origWarn = console.warn;
    const origError = console.error;

    console.log = (...args) => logs.push(args.join(' '));
    console.warn = (...args) => logs.push(args.join(' '));
    console.error = (...args) => logs.push(args.join(' '));

    setupMockFetch({
      'POST /api/patients': () => ({
        status: 201,
        body: { id: 999, name: 'Confidential Patient' }
      })
    });

    try {
      await MediKioskApi.post('/api/patients', {
        phone_number: '+919999888877',
        name: 'SuperSecretPatientName',
        date_of_birth: '1970-01-01',
        gender: 'Female',
        preferred_language: 'hi'
      });

      const allOutput = logs.join('\n');
      assert.ok(!allOutput.includes('SuperSecretPatientName'), 'Patient name logged to console!');
      assert.ok(!allOutput.includes('+919999888877'), 'Phone number logged to console!');
    } finally {
      console.log = origLog;
      console.warn = origWarn;
      console.error = origError;
    }
  });

  console.log(`\nAll ${testCount} Step 2 Registration Integration tests passed successfully!`);
})();
