/**
 * Live Local Frontend -> FastAPI -> PostgreSQL Manual Verification
 * Tests actual HTTP roundtrip between MediKioskApi, local FastAPI backend, and PostgreSQL.
 */

const assert = require('assert');

class MockSessionStorage {
  constructor() { this.store = {}; }
  getItem(k) { return this.store[k] || null; }
  setItem(k, v) { this.store[k] = String(v); }
  removeItem(k) { delete this.store[k]; }
  clear() { this.store = {}; }
}

global.window = global;
global.sessionStorage = new MockSessionStorage();

const MediKioskConfig = require('../src/scripts/config.js');
const MediKioskSession = require('../src/scripts/session.js');
const MediKioskApi = require('../src/scripts/api.js');

async function runLocalTest() {
  console.log('Testing live local registration with FastAPI & PostgreSQL...');
  MediKioskSession.clearWorkflowState();

  // Unique phone number for test run to avoid 409
  const uniquePhone = '+9198' + Date.now().toString().slice(-8);

  const payload = {
    phone_number: uniquePhone,
    name: 'Ramesh Patel',
    date_of_birth: '1982-03-14',
    gender: 'Male',
    preferred_language: 'en'
  };

  console.log(`1. Sending POST /api/patients with phone: ${uniquePhone}`);
  const patientRes = await MediKioskApi.post('/api/patients', payload);
  console.log('   Response Status:', patientRes.status);
  console.log('   Created Patient ID:', patientRes.data.id);
  assert.strictEqual(patientRes.status, 201);
  assert.ok(typeof patientRes.data.id === 'number');

  MediKioskSession.setPatientId(patientRes.data.id);
  assert.strictEqual(MediKioskSession.getPatientId(), String(patientRes.data.id));
  console.log('   Saved to sessionStorage: patient_id =', MediKioskSession.getPatientId());

  console.log(`2. Sending POST /api/sessions with patient_id: ${patientRes.data.id}`);
  const sessionRes = await MediKioskApi.post('/api/sessions', { patient_id: patientRes.data.id });
  console.log('   Response Status:', sessionRes.status);
  console.log('   Created Session ID:', sessionRes.data.id);
  console.log('   Encounter Status:', sessionRes.data.status);
  assert.strictEqual(sessionRes.status, 201);
  assert.strictEqual(sessionRes.data.status, 'REGISTRATION');

  MediKioskSession.setSessionId(sessionRes.data.id);
  assert.strictEqual(MediKioskSession.getSessionId(), String(sessionRes.data.id));
  console.log('   Saved to sessionStorage: session_id =', MediKioskSession.getSessionId());

  console.log('\n✓ Live Local Test Passed: Frontend -> FastAPI -> PostgreSQL -> Response -> sessionStorage verified successfully!');
}

runLocalTest().catch((err) => {
  console.error('Local manual test failed:', err);
  process.exit(1);
});
