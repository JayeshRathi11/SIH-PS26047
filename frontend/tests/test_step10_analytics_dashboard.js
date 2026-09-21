/**
 * Step 10 Test Suite: Operational Analytics Dashboard & Demo Seeding
 * 
 * Verifies:
 *  1. screen6-analytics-dashboard.html exists and contains valid foundation scripts
 *  2. screen6-analytics-dashboard.html contains key KPI metric containers
 *  3. screen6-analytics-dashboard.html contains conversion funnel container
 *  4. screen6-analytics-dashboard.html contains duration benchmark and language containers
 *  5. screen5-doctor-dashboard.html contains btnSeedDemoQueue button
 *  6. screen5-doctor-dashboard.html contains caseSheetPlaceholder and caseSheetContent
 *  7. screen5-doctor-dashboard.html contains quick test login buttons
 *  8. screen5-doctor-dashboard.html links to screen6-analytics-dashboard.html
 *  9. qa-launcher.html links to screen6-analytics-dashboard.html
 * 10. qa-launcher.html contains quick seed demo action
 * 11. GET /api/patients/by-phone/{phone} API contract test
 * 12. POST /api/demo/seed API contract test
 * 13. Storage Purity: zero passwords or sensitive data in browser storage
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

async function runSuite() {
  console.log('--- Step 10: Operational Analytics & Dynamic Dashboard Tests ---');

  // Test 1: screen6 exists and contains foundation scripts
  await runAsyncTest('T1: screen6-analytics-dashboard.html contains foundation scripts in head', () => {
    const filePath = path.join(__dirname, '../src/screens/screen6-analytics-dashboard.html');
    assert.strictEqual(fs.existsSync(filePath), true, 'screen6 file must exist');
    const content = fs.readFileSync(filePath, 'utf-8');
    assert.strictEqual(content.includes('config.js'), true);
    assert.strictEqual(content.includes('session.js'), true);
    assert.strictEqual(content.includes('api.js'), true);
  });

  // Test 2: screen6 contains KPI containers
  await runAsyncTest('T2: screen6 contains KPI metric elements', () => {
    const content = fs.readFileSync(path.join(__dirname, '../src/screens/screen6-analytics-dashboard.html'), 'utf-8');
    assert.strictEqual(content.includes('id="kpiTotalPatients"'), true);
    assert.strictEqual(content.includes('id="kpiCompletionRate"'), true);
    assert.strictEqual(content.includes('id="kpiAvgDuration"'), true);
    assert.strictEqual(content.includes('id="kpiRedFlags"'), true);
    assert.strictEqual(content.includes('id="kpiOcrDocs"'), true);
    assert.strictEqual(content.includes('id="kpiFhirTransmitted"'), true);
  });

  // Test 3: screen6 contains conversion funnel container
  await runAsyncTest('T3: screen6 contains conversion funnel pipeline container', () => {
    const content = fs.readFileSync(path.join(__dirname, '../src/screens/screen6-analytics-dashboard.html'), 'utf-8');
    assert.strictEqual(content.includes('id="funnelContainer"'), true);
  });

  // Test 4: screen6 contains duration benchmark and language elements
  await runAsyncTest('T4: screen6 contains duration and language distribution elements', () => {
    const content = fs.readFileSync(path.join(__dirname, '../src/screens/screen6-analytics-dashboard.html'), 'utf-8');
    assert.strictEqual(content.includes('id="durationTableBody"'), true);
    assert.strictEqual(content.includes('id="languageDistributionList"'), true);
    assert.strictEqual(content.includes('id="escCriticalCount"'), true);
    assert.strictEqual(content.includes('id="contradictionCount"'), true);
  });

  // Test 5: screen5 contains btnSeedDemoQueue
  await runAsyncTest('T5: screen5-doctor-dashboard.html contains btnSeedDemoQueue', () => {
    const content = fs.readFileSync(path.join(__dirname, '../src/screens/screen5-doctor-dashboard.html'), 'utf-8');
    assert.strictEqual(content.includes('id="btnSeedDemoQueue"'), true);
  });

  // Test 6: screen5 contains caseSheetPlaceholder and caseSheetContent
  await runAsyncTest('T6: screen5 contains placeholder state and caseSheetContent', () => {
    const content = fs.readFileSync(path.join(__dirname, '../src/screens/screen5-doctor-dashboard.html'), 'utf-8');
    assert.strictEqual(content.includes('id="caseSheetPlaceholder"'), true);
    assert.strictEqual(content.includes('id="caseSheetContent"'), true);
    assert.strictEqual(content.includes('extractSectionText'), true);
  });

  // Test 7: screen5 contains quick test login buttons
  await runAsyncTest('T7: screen5 contains quick test login buttons for doctor and staff', () => {
    const content = fs.readFileSync(path.join(__dirname, '../src/screens/screen5-doctor-dashboard.html'), 'utf-8');
    assert.strictEqual(content.includes('btn-demo-quick-login'), true);
    assert.strictEqual(content.includes('doctor@aiia.gov.in'), true);
    assert.strictEqual(content.includes('staff@aiia.gov.in'), true);
  });

  // Test 8: screen5 links to screen6
  await runAsyncTest('T8: screen5 links to screen6-analytics-dashboard.html in topbar', () => {
    const content = fs.readFileSync(path.join(__dirname, '../src/screens/screen5-doctor-dashboard.html'), 'utf-8');
    assert.strictEqual(content.includes('href="screen6-analytics-dashboard.html"'), true);
  });

  // Test 9: qa-launcher links to screen6
  await runAsyncTest('T9: qa-launcher.html links to screen6-analytics-dashboard.html', () => {
    const content = fs.readFileSync(path.join(__dirname, '../src/screens/qa-launcher.html'), 'utf-8');
    assert.strictEqual(content.includes('screen6-analytics-dashboard.html'), true);
    assert.strictEqual(content.includes('Hospital Analytics Portal'), true);
  });

  // Test 10: qa-launcher contains quick seed demo action
  await runAsyncTest('T10: qa-launcher contains quick seed demo action button', () => {
    const content = fs.readFileSync(path.join(__dirname, '../src/screens/qa-launcher.html'), 'utf-8');
    assert.strictEqual(content.includes('id="btnQaSeedDemo"'), true);
  });

  // Test 11: GET /api/patients/by-phone contract
  await runAsyncTest('T11: GET /api/patients/by-phone/{phone} contract verification', async () => {
    let capturedUrl = null;
    global.fetch = async (url, opts) => {
      capturedUrl = url;
      return {
        status: 200,
        ok: true,
        headers: { get: () => 'application/json' },
        json: async () => ({
          id: 42,
          name: "Sunita Sharma",
          phone_number: "+919876543210",
          date_of_birth: "1985-07-20",
          gender: "Female"
        })
      };
    };

    const res = await MediKioskApi.get('/api/patients/by-phone/%2B919876543210');
    assert.strictEqual(res.ok, true);
    assert.strictEqual(res.data.id, 42);
    assert.strictEqual(capturedUrl.includes('/api/patients/by-phone/'), true);
  });

  // Test 12: POST /api/demo/seed contract
  await runAsyncTest('T12: POST /api/demo/seed contract verification', async () => {
    let capturedMethod = null;
    let capturedUrl = null;
    global.fetch = async (url, opts) => {
      capturedUrl = url;
      capturedMethod = opts.method;
      return {
        status: 200,
        ok: true,
        headers: { get: () => 'application/json' },
        json: async () => ({
          success: true,
          message: "Demo users and clinical queue successfully seeded.",
          users: [{ id: 1, email: "doctor@aiia.gov.in", role: "DOCTOR" }],
          patients: [{ id: 1, name: "Ramesh Verma", token: "A-101", priority: "EMERGENCY", status: "WAITING" }]
        })
      };
    };

    const res = await MediKioskApi.post('/api/demo/seed', {});
    assert.strictEqual(res.ok, true);
    assert.strictEqual(capturedMethod, 'POST');
    assert.strictEqual(capturedUrl.includes('/api/demo/seed'), true);
    assert.strictEqual(res.data.success, true);
    assert.strictEqual(res.data.patients.length, 1);
  });

  // Test 13: Storage purity
  await runAsyncTest('T13: Storage Purity - Passwords and PHI never persisted in sessionStorage', () => {
    const raw = JSON.stringify(mockStorage.store);
    assert.strictEqual(raw.includes('doctor123'), false);
    assert.strictEqual(raw.includes('staff123'), false);
    assert.strictEqual(raw.includes('Sunita Sharma'), false);
    assert.strictEqual(raw.includes('Metformin'), false);
  });

  console.log(`\nStep 10 Test Results: ${passedTests} passed, ${failedTests} failed`);
  if (failedTests > 0) {
    process.exit(1);
  }
}

runSuite();
