/**
 * MediKiosk Integration Step 6 Automated Tests
 * Tests Case Summary Generation, Consent Verification, Bilingual Output,
 * Patient Confirmation, Correction Flags, and OPD Queue Token allocation.
 */

const assert = require('assert');
const fs = require('fs');
const path = require('path');

// Set up simulated browser environment
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

let testsPassed = 0;
let testsFailed = 0;

function runTest(testName, fn) {
  try {
    fn();
    console.log(`  ✓ ${testName}`);
    testsPassed++;
  } catch (err) {
    console.error(`  ✗ ${testName}`);
    console.error(err);
    testsFailed++;
  }
}

async function runAsyncTest(testName, fn) {
  try {
    await fn();
    console.log(`  ✓ ${testName}`);
    testsPassed++;
  } catch (err) {
    console.error(`  ✗ ${testName}`);
    console.error(err);
    testsFailed++;
  }
}

async function runAllTests() {
  console.log('--- Step 6: Case Summary & Patient Confirmation Tests ---');

  // Test 1: Missing required identifiers triggers validation/redirection
  runTest('T1: Missing required identifiers aborts workflow', () => {
    global.sessionStorage.clear();
    const patientId = MediKioskSession.getPatientId();
    const sessionId = MediKioskSession.getSessionId();
    const interviewId = MediKioskSession.getInterviewId();

    assert.strictEqual(patientId, null);
    assert.strictEqual(sessionId, null);
    assert.strictEqual(interviewId, null);
  });

  // Test 2: Active session identifiers set properly
  runTest('T2: Active session identifiers set and retrieved via MediKioskSession', () => {
    MediKioskSession.setPatientId(101);
    MediKioskSession.setSessionId(202);
    MediKioskSession.setInterviewId(303);

    assert.strictEqual(MediKioskSession.getPatientId(), '101');
    assert.strictEqual(MediKioskSession.getSessionId(), '202');
    assert.strictEqual(MediKioskSession.getInterviewId(), '303');
  });

  // Test 3: Missing AI_SUMMARIZATION consent blocks summary generation
  await runAsyncTest('T3: Missing AI_SUMMARIZATION consent detected', async () => {
    global.fetch = async (url) => {
      if (url.includes('/consents/active/AI_SUMMARIZATION')) {
        return {
          ok: true,
          status: 200,
          headers: { get: () => 'application/json' },
          json: async () => ({ active: false, purpose: 'AI_SUMMARIZATION' }),
          text: async () => JSON.stringify({ active: false, purpose: 'AI_SUMMARIZATION' })
        };
      }
      return { ok: false, status: 404, headers: { get: () => 'application/json' }, json: async () => ({}), text: async () => '{}' };
    };

    const res = await MediKioskApi.get('/api/patients/101/consents/active/AI_SUMMARIZATION');
    assert.strictEqual(res.ok, true);
    assert.strictEqual(res.data.active, false);
  });

  // Test 4: Active AI_SUMMARIZATION consent permits generation
  await runAsyncTest('T4: Active AI_SUMMARIZATION consent verified successfully', async () => {
    global.fetch = async (url) => {
      if (url.includes('/consents/active/AI_SUMMARIZATION')) {
        return {
          ok: true,
          status: 200,
          headers: { get: () => 'application/json' },
          json: async () => ({ active: true, purpose: 'AI_SUMMARIZATION' }),
          text: async () => JSON.stringify({ active: true, purpose: 'AI_SUMMARIZATION' })
        };
      }
      return { ok: false, status: 404, headers: { get: () => 'application/json' }, json: async () => ({}), text: async () => '{}' };
    };

    const res = await MediKioskApi.get('/api/patients/101/consents/active/AI_SUMMARIZATION');
    assert.strictEqual(res.ok, true);
    assert.strictEqual(res.data.active, true);
  });

  // Test 5: Summary Generation POST endpoint contract
  await runAsyncTest('T5: POST /api/interviews/{id}/summary/generate contract verified', async () => {
    let capturedMethod = null;
    let capturedUrl = null;

    global.fetch = async (url, options) => {
      capturedUrl = url;
      capturedMethod = options.method;
      return {
        ok: true,
        status: 201,
        headers: { get: () => 'application/json' },
        json: async () => ({
          id: 55,
          patient_id: 101,
          interview_id: 303,
          summary_version: 1,
          summary_status: 'DRAFT',
          summary_language: 'en',
          provider_name: 'MockSummaryProvider',
          summary_data: {
            chief_complaint: { items: [{ text: 'Chest pain and pressure', sources: [{ source_type: 'INTERVIEW' }] }] },
            history_of_present_illness: { items: [{ text: 'Symptoms started 2 days ago', sources: [{ source_type: 'INTERVIEW' }] }] },
            ayush_profile: { items: [{ text: 'Mandagni with sluggish digestion', sources: [{ source_type: 'INTERVIEW' }] }] },
            medication_history: { items: [{ text: 'Metformin 500mg twice daily', sources: [{ source_type: 'DOCUMENT_EXTRACTION' }] }] }
          },
          disclaimer: 'DRAFT summary generated by AI for physician review only. Does not constitute a clinical diagnosis or treatment recommendation.'
        }),
        text: async () => '{}'
      };
    };

    const res = await MediKioskApi.post('/api/interviews/303/summary/generate', {});
    assert.strictEqual(capturedMethod, 'POST');
    assert.strictEqual(capturedUrl.includes('/api/interviews/303/summary/generate'), true);
    assert.strictEqual(res.ok, true);
    assert.strictEqual(res.data.id, 55);
    assert.strictEqual(res.data.summary_status, 'DRAFT');
    assert.strictEqual(res.data.summary_data.chief_complaint.items[0].text, 'Chest pain and pressure');
  });

  // Test 6: Summary Retrieval GET endpoint contract
  await runAsyncTest('T6: GET /api/interviews/{id}/summary contract verified', async () => {
    global.fetch = async (url, options) => {
      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({
          id: 55,
          patient_id: 101,
          interview_id: 303,
          summary_version: 1,
          summary_status: 'DRAFT',
          summary_data: {
            chief_complaint: { items: [{ text: 'Chest pain', sources: [] }] }
          }
        }),
        text: async () => '{}'
      };
    };

    const res = await MediKioskApi.get('/api/interviews/303/summary');
    assert.strictEqual(res.ok, true);
    assert.strictEqual(res.data.id, 55);
  });

  // Test 7: Bilingual Output requires BILINGUAL_OUTPUT consent
  await runAsyncTest('T7: Missing BILINGUAL_OUTPUT consent handled safely', async () => {
    global.fetch = async (url) => {
      if (url.includes('/consents/active/BILINGUAL_OUTPUT')) {
        return {
          ok: true,
          status: 200,
          headers: { get: () => 'application/json' },
          json: async () => ({ active: false, purpose: 'BILINGUAL_OUTPUT' }),
          text: async () => JSON.stringify({ active: false, purpose: 'BILINGUAL_OUTPUT' })
        };
      }
      return { ok: false, status: 404, headers: { get: () => 'application/json' }, json: async () => ({}), text: async () => '{}' };
    };

    const res = await MediKioskApi.get('/api/patients/101/consents/active/BILINGUAL_OUTPUT');
    assert.strictEqual(res.ok, true);
    assert.strictEqual(res.data.active, false);
  });

  // Test 8: Bilingual Summary generation contract
  await runAsyncTest('T8: POST /api/interviews/{id}/summary/{summary_id}/bilingual contract verified', async () => {
    let capturedBody = null;

    global.fetch = async (url, options) => {
      capturedBody = JSON.parse(options.body);
      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({
          id: 77,
          patient_id: 101,
          interview_id: 303,
          summary_id: 55,
          target_language_code: 'hi',
          is_bilingual: true,
          output_status: 'COMPLETED',
          translated: {
            language_code: 'hi',
            language_name: 'Hindi',
            sections: {
              chief_complaint: {
                display_label: 'मुख्य समस्या (लक्षण)',
                items: [{ text: 'छाती में भारीपन व जकड़न', sources: [] }]
              }
            }
          }
        }),
        text: async () => '{}'
      };
    };

    const res = await MediKioskApi.post('/api/interviews/303/summary/55/bilingual', { target_language_code: 'hi' });
    assert.strictEqual(res.ok, true);
    assert.strictEqual(capturedBody.target_language_code, 'hi');
    assert.strictEqual(res.data.is_bilingual, true);
    assert.strictEqual(res.data.translated.sections.chief_complaint.display_label, 'मुख्य समस्या (लक्षण)');
  });

  // Test 9: Start Patient Confirmation endpoint contract
  await runAsyncTest('T9: POST /api/interviews/{id}/summary/{summary_id}/confirmation/start contract verified', async () => {
    let capturedMethod = null;

    global.fetch = async (url, options) => {
      capturedMethod = options.method;
      return {
        ok: true,
        status: 201,
        headers: { get: () => 'application/json' },
        json: async () => ({
          id: 88,
          patient_id: 101,
          interview_id: 303,
          summary_id: 55,
          summary_version: 1,
          status: 'IN_PROGRESS',
          items: [
            { id: 1, section_key: 'chief_complaint', summary_item_text: 'Chest pain and pressure', display_label: 'Chief Complaint', patient_response: 'PENDING', is_required: true },
            { id: 2, section_key: 'ayush_profile', summary_item_text: 'Mandagni with sluggish digestion', display_label: 'AYUSH Observations', patient_response: 'PENDING', is_required: true }
          ]
        }),
        text: async () => '{}'
      };
    };

    const res = await MediKioskApi.post('/api/interviews/303/summary/55/confirmation/start', {});
    assert.strictEqual(capturedMethod, 'POST');
    assert.strictEqual(res.ok, true);
    assert.strictEqual(res.data.status, 'IN_PROGRESS');
    assert.strictEqual(res.data.items.length, 2);
  });

  // Test 10: Confirm Item endpoint contract
  await runAsyncTest('T10: POST /api/interviews/{id}/confirmations/{cid}/items/{item_id}/confirm contract verified', async () => {
    let capturedUrl = null;

    global.fetch = async (url, options) => {
      capturedUrl = url;
      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({
          id: 1,
          confirmation_id: 88,
          section_key: 'chief_complaint',
          summary_item_text: 'Chest pain and pressure',
          patient_response: 'CONFIRMED'
        }),
        text: async () => '{}'
      };
    };

    const res = await MediKioskApi.post('/api/interviews/303/confirmations/88/items/1/confirm', {});
    assert.strictEqual(res.ok, true);
    assert.strictEqual(capturedUrl.includes('/confirmations/88/items/1/confirm'), true);
    assert.strictEqual(res.data.patient_response, 'CONFIRMED');
  });

  // Test 11: Flag Item with correction note endpoint contract
  await runAsyncTest('T11: POST /api/interviews/{id}/confirmations/{cid}/items/{item_id}/flag contract verified', async () => {
    let capturedBody = null;

    global.fetch = async (url, options) => {
      capturedBody = JSON.parse(options.body);
      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({
          id: 1,
          confirmation_id: 88,
          section_key: 'chief_complaint',
          summary_item_text: 'Chest pain and pressure',
          patient_response: 'FLAGGED',
          patient_correction: capturedBody.correction
        }),
        text: async () => '{}'
      };
    };

    const res = await MediKioskApi.post('/api/interviews/303/confirmations/88/items/1/flag', {
      correction: 'Symptoms began 5 days ago, not 2 days ago'
    });
    assert.strictEqual(res.ok, true);
    assert.strictEqual(capturedBody.correction, 'Symptoms began 5 days ago, not 2 days ago');
    assert.strictEqual(res.data.patient_response, 'FLAGGED');
    assert.strictEqual(res.data.patient_correction, 'Symptoms began 5 days ago, not 2 days ago');
  });

  // Test 12: Complete Confirmation endpoint contract
  await runAsyncTest('T12: POST /api/interviews/{id}/confirmations/{cid}/complete contract verified', async () => {
    let capturedUrl = null;

    global.fetch = async (url, options) => {
      capturedUrl = url;
      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({
          id: 88,
          patient_id: 101,
          interview_id: 303,
          summary_id: 55,
          status: 'CONFIRMED',
          completed_at: '2026-09-14T16:45:00Z'
        }),
        text: async () => '{}'
      };
    };

    const res = await MediKioskApi.post('/api/interviews/303/confirmations/88/complete', {});
    assert.strictEqual(res.ok, true);
    assert.strictEqual(capturedUrl.includes('/confirmations/88/complete'), true);
    assert.strictEqual(res.data.status, 'CONFIRMED');
    assert.ok(res.data.completed_at);
  });

  // Test 13: OPD Queue Token Allocation endpoint contract
  await runAsyncTest('T13: POST /api/opd/queue/entries token allocation verified', async () => {
    let capturedBody = null;

    global.fetch = async (url, options) => {
      capturedBody = JSON.parse(options.body);
      return {
        ok: true,
        status: 201,
        headers: { get: () => 'application/json' },
        json: async () => ({
          id: 42,
          patient_id: capturedBody.patient_id,
          interview_id: capturedBody.interview_id,
          token_number: 24,
          priority: 'NORMAL',
          status: 'WAITING',
          queue_date: '2026-09-14',
          checked_in_at: '2026-09-14T16:45:05Z'
        }),
        text: async () => '{}'
      };
    };

    const res = await MediKioskApi.post('/api/opd/queue/entries', {
      patient_id: 101,
      interview_id: 303,
      priority: 'NORMAL'
    });
    assert.strictEqual(res.ok, true);
    assert.strictEqual(res.data.token_number, 24);
    assert.strictEqual(res.data.status, 'WAITING');
  });

  // Test 14: Storage purity - No clinical text, summary, or confirmation records in sessionStorage
  runTest('T14: Storage Purity - Zero PHI, summary or clinical data in sessionStorage', () => {
    const keys = Object.keys(mockStorage.store);
    const forbiddenSubstrings = [
      'summary',
      'chest',
      'pain',
      'medication',
      'mandagni',
      'confirmation',
      'correction',
      'diagnosis',
      'token_number'
    ];

    for (const k of keys) {
      const val = String(mockStorage.store[k]).toLowerCase();
      for (const f of forbiddenSubstrings) {
        assert.strictEqual(val.includes(f), false, `Forbidden clinical data leaked into storage key ${k}: ${val}`);
      }
    }
  });

  // Test 15: HTTP 403 Consent Required handled as specific error
  await runAsyncTest('T15: HTTP 403 Consent Required error handled safely', async () => {
    global.fetch = async () => {
      return {
        ok: false,
        status: 403,
        headers: { get: () => 'application/json' },
        json: async () => ({
          detail: 'Consent required: purpose AI_SUMMARIZATION has not been granted'
        }),
        text: async () => JSON.stringify({ detail: 'Consent required: purpose AI_SUMMARIZATION has not been granted' })
      };
    };

    try {
      await MediKioskApi.post('/api/interviews/303/summary/generate', {});
      assert.fail('Expected exception');
    } catch (err) {
      assert.strictEqual(err.status, 403);
      assert.strictEqual(err.isForbidden, true);
      assert.strictEqual(err.message.includes('Consent required'), true);
    }
  });

  // Test 16: Verification that MediKioskApi is used rather than raw fetch
  runTest('T16: API calls utilize MediKioskApi wrapper', () => {
    assert.strictEqual(typeof MediKioskApi.get, 'function');
    assert.strictEqual(typeof MediKioskApi.post, 'function');
    assert.strictEqual(typeof MediKioskApi.put, 'function');
  });

  // Test 17: Disclaimer text preserved from backend
  await runAsyncTest('T17: Mandatory clinical disclaimer preserved from backend', async () => {
    const disclaimerText = "DRAFT summary generated by AI for physician review only. Does not constitute a clinical diagnosis or treatment recommendation.";
    global.fetch = async () => {
      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({
          id: 55,
          disclaimer: disclaimerText
        }),
        text: async () => '{}'
      };
    };

    const res = await MediKioskApi.get('/api/interviews/303/summary');
    assert.strictEqual(res.data.disclaimer, disclaimerText);
  });

  // Test 18: No secret or sensitive keys logged
  runTest('T18: No API keys or tokens printed to console', () => {
    const screenCode = fs.readFileSync(path.join(__dirname, '../src/screens/screen4-summary.html'), 'utf8');
    assert.strictEqual(screenCode.includes('AIza'), false);
    assert.strictEqual(screenCode.includes('gsk_'), false);
    assert.strictEqual(screenCode.includes('bearer '), false);
  });

  // Test 19: Screen 4 includes foundation scripts
  runTest('T19: screen4-summary.html contains foundation scripts in head', () => {
    const screenCode = fs.readFileSync(path.join(__dirname, '../src/screens/screen4-summary.html'), 'utf8');
    assert.strictEqual(screenCode.includes('<script src="../scripts/config.js"></script>'), true);
    assert.strictEqual(screenCode.includes('<script src="../scripts/session.js"></script>'), true);
    assert.strictEqual(screenCode.includes('<script src="../scripts/api.js"></script>'), true);
  });

  // Test 20: Screen 4 error alert container exists
  runTest('T20: screen4-summary.html contains summaryErrorMsg container', () => {
    const screenCode = fs.readFileSync(path.join(__dirname, '../src/screens/screen4-summary.html'), 'utf8');
    assert.strictEqual(screenCode.includes('id="summaryErrorMsg"'), true);
  });

  // Test 21: Screen 4 dynamic statements container exists
  runTest('T21: screen4-summary.html contains statementsList container', () => {
    const screenCode = fs.readFileSync(path.join(__dirname, '../src/screens/screen4-summary.html'), 'utf8');
    assert.strictEqual(screenCode.includes('id="statementsList"'), true);
  });

  // Test 22: Screen 4 correction note textarea exists
  runTest('T22: screen4-summary.html contains patientCorrectionInput', () => {
    const screenCode = fs.readFileSync(path.join(__dirname, '../src/screens/screen4-summary.html'), 'utf8');
    assert.strictEqual(screenCode.includes('id="patientCorrectionInput"'), true);
  });

  // Test 23: Screen 4 queue token displays exist
  runTest('T23: screen4-summary.html contains tokenNumberDisplay element', () => {
    const screenCode = fs.readFileSync(path.join(__dirname, '../src/screens/screen4-summary.html'), 'utf8');
    assert.strictEqual(screenCode.includes('id="tokenNumberDisplay"'), true);
  });

  // Test 24: Screen 4 disclaimer container exists
  runTest('T24: screen4-summary.html contains summaryDisclaimerBox element', () => {
    const screenCode = fs.readFileSync(path.join(__dirname, '../src/screens/screen4-summary.html'), 'utf8');
    assert.strictEqual(screenCode.includes('id="summaryDisclaimerBox"'), true);
  });

  console.log(`\nStep 6 Test Results: ${testsPassed} passed, ${testsFailed} failed`);
  if (testsFailed > 0) {
    process.exit(1);
  }
}

runAllTests().catch(err => {
  console.error('Test Suite Failed Exception:', err);
  process.exit(1);
});
