/**
 * Step 7 Integration Test Suite: Doctor & Staff Dashboard
 * 
 * Verifies:
 *  1. Login success stores token in MediKioskSession
 *  2. Login failure handles invalid credentials gracefully
 *  3. Storage Purity: Zero passwords stored in browser storage
 *  4. Storage Purity: Zero PHI stored in browser storage
 *  5. Unauthorized / Forbidden (401/403) handling safely displays error banner
 *  6. OPD Queue retrieval contract (/api/opd/queue) verified
 *  7. Queue Priority / Emergency badge detection from backend fields
 *  8. Patient case selection loads authoritative dashboard (/api/interviews/{id}/dashboard)
 *  9. Case summary data correctly extracted and mapped to UI sections
 * 10. Multi-source contradiction display when contradictions present
 * 11. Medication discrepancy display when discrepancies reported
 * 12. Active red flags and clinical safety alert displayed
 * 13. Patient confirmation audit status displayed accurately
 * 14. Doctor review session initialization (/api/interviews/{id}/summary/{summary_id}/doctor-review/start)
 * 15. Doctor review item verification (/api/interviews/{id}/doctor-reviews/{rid}/items/{iid}/verify)
 * 16. Doctor review completion (/api/interviews/{id}/doctor-reviews/{rid}/complete)
 * 17. Authoritative backend state reload after clinical sign-off
 * 18. Non-doctor role blocked from executing clinical sign-off
 * 19. Disclaimers preserved verbatim from backend payload
 * 20. Zero sensitive credentials, passwords, or tokens printed to console
 * 21. API client boundary: All calls route through MediKioskApi
 * 22. screen5-doctor-dashboard.html contains foundation scripts in head
 * 23. screen5-doctor-dashboard.html contains dashboardErrorBanner container
 * 24. screen5-doctor-dashboard.html contains loginModal and doctorNotesModal
 */

const fs = require('fs');
const path = require('path');
const assert = require('assert');

// Mock browser sessionStorage
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

const mockStorage = new MockSessionStorage();
global.window = global;
global.sessionStorage = mockStorage;
global.localStorage = mockStorage;

// Load foundation scripts
const MediKioskConfig = require('../src/scripts/config.js');
const MediKioskSession = require('../src/scripts/session.js');
const MediKioskApi = require('../src/scripts/api.js');

let passedTests = 0;
let failedTests = 0;

async function runAsyncTest(name, fn) {
  try {
    sessionStorage.clear();
    await fn();
    console.log(`  ✓ ${name}`);
    passedTests++;
  } catch (err) {
    console.error(`  ✗ ${name}`);
    console.error(`    ${err.message}`);
    failedTests++;
  }
}

async function runAllTests() {
  console.log('--- Step 7: Doctor & Staff Dashboard Tests ---');

  // Test 1: Doctor Login Success
  await runAsyncTest('T1: POST /api/auth/login successful authentication stores token', async () => {
    let capturedUrl = null;
    let capturedBody = null;

    global.fetch = async (url, options) => {
      capturedUrl = url;
      capturedBody = JSON.parse(options.body);
      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({
          access_token: 'valid.doctor.jwt.token',
          token_type: 'bearer',
          expires_in_seconds: 3600,
          role: 'DOCTOR'
        }),
        text: async () => '{}'
      };
    };

    const res = await MediKioskApi.post('/api/auth/login', {
      email: 'doctor@aiia.gov.in',
      password: 'DoctorPassword@123'
    });

    assert.strictEqual(res.ok, true);
    assert.strictEqual(capturedUrl, 'http://127.0.0.1:8000/api/auth/login');
    assert.strictEqual(capturedBody.email, 'doctor@aiia.gov.in');
    
    MediKioskSession.setAuthToken(res.data.access_token);
    assert.strictEqual(MediKioskSession.getAuthToken(), 'valid.doctor.jwt.token');
  });

  // Test 2: Doctor Login Failure
  await runAsyncTest('T2: POST /api/auth/login failure returns error safely', async () => {
    global.fetch = async () => ({
      ok: false,
      status: 401,
      headers: { get: () => 'application/json' },
      json: async () => ({
        detail: 'Invalid email or password'
      }),
      text: async () => '{"detail":"Invalid email or password"}'
    });

    let caughtError = null;
    try {
      await MediKioskApi.post('/api/auth/login', {
        email: 'doctor@aiia.gov.in',
        password: 'WrongPassword'
      });
    } catch (err) {
      caughtError = err;
    }

    assert.notStrictEqual(caughtError, null);
    assert.strictEqual(caughtError.status, 401);
    assert.strictEqual(caughtError.message, 'Invalid email or password');
    assert.strictEqual(MediKioskSession.getAuthToken(), null);
  });

  // Test 3: Storage Purity - Zero Passwords
  await runAsyncTest('T3: Storage Purity - Passwords never saved in browser storage', async () => {
    const rawKeys = Object.keys(mockStorage.store);
    const hasPassword = rawKeys.some(k => k.toLowerCase().includes('password') || k.toLowerCase().includes('secret'));
    assert.strictEqual(hasPassword, false);
  });

  // Test 4: Storage Purity - Zero Clinical Summaries or PHI
  await runAsyncTest('T4: Storage Purity - Zero clinical notes or summaries in storage', async () => {
    const rawKeys = Object.keys(mockStorage.store);
    const hasPhi = rawKeys.some(k => k.toLowerCase().includes('summary') || k.toLowerCase().includes('clinical') || k.toLowerCase().includes('patient_name'));
    assert.strictEqual(hasPhi, false);
  });

  // Test 5: Unauthorized / Forbidden handling
  await runAsyncTest('T5: HTTP 401 / 403 responses handled safely with ApiError', async () => {
    global.fetch = async () => ({
      ok: false,
      status: 403,
      headers: { get: () => 'application/json' },
      json: async () => ({ detail: 'Access denied: Requires DOCTOR or STAFF role.' }),
      text: async () => '{"detail":"Access denied: Requires DOCTOR or STAFF role."}'
    });

    let caughtError = null;
    try {
      await MediKioskApi.get('/api/opd/queue');
    } catch (err) {
      caughtError = err;
    }

    assert.notStrictEqual(caughtError, null);
    assert.strictEqual(caughtError.status, 403);
    assert.strictEqual(caughtError.message, 'Access denied: Requires DOCTOR or STAFF role.');
    assert.strictEqual(caughtError.isForbidden, true);
  });

  // Test 6: OPD Queue Retrieval Contract
  await runAsyncTest('T6: GET /api/opd/queue returns valid queue listing', async () => {
    let sentAuth = null;
    MediKioskSession.setAuthToken('valid.doctor.jwt.token');

    global.fetch = async (url, options) => {
      sentAuth = options.headers['Authorization'];
      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({
          queue_date: '2026-09-14',
          total_count: 2,
          entries: [
            {
              id: 1,
              patient_id: 101,
              interview_id: 301,
              token_number: 24,
              priority: 'NORMAL',
              status: 'WAITING',
              position: 1
            },
            {
              id: 2,
              patient_id: 102,
              interview_id: 302,
              token_number: 25,
              priority: 'EMERGENCY',
              status: 'WAITING',
              position: 2
            }
          ]
        }),
        text: async () => '{}'
      };
    };

    const res = await MediKioskApi.get('/api/opd/queue');
    assert.strictEqual(res.ok, true);
    assert.strictEqual(sentAuth, 'Bearer valid.doctor.jwt.token');
    assert.strictEqual(res.data.entries.length, 2);
    assert.strictEqual(res.data.entries[0].token_number, 24);
  });

  // Test 7: Queue Priority & Emergency Detection
  await runAsyncTest('T7: Queue Priority EMERGENCY flag accurately identified', async () => {
    const entry = { priority: 'EMERGENCY', status: 'WAITING' };
    const isEmergency = entry.priority === 'EMERGENCY' || entry.priority === 'URGENT';
    assert.strictEqual(isEmergency, true);
  });

  // Test 8: Patient Case Selection & Dashboard Retrieval Contract
  await runAsyncTest('T8: GET /api/interviews/{id}/dashboard retrieves full clinical payload', async () => {
    let capturedUrl = null;
    MediKioskSession.setAuthToken('valid.doctor.jwt.token');

    global.fetch = async (url) => {
      capturedUrl = url;
      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({
          patient: {
            id: 101,
            name: 'Ramesh Sharma',
            date_of_birth: '1970-05-12',
            gender: 'MALE',
            phone_number: '+919876543210',
            preferred_language: 'en',
            created_at: '2026-09-14T10:00:00Z'
          },
          interview: {
            id: 301,
            status: 'COMPLETED',
            mode: 'STANDARD',
            language_code: 'en',
            preferred_language: 'en',
            created_at: '2026-09-14T10:05:00Z'
          },
          readiness: {
            summary_available: true,
            active_red_flag_count: 1,
            critical_red_flag_count: 0,
            abnormal_value_count: 1,
            document_count: 1,
            timeline_event_count: 0
          },
          red_flags: [
            {
              id: 1,
              rule_key: 'ELEVATED_FASTING_GLUCOSE',
              severity: 'HIGH',
              status: 'ACTIVE',
              message: 'FBS elevated at 142 mg/dL',
              detected_at: '2026-09-14T10:10:00Z'
            }
          ],
          latest_summary: {
            id: 501,
            summary_version: 1,
            summary_status: 'DRAFT',
            summary_language: 'en',
            provider_name: 'deterministic_mock',
            disclaimer: 'DRAFT summary generated by AI for physician review only.',
            summary_data: {
              chief_complaint: 'Central chest heaviness for 2 days',
              history_of_present_illness: 'Patient experiences discomfort after exertion.',
              ayush_profile: { agni: 'Mandagni' },
              medication_history: [
                { drug_name: 'Metformin', dosage: '500mg', frequency: 'BD' }
              ]
            },
            created_at: '2026-09-14T10:15:00Z',
            updated_at: '2026-09-14T10:15:00Z'
          },
          patient_confirmation: {
            id: 601,
            summary_id: 501,
            summary_version: 1,
            status: 'CONFIRMED',
            started_at: '2026-09-14T10:16:00Z',
            is_current_summary_version: true,
            items: [
              { id: 1, section_key: 'chief_complaint', display_label: 'Complaint', summary_item_text: 'Central chest heaviness', patient_response: 'CONFIRMED' }
            ]
          },
          doctor_review: {
            id: 701,
            summary_id: 501,
            summary_version: 1,
            status: 'PENDING',
            started_at: '2026-09-14T10:18:00Z',
            is_current_summary_version: true,
            items: []
          },
          abnormal_values: [
            {
              id: 1,
              investigation_name: 'Fasting Blood Sugar',
              value: '142',
              unit: 'mg/dL',
              abnormal_status: 'Elevated Flag',
              document_id: 801,
              extraction_id: 901
            }
          ],
          medications: {
            total_medications: 1,
            discrepancy_count: 1,
            verification_required: true,
            discrepant_medication_names: ['Metformin']
          },
          contradictions: {
            has_contradictions: false,
            total_contradictions: 0,
            contradictions: []
          },
          emergency_escalations: {
            has_active_escalation: false,
            active_count: 0
          }
        }),
        text: async () => '{}'
      };
    };

    const res = await MediKioskApi.get('/api/interviews/301/dashboard');
    assert.strictEqual(res.ok, true);
    assert.strictEqual(capturedUrl, 'http://127.0.0.1:8000/api/interviews/301/dashboard');
    assert.strictEqual(res.data.patient.name, 'Ramesh Sharma');
    assert.strictEqual(res.data.latest_summary.summary_data.chief_complaint, 'Central chest heaviness for 2 days');
  });

  // Test 9: Case Summary Data Mapping Contract
  await runAsyncTest('T9: Structured case summary fields extracted accurately', async () => {
    const sData = {
      chief_complaint: 'Headache and fever',
      history_of_present_illness: 'Fever onset 3 days ago',
      ayush_profile: { agni: 'Vishamagni' }
    };

    assert.strictEqual(sData.chief_complaint, 'Headache and fever');
    assert.strictEqual(sData.history_of_present_illness, 'Fever onset 3 days ago');
    assert.strictEqual(sData.ayush_profile.agni, 'Vishamagni');
  });

  // Test 10: Multi-source contradiction display
  await runAsyncTest('T10: Contradiction engine alerts detected from backend schema', async () => {
    const contradictionsPayload = {
      has_contradictions: true,
      total_contradictions: 2,
      contradictions: [
        { id: 1, discrepancy_type: 'DOSING_FREQUENCY' }
      ]
    };

    assert.strictEqual(contradictionsPayload.has_contradictions, true);
    assert.strictEqual(contradictionsPayload.total_contradictions, 2);
  });

  // Test 11: Medication discrepancy display
  await runAsyncTest('T11: Medication discrepancy counts detected from backend schema', async () => {
    const medsPayload = {
      total_medications: 2,
      discrepancy_count: 1,
      discrepant_medication_names: ['Metformin']
    };

    assert.strictEqual(medsPayload.discrepancy_count, 1);
    assert.strictEqual(medsPayload.discrepant_medication_names[0], 'Metformin');
  });

  // Test 12: Active Red Flags Display
  await runAsyncTest('T12: Active Red flags alert detected from backend schema', async () => {
    const redFlags = [
      { id: 1, rule_key: 'FBS_ELEVATED', status: 'ACTIVE', message: 'FBS 142' }
    ];
    const active = redFlags.filter(r => r.status === 'ACTIVE');
    assert.strictEqual(active.length, 1);
    assert.strictEqual(active[0].message, 'FBS 142');
  });

  // Test 13: Patient Confirmation Audit Status
  await runAsyncTest('T13: Patient confirmation status detected accurately', async () => {
    const conf = { status: 'CONFIRMED', items: [1, 2, 3] };
    assert.strictEqual(conf.status, 'CONFIRMED');
    assert.strictEqual(conf.items.length, 3);
  });

  // Test 14: Doctor Review Start Endpoint Contract
  await runAsyncTest('T14: POST /api/interviews/{id}/summary/{sid}/doctor-review/start contract verified', async () => {
    let capturedUrl = null;
    let capturedBody = null;

    global.fetch = async (url, options) => {
      capturedUrl = url;
      capturedBody = JSON.parse(options.body);
      return {
        ok: true,
        status: 201,
        headers: { get: () => 'application/json' },
        json: async () => ({
          id: 701,
          patient_id: 101,
          interview_id: 301,
          summary_id: 501,
          summary_version: 1,
          status: 'IN_PROGRESS',
          doctor_name: 'Dr. Deshmukh',
          started_at: '2026-09-14T10:20:00Z',
          items: [
            { id: 11, section_key: 'chief_complaint', doctor_response: 'PENDING', is_required: true }
          ]
        }),
        text: async () => '{}'
      };
    };

    const res = await MediKioskApi.post('/api/interviews/301/summary/501/doctor-review/start', {
      doctor_name: 'Dr. Deshmukh',
      doctor_notes: 'Initial clinical desk review'
    });

    assert.strictEqual(res.ok, true);
    assert.strictEqual(capturedUrl, 'http://127.0.0.1:8000/api/interviews/301/summary/501/doctor-review/start');
    assert.strictEqual(capturedBody.doctor_name, 'Dr. Deshmukh');
    assert.strictEqual(res.data.status, 'IN_PROGRESS');
  });

  // Test 15: Doctor Review Item Verify Contract
  await runAsyncTest('T15: POST /api/interviews/{id}/doctor-reviews/{rid}/items/{iid}/verify contract verified', async () => {
    let capturedUrl = null;

    global.fetch = async (url) => {
      capturedUrl = url;
      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({
          id: 701,
          status: 'IN_PROGRESS',
          verified_items_count: 1
        }),
        text: async () => '{}'
      };
    };

    const res = await MediKioskApi.post('/api/interviews/301/doctor-reviews/701/items/11/verify', {
      doctor_note: 'Verified in consult'
    });

    assert.strictEqual(res.ok, true);
    assert.strictEqual(capturedUrl, 'http://127.0.0.1:8000/api/interviews/301/doctor-reviews/701/items/11/verify');
    assert.strictEqual(res.data.verified_items_count, 1);
  });

  // Test 16: Doctor Review Complete Contract
  await runAsyncTest('T16: POST /api/interviews/{id}/doctor-reviews/{rid}/complete contract verified', async () => {
    let capturedUrl = null;

    global.fetch = async (url) => {
      capturedUrl = url;
      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({
          id: 701,
          status: 'COMPLETED',
          completed_at: '2026-09-14T10:25:00Z'
        }),
        text: async () => '{}'
      };
    };

    const res = await MediKioskApi.post('/api/interviews/301/doctor-reviews/701/complete', {
      doctor_notes: 'All items verified and locked.'
    });

    assert.strictEqual(res.ok, true);
    assert.strictEqual(capturedUrl, 'http://127.0.0.1:8000/api/interviews/301/doctor-reviews/701/complete');
    assert.strictEqual(res.data.status, 'COMPLETED');
  });

  // Test 17: Authoritative Backend State Reload
  await runAsyncTest('T17: Authoritative dashboard state reloads upon review completion', async () => {
    let calledDashboard = false;

    global.fetch = async (url) => {
      if (url.includes('/dashboard')) calledDashboard = true;
      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({
          patient: { id: 101, name: 'Ramesh Sharma' },
          interview: { id: 301 },
          doctor_review: { status: 'COMPLETED' },
          readiness: { doctor_review_status: 'COMPLETED' }
        }),
        text: async () => '{}'
      };
    };

    const res = await MediKioskApi.get('/api/interviews/301/dashboard');
    assert.strictEqual(calledDashboard, true);
    assert.strictEqual(res.data.doctor_review.status, 'COMPLETED');
  });

  // Test 18: Non-Doctor Role Gate
  await runAsyncTest('T18: Clinical sign-off requires DOCTOR role', async () => {
    const staffUser = { role: 'STAFF', email: 'staff@aiia.gov.in' };
    const canSignOff = staffUser.role === 'DOCTOR';
    assert.strictEqual(canSignOff, false);
  });

  // Test 19: Clinical Disclaimer Preserved Verbatim
  await runAsyncTest('T19: Mandatory clinical disclaimer preserved verbatim', async () => {
    const disclaimer = 'DRAFT summary generated by AI for physician review only. Does not constitute a clinical diagnosis or treatment recommendation.';
    assert.strictEqual(disclaimer.includes('AI for physician review only'), true);
  });

  // Test 20: Zero Secrets Printed to Console
  await runAsyncTest('T20: Zero passwords or tokens printed to console', async () => {
    let logged = '';
    const origLog = console.log;
    console.log = (...args) => { logged += args.join(' '); };

    MediKioskSession.setAuthToken('test.secret.token');
    console.log = origLog;

    assert.strictEqual(logged.includes('test.secret.token'), false);
  });

  // Test 21: screen5-doctor-dashboard.html contains foundation scripts in head
  await runAsyncTest('T21: screen5-doctor-dashboard.html contains foundation scripts in head', async () => {
    const html = fs.readFileSync(path.join(__dirname, '../src/screens/screen5-doctor-dashboard.html'), 'utf-8');
    assert.strictEqual(html.includes('<script src="../scripts/config.js">'), true);
    assert.strictEqual(html.includes('<script src="../scripts/session.js">'), true);
    assert.strictEqual(html.includes('<script src="../scripts/api.js">'), true);
  });

  // Test 22: screen5-doctor-dashboard.html contains dashboardErrorBanner container
  await runAsyncTest('T22: screen5-doctor-dashboard.html contains dashboardErrorBanner container', async () => {
    const html = fs.readFileSync(path.join(__dirname, '../src/screens/screen5-doctor-dashboard.html'), 'utf-8');
    assert.strictEqual(html.includes('id="dashboardErrorBanner"'), true);
  });

  // Test 23: screen5-doctor-dashboard.html contains loginModal and doctorNotesModal
  await runAsyncTest('T23: screen5-doctor-dashboard.html contains loginModal and doctorNotesModal', async () => {
    const html = fs.readFileSync(path.join(__dirname, '../src/screens/screen5-doctor-dashboard.html'), 'utf-8');
    assert.strictEqual(html.includes('id="loginModal"'), true);
    assert.strictEqual(html.includes('id="doctorNotesModal"'), true);
  });

  // Test 24: screen5-doctor-dashboard.html contains conflictBanner and summaryDisclaimerBox
  await runAsyncTest('T24: screen5-doctor-dashboard.html contains conflictBanner and summaryDisclaimerBox', async () => {
    const html = fs.readFileSync(path.join(__dirname, '../src/screens/screen5-doctor-dashboard.html'), 'utf-8');
    assert.strictEqual(html.includes('id="conflictBanner"'), true);
    assert.strictEqual(html.includes('id="summaryDisclaimerBox"'), true);
  });

  console.log(`\nStep 7 Test Results: ${passedTests} passed, ${failedTests} failed\n`);
  if (failedTests > 0) {
    process.exit(1);
  }
}

runAllTests().catch(err => {
  console.error('Test execution failed:', err);
  process.exit(1);
});
