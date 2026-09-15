/**
 * Step 1 Foundation Unit & Security Verification
 * Tests config.js, session.js, and api.js using mocked fetch without touching live backend.
 */

const assert = require('assert');

// Mock browser global environment for Node
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

// Load modules
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

console.log('Running MediKiosk Step 1 Foundation Test Suite...\n');

// 1. Config tests
test('Config: defaults to http://127.0.0.1:8000', () => {
  assert.strictEqual(MediKioskConfig.getApiBaseUrl(), 'http://127.0.0.1:8000');
});

test('Config: handles trailing slashes cleanly', () => {
  MediKioskConfig.setApiBaseUrl('http://localhost:8000///');
  assert.strictEqual(MediKioskConfig.getApiBaseUrl(), 'http://localhost:8000');
  MediKioskConfig.setApiBaseUrl('http://127.0.0.1:8000'); // reset
});

// 2. Session state tests
test('Session: set, get, and clear auth token', () => {
  MediKioskSession.clearAuthToken();
  assert.strictEqual(MediKioskSession.getAuthToken(), null);

  MediKioskSession.setAuthToken('test-jwt-token-xyz');
  assert.strictEqual(MediKioskSession.getAuthToken(), 'test-jwt-token-xyz');

  MediKioskSession.clearAuthToken();
  assert.strictEqual(MediKioskSession.getAuthToken(), null);
});

test('Session: patient_id, session_id, interview_id lifecycles', () => {
  MediKioskSession.setPatientId('pat-uuid-001');
  MediKioskSession.setSessionId('sess-uuid-002');
  MediKioskSession.setInterviewId('intv-uuid-003');

  assert.strictEqual(MediKioskSession.getPatientId(), 'pat-uuid-001');
  assert.strictEqual(MediKioskSession.getSessionId(), 'sess-uuid-002');
  assert.strictEqual(MediKioskSession.getInterviewId(), 'intv-uuid-003');

  const summary = MediKioskSession.getWorkflowSummary();
  assert.strictEqual(summary.patientId, 'pat-uuid-001');
  assert.strictEqual(summary.sessionId, 'sess-uuid-002');
  assert.strictEqual(summary.interviewId, 'intv-uuid-003');

  MediKioskSession.clearWorkflowState();
  assert.strictEqual(MediKioskSession.getPatientId(), null);
  assert.strictEqual(MediKioskSession.getSessionId(), null);
  assert.strictEqual(MediKioskSession.getInterviewId(), null);
  assert.strictEqual(MediKioskSession.getAuthToken(), null);
});

// 3. API Client fetch tests with mock fetch
(async () => {
  let lastFetchCall = null;

  function mockFetch(status, responseData, headers = {}) {
    return async (url, options) => {
      lastFetchCall = { url, options };
      return {
        status: status,
        ok: status >= 200 && status < 300,
        headers: {
          get: (headerName) => {
            const h = headerName.toLowerCase();
            return headers[h] || (status === 204 ? null : 'application/json');
          }
        },
        json: async () => responseData,
        text: async () => (typeof responseData === 'string' ? responseData : JSON.stringify(responseData))
      };
    };
  }

  // GET request
  await runAsyncTest('API: GET request URL and default headers', async () => {
    global.fetch = mockFetch(200, { success: true });
    MediKioskSession.clearAuthToken();

    const res = await MediKioskApi.get('/api/v1/health');
    assert.strictEqual(res.ok, true);
    assert.strictEqual(res.status, 200);
    assert.deepStrictEqual(res.data, { success: true });
    assert.strictEqual(lastFetchCall.url, 'http://127.0.0.1:8000/api/v1/health');
    assert.strictEqual(lastFetchCall.options.method, 'GET');
    assert.strictEqual(lastFetchCall.options.headers['Authorization'], undefined);
    assert.strictEqual(lastFetchCall.options.headers['Accept'], 'application/json');
  });

  // POST JSON request
  await runAsyncTest('API: POST JSON serializes body and sets Content-Type', async () => {
    global.fetch = mockFetch(201, { id: 'created-123' });
    const payload = { abha_number: '12-3456-7890-1234' };

    const res = await MediKioskApi.post('/api/v1/patients/verify', payload);
    assert.strictEqual(res.ok, true);
    assert.strictEqual(res.status, 201);
    assert.strictEqual(lastFetchCall.options.method, 'POST');
    assert.strictEqual(lastFetchCall.options.headers['Content-Type'], 'application/json');
    assert.strictEqual(lastFetchCall.options.body, JSON.stringify(payload));
  });

  // FormData request
  await runAsyncTest('API: postForm does not override Content-Type (leaves for boundary)', async () => {
    global.fetch = mockFetch(200, { doc_id: 'doc-456' });
    const formData = new FormData();
    formData.append('document_type', 'prescription');

    const res = await MediKioskApi.postForm('/api/v1/documents/upload', formData);
    assert.strictEqual(res.ok, true);
    assert.strictEqual(lastFetchCall.options.headers['Content-Type'], undefined);
    assert.strictEqual(lastFetchCall.options.body, formData);
  });

  // Authorization header injection
  await runAsyncTest('API: Automatic Authorization: Bearer <token> when token in session', async () => {
    global.fetch = mockFetch(200, { user: 'patient' });
    MediKioskSession.setAuthToken('sample-bearer-jwt-token-999');

    await MediKioskApi.get('/api/v1/patients/me');
    assert.strictEqual(lastFetchCall.options.headers['Authorization'], 'Bearer sample-bearer-jwt-token-999');

    MediKioskSession.clearAuthToken();
    await MediKioskApi.get('/api/v1/public/info');
    assert.strictEqual(lastFetchCall.options.headers['Authorization'], undefined);
  });

  // 204 No Content
  await runAsyncTest('API: Handles 204 No Content safely', async () => {
    global.fetch = mockFetch(204, null);
    const res = await MediKioskApi.delete('/api/v1/session/current');
    assert.strictEqual(res.status, 204);
    assert.strictEqual(res.ok, true);
    assert.strictEqual(res.data, null);
  });

  // Error mappings: 400, 401, 403, 404, 409, 422, 429, 500, network error
  const statusTestCases = [
    { code: 400, prop: 'isClientError' },
    { code: 401, prop: 'isAuthError' },
    { code: 403, prop: 'isForbidden' },
    { code: 404, prop: 'isNotFound' },
    { code: 409, prop: 'isConflict' },
    { code: 422, prop: 'isValidationError' },
    { code: 429, prop: 'isRateLimit' },
    { code: 500, prop: 'isServerError' },
  ];

  for (const { code, prop } of statusTestCases) {
    await runAsyncTest(`API Error: Status ${code} sets ${prop}=true`, async () => {
      global.fetch = mockFetch(code, { detail: `Error detail for ${code}` });
      try {
        await MediKioskApi.get(`/api/test/${code}`);
        assert.fail(`Should have thrown for ${code}`);
      } catch (err) {
        assert.strictEqual(err.name, 'ApiError');
        assert.strictEqual(err.status, code);
        assert.strictEqual(err[prop], true);
        assert.strictEqual(err.message, `Error detail for ${code}`);
      }
    });
  }

  // Network failure test
  await runAsyncTest('API Error: Network failure throws with isNetworkError=true and status 0', async () => {
    global.fetch = async () => {
      throw new TypeError('Failed to fetch');
    };
    try {
      await MediKioskApi.get('/api/test/offline');
      assert.fail('Should have thrown network error');
    } catch (err) {
      assert.strictEqual(err.name, 'ApiError');
      assert.strictEqual(err.status, 0);
      assert.strictEqual(err.isNetworkError, true);
      assert.ok(err.message.includes('Network error'));
    }
  });

  // Security test: Verify zero sensitive console logging
  await runAsyncTest('Security: No tokens or secrets logged to console', async () => {
    const loggedOutputs = [];
    const origLog = console.log;
    const origWarn = console.warn;
    const origError = console.error;

    console.log = (...args) => loggedOutputs.push(args.join(' '));
    console.warn = (...args) => loggedOutputs.push(args.join(' '));
    console.error = (...args) => loggedOutputs.push(args.join(' '));

    try {
      MediKioskSession.setAuthToken('secret-super-confidential-token-12345');
      global.fetch = mockFetch(200, { secretData: 'phi-clinical-information' });

      await MediKioskApi.post('/api/v1/patient/clinical', { diagnosis: 'Hypertension' });

      const allLogs = loggedOutputs.join('\n');
      assert.ok(!allLogs.includes('secret-super-confidential-token-12345'), 'Token found in console log!');
      assert.ok(!allLogs.includes('phi-clinical-information'), 'Response body found in console log!');
      assert.ok(!allLogs.includes('Hypertension'), 'Request body found in console log!');
    } finally {
      console.log = origLog;
      console.warn = origWarn;
      console.error = origError;
      MediKioskSession.clearWorkflowState();
    }
  });

  console.log(`\nAll ${testCount} Step 1 Foundation tests passed successfully!`);
})();
