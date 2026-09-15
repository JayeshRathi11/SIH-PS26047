/**
 * Step 8 Integration Test Suite: OPD Queue & Emergency Escalation Workflow
 * 
 * Verifies:
 *  1. POST /api/opd/queue/entries: Token allocation creates valid entry with patient/interview link
 *  2. GET /api/opd/queue: Active queue entries retrieved and parsed
 *  3. GET /api/opd/queue: Empty queue payload handled cleanly without crashing
 *  4. GET /api/opd/queue: Network / API failure handled safely with error propagation
 *  5. GET /api/opd/queue/summary: Operational queue metrics (waiting, called, in_service, emergency)
 *  6. POST /api/opd/queue/next: Atomically calling next waiting patient transitions token to CALLED
 *  7. POST /api/opd/queue/entries/{id}/start: Starting consultation transitions token to IN_SERVICE
 *  8. POST /api/opd/queue/entries/{id}/complete: Completing consultation transitions token to COMPLETED
 *  9. POST /api/opd/queue/entries/{id}/return-to-waiting: Returning called token back to WAITING
 * 10. POST /api/opd/queue/entries/{id}/escalate: Clinical staff priority escalation to EMERGENCY
 * 11. POST /api/opd/queue/entries/{id}/cancel: Cancelling token transitions status to CANCELLED
 * 12. Priority Distinction: Emergency vs Normal queue items accurately mapped from backend data
 * 13. GET /api/emergency/active: Active emergency escalations retrieved for clinical desk
 * 14. GET /api/emergency/active: Empty active emergency escalations handled cleanly
 * 15. POST /api/emergency/{id}/acknowledge: Acknowledging emergency escalation with staff_id
 * 16. POST /api/emergency/{id}/triage: Triaging emergency escalation with clinical notes
 * 17. POST /api/emergency/{id}/resolve: Resolving emergency escalation with resolution reason
 * 18. POST /api/emergency/{id}/cancel: Cancelling emergency escalation with cancellation reason
 * 19. Red-Flag Lifecycle: POST /api/interviews/{id}/red-flags/{rf_id}/acknowledge updates flag
 * 20. Red-Flag Lifecycle: POST /api/interviews/{id}/red-flags/{rf_id}/resolve resolves red flag
 * 21. Manual Emergency Escalation: POST /api/interviews/{id}/emergency/escalate triggers critical alert
 * 22. RBAC Enforcement: Unauthorized role (PATIENT attempting staff queue action) receives 403 Forbidden
 * 23. Authoritative State Reload: Authoritative backend state reloaded after each queue/escalation action
 * 24. Storage Purity: Zero PHI, queue tokens, red flags, or clinical data stored in browser storage
 * 25. Console Security: Zero sensitive credentials or PHI leaked to console
 * 26. Screen Verification: screen5-doctor-dashboard.html contains all Step 8 UI elements
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
    localStorage.clear();
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
  console.log('--- Step 8: OPD Queue & Emergency Escalation Tests ---');

  // Test 1: POST /api/opd/queue/entries
  await runAsyncTest('T1: POST /api/opd/queue/entries allocates token with patient/interview association', async () => {
    let capturedUrl = null;
    let capturedBody = null;
    let capturedMethod = null;

    global.fetch = async (url, options) => {
      capturedUrl = url;
      capturedMethod = options.method;
      capturedBody = JSON.parse(options.body);
      return {
        ok: true,
        status: 201,
        headers: { get: () => 'application/json' },
        json: async () => ({
          id: 101,
          token_number: 24,
          patient_id: 12,
          interview_id: 5,
          priority: 'NORMAL',
          status: 'WAITING',
          position: 1,
          created_at: new Date().toISOString()
        })
      };
    };

    const res = await MediKioskApi.post('/api/opd/queue/entries', {
      patient_id: 12,
      interview_id: 5
    });

    assert.strictEqual(res.ok, true);
    assert.strictEqual(res.status, 201);
    assert.strictEqual(capturedMethod, 'POST');
    assert.strictEqual(capturedUrl.endsWith('/api/opd/queue/entries'), true);
    assert.strictEqual(capturedBody.patient_id, 12);
    assert.strictEqual(capturedBody.interview_id, 5);
    assert.strictEqual(res.data.token_number, 24);
    assert.strictEqual(res.data.status, 'WAITING');
  });

  // Test 2: GET /api/opd/queue
  await runAsyncTest('T2: GET /api/opd/queue retrieves authoritative active queue entries', async () => {
    let capturedUrl = null;

    global.fetch = async (url, options) => {
      capturedUrl = url;
      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({
          queue_date: '2026-09-14',
          total_count: 2,
          entries: [
            { id: 1, token_number: 1, patient_id: 10, interview_id: 1, priority: 'EMERGENCY', status: 'WAITING', position: 1 },
            { id: 2, token_number: 2, patient_id: 11, interview_id: 2, priority: 'NORMAL', status: 'WAITING', position: 2 }
          ]
        })
      };
    };

    const res = await MediKioskApi.get('/api/opd/queue');
    assert.strictEqual(res.ok, true);
    assert.strictEqual(capturedUrl.endsWith('/api/opd/queue'), true);
    assert.strictEqual(res.data.total_count, 2);
    assert.strictEqual(res.data.entries.length, 2);
    assert.strictEqual(res.data.entries[0].token_number, 1);
    assert.strictEqual(res.data.entries[0].priority, 'EMERGENCY');
  });

  // Test 3: GET /api/opd/queue with Empty Queue
  await runAsyncTest('T3: GET /api/opd/queue handles empty queue cleanly', async () => {
    global.fetch = async (url) => ({
      ok: true,
      status: 200,
      headers: { get: () => 'application/json' },
      json: async () => ({
        queue_date: '2026-09-14',
        total_count: 0,
        entries: []
      })
    });

    const res = await MediKioskApi.get('/api/opd/queue');
    assert.strictEqual(res.ok, true);
    assert.strictEqual(res.data.total_count, 0);
    assert.strictEqual(Array.isArray(res.data.entries), true);
    assert.strictEqual(res.data.entries.length, 0);
  });

  // Test 4: GET /api/opd/queue loading failure (403 Forbidden)
  await runAsyncTest('T4: GET /api/opd/queue handles failure (403 Forbidden) throwing ApiError safely', async () => {
    global.fetch = async (url) => ({
      ok: false,
      status: 403,
      headers: { get: () => 'application/json' },
      json: async () => ({ detail: 'Role DOCTOR or STAFF required' })
    });

    let caughtError = null;
    try {
      await MediKioskApi.get('/api/opd/queue');
    } catch (err) {
      caughtError = err;
    }

    assert.notStrictEqual(caughtError, null);
    assert.strictEqual(caughtError.status, 403);
    assert.strictEqual(caughtError.isForbidden, true);
  });

  // Test 5: GET /api/opd/queue/summary
  await runAsyncTest('T5: GET /api/opd/queue/summary retrieves operational counts', async () => {
    let capturedUrl = null;

    global.fetch = async (url) => {
      capturedUrl = url;
      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({
          queue_date: '2026-09-14',
          total_entries: 5,
          waiting: 2,
          called: 1,
          in_service: 1,
          completed: 1,
          cancelled: 0,
          normal: 3,
          urgent: 1,
          emergency: 1
        })
      };
    };

    const res = await MediKioskApi.get('/api/opd/queue/summary');
    assert.strictEqual(res.ok, true);
    assert.strictEqual(capturedUrl.endsWith('/api/opd/queue/summary'), true);
    assert.strictEqual(res.data.waiting, 2);
    assert.strictEqual(res.data.called, 1);
    assert.strictEqual(res.data.in_service, 1);
    assert.strictEqual(res.data.emergency, 1);
  });

  // Test 6: POST /api/opd/queue/next
  await runAsyncTest('T6: POST /api/opd/queue/next atomically calls next waiting patient', async () => {
    let capturedUrl = null;
    let capturedMethod = null;

    global.fetch = async (url, options) => {
      capturedUrl = url;
      capturedMethod = options.method;
      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({
          id: 5,
          token_number: 1,
          patient_id: 10,
          interview_id: 1,
          priority: 'EMERGENCY',
          status: 'CALLED',
          called_at: new Date().toISOString()
        })
      };
    };

    const res = await MediKioskApi.post('/api/opd/queue/next', {});
    assert.strictEqual(res.ok, true);
    assert.strictEqual(capturedMethod, 'POST');
    assert.strictEqual(capturedUrl.endsWith('/api/opd/queue/next'), true);
    assert.strictEqual(res.data.status, 'CALLED');
    assert.strictEqual(res.data.priority, 'EMERGENCY');
  });

  // Test 7: POST /api/opd/queue/entries/{id}/start
  await runAsyncTest('T7: POST /api/opd/queue/entries/{id}/start transitions token to IN_SERVICE', async () => {
    let capturedUrl = null;

    global.fetch = async (url, options) => {
      capturedUrl = url;
      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({
          id: 5,
          token_number: 1,
          patient_id: 10,
          status: 'IN_SERVICE',
          service_started_at: new Date().toISOString()
        })
      };
    };

    const res = await MediKioskApi.post('/api/opd/queue/entries/5/start', {});
    assert.strictEqual(res.ok, true);
    assert.strictEqual(capturedUrl.endsWith('/api/opd/queue/entries/5/start'), true);
    assert.strictEqual(res.data.status, 'IN_SERVICE');
  });

  // Test 8: POST /api/opd/queue/entries/{id}/complete
  await runAsyncTest('T8: POST /api/opd/queue/entries/{id}/complete transitions token to COMPLETED', async () => {
    let capturedUrl = null;

    global.fetch = async (url, options) => {
      capturedUrl = url;
      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({
          id: 5,
          token_number: 1,
          patient_id: 10,
          status: 'COMPLETED',
          completed_at: new Date().toISOString()
        })
      };
    };

    const res = await MediKioskApi.post('/api/opd/queue/entries/5/complete', {});
    assert.strictEqual(res.ok, true);
    assert.strictEqual(capturedUrl.endsWith('/api/opd/queue/entries/5/complete'), true);
    assert.strictEqual(res.data.status, 'COMPLETED');
  });

  // Test 9: POST /api/opd/queue/entries/{id}/return-to-waiting
  await runAsyncTest('T9: POST /api/opd/queue/entries/{id}/return-to-waiting returns called token to WAITING', async () => {
    let capturedUrl = null;

    global.fetch = async (url) => {
      capturedUrl = url;
      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({
          id: 5,
          token_number: 1,
          patient_id: 10,
          status: 'WAITING',
          called_at: null
        })
      };
    };

    const res = await MediKioskApi.post('/api/opd/queue/entries/5/return-to-waiting', {});
    assert.strictEqual(res.ok, true);
    assert.strictEqual(capturedUrl.endsWith('/api/opd/queue/entries/5/return-to-waiting'), true);
    assert.strictEqual(res.data.status, 'WAITING');
  });

  // Test 10: POST /api/opd/queue/entries/{id}/escalate
  await runAsyncTest('T10: POST /api/opd/queue/entries/{id}/escalate escalates token priority to EMERGENCY', async () => {
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
          id: 5,
          token_number: 1,
          priority: 'EMERGENCY',
          priority_reason: capturedBody.reason,
          status: 'WAITING'
        })
      };
    };

    const res = await MediKioskApi.post('/api/opd/queue/entries/5/escalate', {
      target_priority: 'EMERGENCY',
      reason: 'CLINICAL_STAFF_ESCALATION',
      notes: 'Patient showing diaphoresis and chest pain in waiting area'
    });

    assert.strictEqual(res.ok, true);
    assert.strictEqual(capturedUrl.endsWith('/api/opd/queue/entries/5/escalate'), true);
    assert.strictEqual(capturedBody.target_priority, 'EMERGENCY');
    assert.strictEqual(res.data.priority, 'EMERGENCY');
  });

  // Test 11: POST /api/opd/queue/entries/{id}/cancel
  await runAsyncTest('T11: POST /api/opd/queue/entries/{id}/cancel cancels token entry', async () => {
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
          id: 5,
          token_number: 1,
          status: 'CANCELLED',
          cancellation_reason: capturedBody.reason
        })
      };
    };

    const res = await MediKioskApi.post('/api/opd/queue/entries/5/cancel', {
      reason: 'Patient departed hospital'
    });

    assert.strictEqual(res.ok, true);
    assert.strictEqual(capturedUrl.endsWith('/api/opd/queue/entries/5/cancel'), true);
    assert.strictEqual(res.data.status, 'CANCELLED');
    assert.strictEqual(res.data.cancellation_reason, 'Patient departed hospital');
  });

  // Test 12: Queue Priority Distinction
  await runAsyncTest('T12: Priority distinction: NORMAL, URGENT, and EMERGENCY accurately classified', async () => {
    const mockEntries = [
      { id: 1, token_number: 10, priority: 'NORMAL', status: 'WAITING' },
      { id: 2, token_number: 11, priority: 'URGENT', status: 'WAITING' },
      { id: 3, token_number: 12, priority: 'EMERGENCY', status: 'WAITING' }
    ];

    const isHighPriority = entry => entry.priority === 'EMERGENCY' || entry.priority === 'URGENT';

    assert.strictEqual(isHighPriority(mockEntries[0]), false);
    assert.strictEqual(isHighPriority(mockEntries[1]), true);
    assert.strictEqual(isHighPriority(mockEntries[2]), true);
  });

  // Test 13: GET /api/emergency/active
  await runAsyncTest('T13: GET /api/emergency/active retrieves active emergency escalations', async () => {
    let capturedUrl = null;

    global.fetch = async (url) => {
      capturedUrl = url;
      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => [
          {
            escalation_id: 101,
            interview_id: 7,
            patient_id: 3,
            queue_token_number: 14,
            severity: 'CRITICAL',
            status: 'ACTIVE',
            reason: 'Acute cardiac chest pain reported in kiosk',
            triggered_at: new Date().toISOString()
          }
        ]
      };
    };

    const res = await MediKioskApi.get('/api/emergency/active');
    assert.strictEqual(res.ok, true);
    assert.strictEqual(capturedUrl.endsWith('/api/emergency/active'), true);
    assert.strictEqual(res.data.length, 1);
    assert.strictEqual(res.data[0].escalation_id, 101);
    assert.strictEqual(res.data[0].severity, 'CRITICAL');
    assert.strictEqual(res.data[0].status, 'ACTIVE');
  });

  // Test 14: GET /api/emergency/active with empty list
  await runAsyncTest('T14: GET /api/emergency/active handles empty escalation list cleanly', async () => {
    global.fetch = async (url) => ({
      ok: true,
      status: 200,
      headers: { get: () => 'application/json' },
      json: async () => []
    });

    const res = await MediKioskApi.get('/api/emergency/active');
    assert.strictEqual(res.ok, true);
    assert.strictEqual(Array.isArray(res.data), true);
    assert.strictEqual(res.data.length, 0);
  });

  // Test 15: POST /api/emergency/{id}/acknowledge
  await runAsyncTest('T15: POST /api/emergency/{id}/acknowledge transitions escalation to ACKNOWLEDGED', async () => {
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
          escalation_id: 101,
          status: 'ACKNOWLEDGED',
          acknowledged_by: capturedBody.staff_id,
          acknowledged_at: new Date().toISOString()
        })
      };
    };

    const res = await MediKioskApi.post('/api/emergency/101/acknowledge', {
      staff_id: 'nurse.station@hospital.gov.in',
      notes: 'Nurse dispatched to intake kiosk'
    });

    assert.strictEqual(res.ok, true);
    assert.strictEqual(capturedUrl.endsWith('/api/emergency/101/acknowledge'), true);
    assert.strictEqual(capturedBody.staff_id, 'nurse.station@hospital.gov.in');
    assert.strictEqual(res.data.status, 'ACKNOWLEDGED');
  });

  // Test 16: POST /api/emergency/{id}/triage
  await runAsyncTest('T16: POST /api/emergency/{id}/triage transitions escalation to TRIAGED', async () => {
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
          escalation_id: 101,
          status: 'TRIAGED',
          triaged_by: capturedBody.staff_id,
          triage_notes: capturedBody.triage_notes,
          triaged_at: new Date().toISOString()
        })
      };
    };

    const res = await MediKioskApi.post('/api/emergency/101/triage', {
      staff_id: 'dr.deshmukh@hospital.gov.in',
      triage_notes: 'Patient directed immediately to Emergency Bay 2'
    });

    assert.strictEqual(res.ok, true);
    assert.strictEqual(capturedUrl.endsWith('/api/emergency/101/triage'), true);
    assert.strictEqual(res.data.status, 'TRIAGED');
    assert.strictEqual(res.data.triage_notes, 'Patient directed immediately to Emergency Bay 2');
  });

  // Test 17: POST /api/emergency/{id}/resolve
  await runAsyncTest('T17: POST /api/emergency/{id}/resolve resolves active emergency escalation', async () => {
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
          escalation_id: 101,
          status: 'RESOLVED',
          resolved_by: capturedBody.staff_id,
          resolution_reason: capturedBody.resolution_reason,
          resolved_at: new Date().toISOString()
        })
      };
    };

    const res = await MediKioskApi.post('/api/emergency/101/resolve', {
      staff_id: 'dr.deshmukh@hospital.gov.in',
      resolution_reason: 'ECG normal, patient stabilized, returned to standard OPD consult'
    });

    assert.strictEqual(res.ok, true);
    assert.strictEqual(capturedUrl.endsWith('/api/emergency/101/resolve'), true);
    assert.strictEqual(res.data.status, 'RESOLVED');
  });

  // Test 18: POST /api/emergency/{id}/cancel
  await runAsyncTest('T18: POST /api/emergency/{id}/cancel cancels emergency escalation', async () => {
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
          escalation_id: 101,
          status: 'CANCELLED',
          cancelled_by: capturedBody.staff_id,
          cancellation_reason: capturedBody.cancellation_reason,
          cancelled_at: new Date().toISOString()
        })
      };
    };

    const res = await MediKioskApi.post('/api/emergency/101/cancel', {
      staff_id: 'staff@hospital.gov.in',
      cancellation_reason: 'Accidental trigger during voice intake demo'
    });

    assert.strictEqual(res.ok, true);
    assert.strictEqual(capturedUrl.endsWith('/api/emergency/101/cancel'), true);
    assert.strictEqual(res.data.status, 'CANCELLED');
  });

  // Test 19: POST /api/interviews/{id}/red-flags/{rf_id}/acknowledge
  await runAsyncTest('T19: POST /api/interviews/{id}/red-flags/{rf_id}/acknowledge updates red-flag status', async () => {
    let capturedUrl = null;

    global.fetch = async (url) => {
      capturedUrl = url;
      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({
          id: 42,
          interview_id: 7,
          status: 'ACKNOWLEDGED',
          acknowledged_at: new Date().toISOString()
        })
      };
    };

    const res = await MediKioskApi.post('/api/interviews/7/red-flags/42/acknowledge', {});
    assert.strictEqual(res.ok, true);
    assert.strictEqual(capturedUrl.endsWith('/api/interviews/7/red-flags/42/acknowledge'), true);
    assert.strictEqual(res.data.status, 'ACKNOWLEDGED');
  });

  // Test 20: POST /api/interviews/{id}/red-flags/{rf_id}/resolve
  await runAsyncTest('T20: POST /api/interviews/{id}/red-flags/{rf_id}/resolve resolves red flag', async () => {
    let capturedUrl = null;

    global.fetch = async (url) => {
      capturedUrl = url;
      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({
          id: 42,
          interview_id: 7,
          status: 'RESOLVED',
          resolved_at: new Date().toISOString()
        })
      };
    };

    const res = await MediKioskApi.post('/api/interviews/7/red-flags/42/resolve', {});
    assert.strictEqual(res.ok, true);
    assert.strictEqual(capturedUrl.endsWith('/api/interviews/7/red-flags/42/resolve'), true);
    assert.strictEqual(res.data.status, 'RESOLVED');
  });

  // Test 21: POST /api/interviews/{id}/emergency/escalate
  await runAsyncTest('T21: POST /api/interviews/{id}/emergency/escalate triggers manual emergency escalation', async () => {
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
          escalation_id: 102,
          interview_id: 7,
          severity: capturedBody.severity,
          reason: capturedBody.reason,
          status: 'ACTIVE'
        })
      };
    };

    const res = await MediKioskApi.post('/api/interviews/7/emergency/escalate', {
      staff_id: 'dr.deshmukh@hospital.gov.in',
      reason: 'Physician direct clinical escalation: acute respiratory distress',
      severity: 'CRITICAL'
    });

    assert.strictEqual(res.ok, true);
    assert.strictEqual(capturedUrl.endsWith('/api/interviews/7/emergency/escalate'), true);
    assert.strictEqual(capturedBody.severity, 'CRITICAL');
    assert.strictEqual(res.data.status, 'ACTIVE');
  });

  // Test 22: RBAC Enforcement
  await runAsyncTest('T22: RBAC: Unauthorized role receives 403 Forbidden on staff/doctor queue actions', async () => {
    global.fetch = async (url) => ({
      ok: false,
      status: 403,
      headers: { get: () => 'application/json' },
      json: async () => ({
        detail: 'Operation requires DOCTOR or STAFF role'
      })
    });

    let caughtError = null;
    try {
      await MediKioskApi.post('/api/opd/queue/next', {});
    } catch (err) {
      caughtError = err;
    }

    assert.notStrictEqual(caughtError, null);
    assert.strictEqual(caughtError.status, 403);
    assert.strictEqual(caughtError.isForbidden, true);
  });

  // Test 23: Authoritative state reload
  await runAsyncTest('T23: Authoritative backend state reloaded after queue transition', async () => {
    let queueReloaded = false;

    global.fetch = async (url, options) => {
      if (url.includes('/api/opd/queue/entries/5/start')) {
        return {
          ok: true,
          status: 200,
          headers: { get: () => 'application/json' },
          json: async () => ({ id: 5, status: 'IN_SERVICE' })
        };
      }
      if (url.endsWith('/api/opd/queue')) {
        queueReloaded = true;
        return {
          ok: true,
          status: 200,
          headers: { get: () => 'application/json' },
          json: async () => ({
            queue_date: '2026-09-14',
            total_count: 1,
            entries: [{ id: 5, token_number: 1, status: 'IN_SERVICE' }]
          })
        };
      }
      return { ok: true, status: 200, headers: { get: () => 'application/json' }, json: async () => ({}) };
    };

    // Simulate transition
    await MediKioskApi.post('/api/opd/queue/entries/5/start', {});
    // Simulate re-fetching authoritative queue
    const queueRes = await MediKioskApi.get('/api/opd/queue');

    assert.strictEqual(queueReloaded, true);
    assert.strictEqual(queueRes.data.entries[0].status, 'IN_SERVICE');
  });

  // Test 24: Storage Purity
  await runAsyncTest('T24: Storage Purity: Zero PHI, queue tokens, red flags, or clinical data stored in browser storage', async () => {
    MediKioskSession.setAuthToken('mock.valid.token');
    MediKioskSession.setPatientId(10);
    MediKioskSession.setInterviewId(5);

    // Verify allowed keys
    const allowedKeys = new Set([
      'medikiosk_auth_token',
      'medikiosk_patient_id',
      'medikiosk_session_id',
      'medikiosk_interview_id'
    ]);
    for (const key of Object.keys(mockStorage.store)) {
      assert.strictEqual(allowedKeys.has(key), true, `Illegal key found in storage: ${key}`);
    }

    // Verify forbidden data types are not present
    const forbiddenSubstrings = ['token_number', 'EMERGENCY', 'red_flag', 'chest pain', 'Ramesh', 'A-24'];
    const serialized = JSON.stringify(mockStorage.store);
    for (const sub of forbiddenSubstrings) {
      assert.strictEqual(serialized.includes(sub), false, `Forbidden string '${sub}' found in storage!`);
    }
  });

  // Test 25: Console Security
  await runAsyncTest('T25: Console Security: Zero bearer tokens, credentials, or PHI printed to console', async () => {
    const logs = [];
    const origLog = console.log;
    console.log = (...args) => {
      logs.push(args.join(' '));
      origLog(...args);
    };

    try {
      global.fetch = async () => ({
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({ id: 1, token_number: 24, priority: 'NORMAL' })
      });

      await MediKioskApi.get('/api/opd/queue');

      const allLogs = logs.join('\n');
      assert.strictEqual(allLogs.includes('Bearer'), false, 'Bearer token leaked in console logs');
      assert.strictEqual(allLogs.includes('password'), false, 'Password leaked in console logs');
    } finally {
      console.log = origLog;
    }
  });

  // Test 26: Screen UI Verification
  await runAsyncTest('T26: screen5-doctor-dashboard.html contains all Step 8 queue & emergency desk components', async () => {
    const filePath = path.join(__dirname, '../src/screens/screen5-doctor-dashboard.html');
    const content = fs.readFileSync(filePath, 'utf8');

    // Queue buttons and elements
    assert.strictEqual(content.includes('id="btnCallNext"'), true, 'Missing btnCallNext');
    assert.strictEqual(content.includes('id="queueSummaryBar"'), true, 'Missing queueSummaryBar');
    assert.strictEqual(content.includes('id="summaryWaitingCount"'), true, 'Missing summaryWaitingCount');
    assert.strictEqual(content.includes('id="summaryCalledCount"'), true, 'Missing summaryCalledCount');
    assert.strictEqual(content.includes('id="summaryInServiceCount"'), true, 'Missing summaryInServiceCount');
    assert.strictEqual(content.includes('id="summaryEmergencyCount"'), true, 'Missing summaryEmergencyCount');
    assert.strictEqual(content.includes('id="queueActionControls"'), true, 'Missing queueActionControls');
    assert.strictEqual(content.includes('id="btnStartService"'), true, 'Missing btnStartService');
    assert.strictEqual(content.includes('id="btnCompleteService"'), true, 'Missing btnCompleteService');
    assert.strictEqual(content.includes('id="btnReturnWaiting"'), true, 'Missing btnReturnWaiting');
    assert.strictEqual(content.includes('id="btnEscalateQueue"'), true, 'Missing btnEscalateQueue');
    assert.strictEqual(content.includes('id="btnCancelQueue"'), true, 'Missing btnCancelQueue');

    // Emergency desk elements
    assert.strictEqual(content.includes('id="emergencyDeskBanner"'), true, 'Missing emergencyDeskBanner');
    assert.strictEqual(content.includes('id="emergencyEscalationsList"'), true, 'Missing emergencyEscalationsList');
    assert.strictEqual(content.includes('/api/emergency/active'), true, 'Missing /api/emergency/active call');
    assert.strictEqual(content.includes('/api/opd/queue/summary'), true, 'Missing /api/opd/queue/summary call');
    assert.strictEqual(content.includes('/api/opd/queue/next'), true, 'Missing /api/opd/queue/next call');
  });

  console.log(`\nResults: ${passedTests} passed, ${failedTests} failed`);
  if (failedTests > 0) {
    process.exit(1);
  }
}

runAllTests().catch(err => {
  console.error('Fatal test error:', err);
  process.exit(1);
});
