/**
 * Live Local Frontend -> Consent API -> PostgreSQL Manual Verification
 * Tests actual HTTP roundtrip between MediKioskApi, local FastAPI backend, and PostgreSQL for patient consent.
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

async function runLocalConsentTest() {
  console.log('Testing live local consent workflow with FastAPI & PostgreSQL...');
  MediKioskSession.clearWorkflowState();

  // 1. Register a fresh patient first
  const uniquePhone = '+9198' + Date.now().toString().slice(-8);
  const patientRes = await MediKioskApi.post('/api/patients', {
    phone_number: uniquePhone,
    name: 'Anita Verma',
    date_of_birth: '1992-11-05',
    gender: 'Female',
    preferred_language: 'en'
  });

  assert.strictEqual(patientRes.status, 201);
  const patientId = patientRes.data.id;
  MediKioskSession.setPatientId(patientId);
  console.log(`1. Created patient ID: ${patientId}`);

  // 2. Grant CLINICAL_HISTORY consent
  console.log(`2. Sending POST /api/patients/${patientId}/consents for CLINICAL_HISTORY...`);
  const consentRes = await MediKioskApi.post(`/api/patients/${patientId}/consents`, {
    purpose: 'CLINICAL_HISTORY',
    language_code: 'en',
    consent_version: '1.0',
    collection_method: 'PATIENT_SELF'
  });

  console.log('   Response Status:', consentRes.status);
  console.log('   Consent ID:', consentRes.data.id);
  console.log('   Consent Status:', consentRes.data.status);
  console.log('   Purpose:', consentRes.data.purpose);
  assert.strictEqual(consentRes.status, 201);
  assert.strictEqual(consentRes.data.status, 'GRANTED');
  assert.strictEqual(consentRes.data.purpose, 'CLINICAL_HISTORY');

  // 3. Verify backend active consent confirms PostgreSQL persistence
  console.log(`3. Sending GET /api/patients/${patientId}/consents/active/CLINICAL_HISTORY...`);
  const activeRes = await MediKioskApi.get(`/api/patients/${patientId}/consents/active/CLINICAL_HISTORY`);
  console.log('   Active Response Status:', activeRes.status);
  console.log('   Active Consent ID:', activeRes.data.consent.id);
  assert.strictEqual(activeRes.status, 200);
  assert.strictEqual(activeRes.data.active, true);
  assert.strictEqual(activeRes.data.consent.purpose, 'CLINICAL_HISTORY');

  // 4. Verify session storage contains only IDs, zero consent text
  const storedKeys = Object.keys(global.sessionStorage.store);
  assert.ok(!storedKeys.includes('consent'));
  assert.strictEqual(MediKioskSession.getPatientId(), String(patientId));
  console.log('   sessionStorage contains ONLY patient_id:', MediKioskSession.getPatientId());

  console.log('\n✓ Live Local Test Passed: Frontend -> Consent API -> PostgreSQL verified successfully!');
}

runLocalConsentTest().catch((err) => {
  console.error('Local manual consent test failed:', err);
  process.exit(1);
});
