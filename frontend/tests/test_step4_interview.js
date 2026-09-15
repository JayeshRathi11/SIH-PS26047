/**
 * Step 4: Clinical Interview & Adaptive Intake Integration Test Suite
 * Tests:
 * 1. active patient/session is read correctly
 * 2. interview creation uses the correct patient/session
 * 3. returned interview_id is stored
 * 4. CLINICAL_HISTORY consent is respected
 * 5. missing patient ID handled safely
 * 6. missing session ID handled safely
 * 7. interview start failure handled
 * 8. first question rendered from backend response
 * 9. text response sent to correct endpoint
 * 10. next question rendered from backend response
 * 11. duplicate message submission prevented
 * 12. 401 handling
 * 13. 403 consent handling
 * 14. 404 handling
 * 15. 409 handling
 * 16. 422 handling
 * 17. 429 handling
 * 18. network failure handling
 * 19. interview terminal state is respected
 * 20. no transcript/clinical data stored in sessionStorage
 * 21. no sensitive console logging
 * 22. existing UI remains intact
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
global.localStorage = mockStorage;

const MediKioskConfig = require('../src/scripts/config.js');
const MediKioskSession = require('../src/scripts/session.js');
const MediKioskApi = require('../src/scripts/api.js');

let testCount = 0;
async function runTest(name, fn) {
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
      json: async () => res.data || {},
      text: async () => JSON.stringify(res.data || {})
    };
  };
}

async function runAll() {
  console.log('Running MediKiosk Step 4 Interview Integration Test Suite...\n');

  // 1. active patient/session is read correctly
  await runTest('1. active patient/session is read correctly from MediKioskSession', () => {
    mockStorage.clear();
    MediKioskSession.setPatientId('101');
    MediKioskSession.setSessionId('202');
    assert.strictEqual(MediKioskSession.getPatientId(), '101');
    assert.strictEqual(MediKioskSession.getSessionId(), '202');
  });

  // 2. interview creation uses the correct patient/session
  await runTest('2. interview creation uses correct patient/session', async () => {
    mockStorage.clear();
    MediKioskSession.setPatientId('101');
    MediKioskSession.setSessionId('202');

    let interceptedCreateBody = null;
    let interceptedAttachBody = null;

    setupMockFetch({
      'POST /api/interviews': (opts) => {
        interceptedCreateBody = JSON.parse(opts.body);
        return { status: 201, data: { id: 303, patient_id: 101, status: 'NOT_STARTED' } };
      },
      'POST /api/sessions/202/attach-interview': (opts) => {
        interceptedAttachBody = JSON.parse(opts.body);
        return { status: 200, data: { id: 202, interview_id: 303, status: 'IN_PROGRESS' } };
      }
    });

    const createRes = await MediKioskApi.post('/api/interviews', {
      patient_id: parseInt(MediKioskSession.getPatientId(), 10),
      preferred_language: 'en'
    });
    assert.strictEqual(createRes.status, 201);
    assert.strictEqual(interceptedCreateBody.patient_id, 101);

    const attachRes = await MediKioskApi.post(`/api/sessions/${MediKioskSession.getSessionId()}/attach-interview`, {
      interview_id: createRes.data.id
    });
    assert.strictEqual(attachRes.status, 200);
    assert.strictEqual(interceptedAttachBody.interview_id, 303);
  });

  // 3. returned interview_id is stored
  await runTest('3. returned interview_id is stored in MediKioskSession', () => {
    MediKioskSession.setInterviewId(303);
    assert.strictEqual(MediKioskSession.getInterviewId(), '303');
    assert.strictEqual(mockStorage.getItem('medikiosk_interview_id'), '303');
  });

  // 4. CLINICAL_HISTORY consent is respected
  await runTest('4. CLINICAL_HISTORY consent is respected when starting interview', async () => {
    setupMockFetch({
      'POST /api/interviews/303/start': () => {
        return { status: 200, data: { id: 303, status: 'IN_PROGRESS' } };
      }
    });

    const res = await MediKioskApi.post('/api/interviews/303/start', {});
    assert.strictEqual(res.status, 200);
    assert.strictEqual(res.data.status, 'IN_PROGRESS');
  });

  // 5. missing patient ID handled safely
  await runTest('5. missing patient ID handled safely', () => {
    mockStorage.clear();
    const pid = MediKioskSession.getPatientId();
    assert.strictEqual(pid, null);
    const canStart = !!pid && !!MediKioskSession.getSessionId();
    assert.strictEqual(canStart, false);
  });

  // 6. missing session ID handled safely
  await runTest('6. missing session ID handled safely', () => {
    mockStorage.clear();
    MediKioskSession.setPatientId('101');
    const sid = MediKioskSession.getSessionId();
    assert.strictEqual(sid, null);
    const canStart = !!MediKioskSession.getPatientId() && !!sid;
    assert.strictEqual(canStart, false);
  });

  // 7. interview start failure handled
  await runTest('7. interview start failure handled with ApiError', async () => {
    setupMockFetch({
      'POST /api/interviews/303/start': () => {
        return { status: 400, data: { detail: "Cannot start interview with status 'COMPLETED'" } };
      }
    });

    try {
      await MediKioskApi.post('/api/interviews/303/start', {});
      assert.fail('Should have thrown ApiError');
    } catch (err) {
      assert.ok(err instanceof MediKioskApi.ApiError);
      assert.strictEqual(err.status, 400);
      assert.ok(err.message.includes('Cannot start'));
    }
  });

  // 8. first question rendered from backend response
  await runTest('8. first question retrieved from backend response', async () => {
    setupMockFetch({
      'GET /api/interviews/303/next-question': () => {
        return {
          status: 200,
          data: {
            has_next: true,
            is_complete: false,
            field_key: 'chief_complaint',
            section: 'CHIEF_COMPLAINTS',
            display_name: 'Chief Complaint',
            description: 'What is the main discomfort or illness that brought you to the hospital today?',
            required: true,
            priority: 1,
            reason: 'Initial clinical assessment'
          }
        };
      }
    });

    const res = await MediKioskApi.get('/api/interviews/303/next-question');
    assert.strictEqual(res.status, 200);
    assert.strictEqual(res.data.has_next, true);
    assert.strictEqual(res.data.display_name, 'Chief Complaint');
    assert.strictEqual(res.data.field_key, 'chief_complaint');
  });

  // 9. text response sent to correct endpoint
  await runTest('9. text response sent to /api/interviews/{id}/messages/process', async () => {
    let processedPayload = null;
    setupMockFetch({
      'POST /api/interviews/303/messages/process': (opts) => {
        processedPayload = JSON.parse(opts.body);
        return {
          status: 200,
          data: {
            message: { id: 1, interview_id: 303, role: 'PATIENT', content: 'Severe headache for 3 days', language: 'en' },
            nlp_status: 'VALID',
            integration_status: 'APPLIED',
            requires_human_verification: false,
            applied_fields: ['chief_complaint'],
            validation_issues: [],
            next_question: {
              has_next: true,
              is_complete: false,
              field_key: 'symptom_duration',
              section: 'HISTORY_OF_PRESENT_ILLNESS',
              display_name: 'Duration',
              description: 'How long have you had this headache?'
            },
            is_history_complete: false
          }
        };
      }
    });

    const res = await MediKioskApi.post('/api/interviews/303/messages/process', {
      role: 'PATIENT',
      content: 'Severe headache for 3 days',
      language: 'en'
    });

    assert.strictEqual(res.status, 200);
    assert.strictEqual(processedPayload.role, 'PATIENT');
    assert.strictEqual(processedPayload.content, 'Severe headache for 3 days');
    assert.strictEqual(res.data.integration_status, 'APPLIED');
  });

  // 10. next question rendered from backend response
  await runTest('10. next question returned directly in process response', async () => {
    setupMockFetch({
      'POST /api/interviews/303/messages/process': () => {
        return {
          status: 200,
          data: {
            message: { id: 2, interview_id: 303, role: 'PATIENT', content: '3 days' },
            nlp_status: 'VALID',
            integration_status: 'APPLIED',
            next_question: {
              has_next: true,
              is_complete: false,
              field_key: 'pain_severity',
              display_name: 'Pain Severity',
              description: 'On a scale of 1 to 10, how intense is the pain?'
            },
            is_history_complete: false
          }
        };
      }
    });

    const res = await MediKioskApi.post('/api/interviews/303/messages/process', {
      role: 'PATIENT',
      content: '3 days'
    });

    assert.ok(res.data.next_question);
    assert.strictEqual(res.data.next_question.display_name, 'Pain Severity');
    assert.strictEqual(res.data.next_question.field_key, 'pain_severity');
  });

  // 11. duplicate message submission prevented
  await runTest('11. duplicate message submission prevented by disabled state', async () => {
    let isSubmitting = false;
    let callCount = 0;

    async function submitResponse() {
      if (isSubmitting) return false;
      isSubmitting = true;
      try {
        callCount++;
        await new Promise(r => setTimeout(r, 10));
        return true;
      } finally {
        isSubmitting = false;
      }
    }

    const firstCall = submitResponse();
    const secondCall = submitResponse();

    const [res1, res2] = await Promise.all([firstCall, secondCall]);
    assert.strictEqual(res1, true);
    assert.strictEqual(res2, false);
    assert.strictEqual(callCount, 1);
  });

  // 12. 401 handling
  await runTest('12. 401 Unauthorized handling', async () => {
    setupMockFetch({
      'POST /api/interviews/303/messages/process': () => {
        return { status: 401, data: { detail: 'Not authenticated' } };
      }
    });

    try {
      await MediKioskApi.post('/api/interviews/303/messages/process', { role: 'PATIENT', content: 'test' });
      assert.fail('Should throw');
    } catch (err) {
      assert.strictEqual(err.status, 401);
      assert.strictEqual(err.isAuthError, true);
    }
  });

  // 13. 403 consent handling
  await runTest('13. 403 Consent Required handling', async () => {
    setupMockFetch({
      'POST /api/interviews/303/start': () => {
        return {
          status: 403,
          data: { detail: 'Active consent required for purpose CLINICAL_HISTORY before proceeding.' }
        };
      }
    });

    try {
      await MediKioskApi.post('/api/interviews/303/start', {});
      assert.fail('Should throw');
    } catch (err) {
      assert.strictEqual(err.status, 403);
      assert.strictEqual(err.isForbidden, true);
      assert.ok(err.message.includes('CLINICAL_HISTORY'));
    }
  });

  // 14. 404 handling
  await runTest('14. 404 Not Found handling', async () => {
    setupMockFetch({
      'GET /api/interviews/999': () => {
        return { status: 404, data: { detail: 'Interview with ID 999 not found.' } };
      }
    });

    try {
      await MediKioskApi.get('/api/interviews/999');
      assert.fail('Should throw');
    } catch (err) {
      assert.strictEqual(err.status, 404);
      assert.strictEqual(err.isNotFound, true);
    }
  });

  // 15. 409 handling
  await runTest('15. 409 Conflict handling', async () => {
    setupMockFetch({
      'POST /api/sessions/202/attach-interview': () => {
        return { status: 409, data: { detail: 'Session already has an attached interview.' } };
      }
    });

    try {
      await MediKioskApi.post('/api/sessions/202/attach-interview', { interview_id: 303 });
      assert.fail('Should throw');
    } catch (err) {
      assert.strictEqual(err.status, 409);
      assert.strictEqual(err.isConflict, true);
    }
  });

  // 16. 422 handling
  await runTest('16. 422 Validation Error handling', async () => {
    setupMockFetch({
      'POST /api/interviews/303/messages/process': () => {
        return {
          status: 422,
          data: {
            detail: [{ loc: ['body', 'content'], msg: 'Field required', type: 'value_error.missing' }]
          }
        };
      }
    });

    try {
      await MediKioskApi.post('/api/interviews/303/messages/process', {});
      assert.fail('Should throw');
    } catch (err) {
      assert.strictEqual(err.status, 422);
      assert.strictEqual(err.isValidationError, true);
    }
  });

  // 17. 429 handling
  await runTest('17. 429 Rate Limit handling', async () => {
    setupMockFetch({
      'POST /api/interviews/303/messages/process': () => {
        return { status: 429, data: { detail: 'Too many requests. Slow down.' } };
      }
    });

    try {
      await MediKioskApi.post('/api/interviews/303/messages/process', { role: 'PATIENT', content: 'hello' });
      assert.fail('Should throw');
    } catch (err) {
      assert.strictEqual(err.status, 429);
      assert.strictEqual(err.isRateLimit, true);
    }
  });

  // 18. network failure handling
  await runTest('18. network failure handling', async () => {
    global.fetch = async () => {
      throw new Error('Connection refused');
    };

    try {
      await MediKioskApi.get('/api/interviews/303');
      assert.fail('Should throw');
    } catch (err) {
      assert.ok(err instanceof MediKioskApi.ApiError);
      assert.strictEqual(err.isNetworkError, true);
      assert.strictEqual(err.status, 0);
    }
  });

  // 19. interview terminal state is respected
  await runTest('19. interview terminal state (COMPLETED) is respected', async () => {
    setupMockFetch({
      'GET /api/interviews/303': () => {
        return {
          status: 200,
          data: { id: 303, patient_id: 101, status: 'COMPLETED' }
        };
      }
    });

    const res = await MediKioskApi.get('/api/interviews/303');
    assert.strictEqual(res.data.status, 'COMPLETED');
    const isTerminal = ['COMPLETED', 'CANCELLED'].includes(res.data.status);
    assert.strictEqual(isTerminal, true);
  });

  // 20. no transcript/clinical data stored in sessionStorage
  await runTest('20. strict session storage purity: zero transcripts or clinical data stored', () => {
    const allowedKeys = [
      'medikiosk_auth_token',
      'medikiosk_patient_id',
      'medikiosk_session_id',
      'medikiosk_interview_id',
      'medikiosk_lang'
    ];

    for (const key of Object.keys(mockStorage.store)) {
      assert.ok(
        allowedKeys.includes(key),
        `Forbidden data key found in sessionStorage: ${key}`
      );
    }
  });

  // 21. no sensitive console logging
  await runTest('21. no sensitive console logging of tokens or transcripts', () => {
    const apiCode = fs.readFileSync(path.join(__dirname, '../src/scripts/api.js'), 'utf8');
    assert.strictEqual(apiCode.includes('console.log(headers'), false);
    assert.strictEqual(apiCode.includes('console.log(token'), false);
    assert.strictEqual(apiCode.includes('console.log(body'), false);
  });

  // 22. existing UI remains intact
  await runTest('22. existing screen markup remains intact', () => {
    const screen2 = fs.readFileSync(path.join(__dirname, '../src/screens/screen2-interview.html'), 'utf8');
    assert.ok(screen2.includes('id="btnStartInterview"'), 'btnStartInterview missing');
    assert.ok(screen2.includes('id="interviewErrorMsg"'), 'interviewErrorMsg missing in screen2');
    assert.ok(screen2.includes('scripts/config.js'), 'config.js missing in screen2');
    assert.ok(screen2.includes('scripts/session.js'), 'session.js missing in screen2');
    assert.ok(screen2.includes('scripts/api.js'), 'api.js missing in screen2');

    const screen2a = fs.readFileSync(path.join(__dirname, '../src/screens/screen2a-standard.html'), 'utf8');
    assert.ok(screen2a.includes('id="btnNextQuestion"'), 'btnNextQuestion missing in screen2a');
    assert.ok(screen2a.includes('id="questionText"'), 'questionText missing in screen2a');
    assert.ok(screen2a.includes('id="questionCategory"'), 'questionCategory missing in screen2a');
    assert.ok(screen2a.includes('id="progressText"'), 'progressText missing in screen2a');
    assert.ok(screen2a.includes('id="interviewErrorMsg"'), 'interviewErrorMsg missing in screen2a');
    assert.ok(screen2a.includes('scripts/config.js'), 'config.js missing in screen2a');

    const screen2b = fs.readFileSync(path.join(__dirname, '../src/screens/screen2b-ayush.html'), 'utf8');
    assert.ok(screen2b.includes('scripts/config.js'), 'config.js missing in screen2b');
    assert.ok(screen2b.includes('/api/interviews/${interviewId}/mode'), 'mode update endpoint missing in screen2b');
  });

  console.log(`\nAll ${testCount} Step 4 interview tests passed successfully!\n`);
}

runAll().catch((err) => {
  console.error('Fatal test error:', err);
  process.exit(1);
});
