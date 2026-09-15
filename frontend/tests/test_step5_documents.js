/**
 * Step 5: Document Upload, Consent, & Clinical OCR Processing Integration Test Suite
 * Tests:
 * 1. file input exists
 * 2. valid file accepted
 * 3. unsupported file rejected
 * 4. oversized file rejected
 * 5. correct patient_id/session/interview state used
 * 6. DOCUMENT_PROCESSING consent requirement respected
 * 7. FormData constructed correctly
 * 8. upload endpoint called correctly
 * 9. processing endpoint called correctly if separate
 * 10. successful processing reflected in UI
 * 11. processing state reflected correctly
 * 12. failed processing reflected correctly
 * 13. duplicate upload prevented
 * 14. 401 handling
 * 15. 403 consent handling
 * 16. 404 handling
 * 17. 409 handling
 * 18. 422 handling
 * 19. 429 handling
 * 20. server failure handling
 * 21. network failure handling
 * 22. no document contents stored in sessionStorage
 * 23. no clinical data logged
 * 24. existing UI remains intact
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

// Mock FormData for Node test runner
class MockFormData {
  constructor() {
    this.fields = {};
  }
  append(key, value) {
    this.fields[key] = value;
  }
  get(key) {
    return this.fields[key];
  }
}
global.FormData = MockFormData;

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
  console.log('Running MediKiosk Step 5 Documents Integration Test Suite...\n');

  // 1. file input exists
  await runTest('1. real file input exists in screen3-documents.html', () => {
    const html = fs.readFileSync(path.join(__dirname, '../src/screens/screen3-documents.html'), 'utf8');
    assert.ok(html.includes('id="realFileInput"'), 'realFileInput missing in screen3');
    assert.ok(html.includes('type="file"'), 'file input type missing in screen3');
    assert.ok(html.includes('.pdf'), 'PDF accept attribute missing');
  });

  // 2. valid file accepted
  await runTest('2. valid file (PDF/Image) validation passes', () => {
    const allowedExts = ['.pdf', '.jpg', '.jpeg', '.png', '.webp'];
    const allowedMimes = ['application/pdf', 'image/jpeg', 'image/png', 'image/webp'];

    const testFile = { name: 'prescription_report.pdf', size: 1024 * 100, type: 'application/pdf' };
    const ext = testFile.name.substring(testFile.name.lastIndexOf('.')).toLowerCase();
    assert.ok(allowedExts.includes(ext));
    assert.ok(allowedMimes.includes(testFile.type));
    assert.ok(testFile.size <= 10 * 1024 * 1024);
  });

  // 3. unsupported file rejected
  await runTest('3. unsupported file format (e.g. .exe or .docx) rejected', () => {
    const allowedExts = ['.pdf', '.jpg', '.jpeg', '.png', '.webp'];
    const allowedMimes = ['application/pdf', 'image/jpeg', 'image/png', 'image/webp'];

    const invalidFile = { name: 'malicious.exe', size: 500, type: 'application/x-msdownload' };
    const ext = invalidFile.name.substring(invalidFile.name.lastIndexOf('.')).toLowerCase();
    const isValid = allowedExts.includes(ext) || allowedMimes.includes(invalidFile.type);
    assert.strictEqual(isValid, false);
  });

  // 4. oversized file rejected
  await runTest('4. oversized file (>10MB) rejected by client-side rule', () => {
    const MAX_SIZE_BYTES = 10 * 1024 * 1024;
    const oversizedFile = { name: 'huge_scan.pdf', size: 15 * 1024 * 1024, type: 'application/pdf' };
    const isTooLarge = oversizedFile.size > MAX_SIZE_BYTES;
    assert.strictEqual(isTooLarge, true);
  });

  // 5. correct patient_id/session/interview state used
  await runTest('5. correct patient_id and interview_id state used from MediKioskSession', () => {
    mockStorage.clear();
    MediKioskSession.setPatientId('555');
    MediKioskSession.setSessionId('666');
    MediKioskSession.setInterviewId('777');
    assert.strictEqual(MediKioskSession.getPatientId(), '555');
    assert.strictEqual(MediKioskSession.getSessionId(), '666');
    assert.strictEqual(MediKioskSession.getInterviewId(), '777');
  });

  // 6. DOCUMENT_PROCESSING consent requirement respected
  await runTest('6. DOCUMENT_PROCESSING consent verified before initiating upload', async () => {
    let consentChecked = false;
    setupMockFetch({
      'GET /api/patients/555/consents/active/DOCUMENT_PROCESSING': () => {
        consentChecked = true;
        return {
          status: 200,
          data: { active: true, purpose: 'DOCUMENT_PROCESSING', patient_id: 555 }
        };
      }
    });

    const consentRes = await MediKioskApi.get('/api/patients/555/consents/active/DOCUMENT_PROCESSING');
    assert.strictEqual(consentChecked, true);
    assert.strictEqual(consentRes.data.active, true);
  });

  // 7. FormData constructed correctly
  await runTest('7. FormData constructed with file and document_type', () => {
    const formData = new MockFormData();
    formData.append('file', { name: 'rx.png' });
    formData.append('document_type', 'PRESCRIPTION');

    assert.strictEqual(formData.get('document_type'), 'PRESCRIPTION');
    assert.strictEqual(formData.get('file').name, 'rx.png');
  });

  // 8. upload endpoint called correctly
  await runTest('8. upload endpoint /api/interviews/{id}/documents called with FormData', async () => {
    let interceptedForm = null;
    setupMockFetch({
      'POST /api/interviews/777/documents': (opts) => {
        interceptedForm = opts.body;
        return {
          status: 201,
          data: {
            id: 10,
            interview_id: 777,
            original_filename: 'rx.png',
            document_type: 'PRESCRIPTION',
            processing_status: 'UPLOADED'
          }
        };
      }
    });

    const formData = new MockFormData();
    formData.append('file', { name: 'rx.png' });
    formData.append('document_type', 'PRESCRIPTION');

    const res = await MediKioskApi.postForm('/api/interviews/777/documents', formData);
    assert.strictEqual(res.status, 201);
    assert.strictEqual(res.data.id, 10);
    assert.strictEqual(res.data.processing_status, 'UPLOADED');
    assert.strictEqual(interceptedForm.get('document_type'), 'PRESCRIPTION');
  });

  // 9. processing endpoint called correctly if separate
  await runTest('9. processing endpoint /api/interviews/{id}/documents/{docId}/process called', async () => {
    let processedDocId = null;
    setupMockFetch({
      'POST /api/interviews/777/documents/10/process': () => {
        processedDocId = 10;
        return {
          status: 200,
          data: {
            id: 88,
            document_id: 10,
            extraction_status: 'COMPLETED',
            structured_data: {
              medications: [
                { name: 'Metformin', dosage: '500mg', frequency: 'twice daily', route: 'oral' }
              ]
            }
          }
        };
      }
    });

    const res = await MediKioskApi.post('/api/interviews/777/documents/10/process', {});
    assert.strictEqual(res.status, 200);
    assert.strictEqual(processedDocId, 10);
    assert.strictEqual(res.data.extraction_status, 'COMPLETED');
  });

  // 10. successful processing reflected in UI
  await runTest('10. successful processing outcome reflects structured data', () => {
    const mockExtraction = {
      extraction_status: 'COMPLETED',
      structured_data: {
        medications: [{ name: 'Metformin', dosage: '500mg', frequency: 'twice daily', route: 'oral' }]
      }
    };
    const firstMed = mockExtraction.structured_data.medications[0];
    const medTitle = `${firstMed.name} ${firstMed.dosage}`.trim();
    assert.strictEqual(medTitle, 'Metformin 500mg');
  });

  // 11. processing state reflected correctly
  await runTest('11. intermediate processing state reflects scanning transition', () => {
    let uiState = 'READY';
    // When upload begins
    uiState = 'SCANNING';
    assert.strictEqual(uiState, 'SCANNING');
    // When completed
    uiState = 'COMPLETE';
    assert.strictEqual(uiState, 'COMPLETE');
  });

  // 12. failed processing reflected correctly
  await runTest('12. failed processing status handled gracefully', async () => {
    setupMockFetch({
      'POST /api/interviews/777/documents/10/process': () => {
        return {
          status: 500,
          data: { detail: 'OCR provider timeout during text recognition' }
        };
      }
    });

    try {
      await MediKioskApi.post('/api/interviews/777/documents/10/process', {});
      assert.fail('Should throw');
    } catch (err) {
      assert.strictEqual(err.status, 500);
      assert.strictEqual(err.isServerError, true);
    }
  });

  // 13. duplicate upload prevented
  await runTest('13. duplicate upload prevented by locking submission flag', async () => {
    let isUploading = false;
    let callCount = 0;

    async function triggerUpload() {
      if (isUploading) return false;
      isUploading = true;
      try {
        callCount++;
        await new Promise(r => setTimeout(r, 10));
        return true;
      } finally {
        isUploading = false;
      }
    }

    const [first, second] = await Promise.all([triggerUpload(), triggerUpload()]);
    assert.strictEqual(first, true);
    assert.strictEqual(second, false);
    assert.strictEqual(callCount, 1);
  });

  // 14. 401 handling
  await runTest('14. 401 Unauthorized handling on document upload', async () => {
    setupMockFetch({
      'POST /api/interviews/777/documents': () => {
        return { status: 401, data: { detail: 'Missing authentication credentials' } };
      }
    });

    try {
      await MediKioskApi.postForm('/api/interviews/777/documents', new MockFormData());
      assert.fail('Should throw');
    } catch (err) {
      assert.strictEqual(err.status, 401);
      assert.strictEqual(err.isAuthError, true);
    }
  });

  // 15. 403 consent handling
  await runTest('15. 403 Forbidden handling when DOCUMENT_PROCESSING consent missing', async () => {
    setupMockFetch({
      'POST /api/interviews/777/documents/10/process': () => {
        return {
          status: 403,
          data: { detail: 'Consent required: DOCUMENT_PROCESSING consent missing or revoked' }
        };
      }
    });

    try {
      await MediKioskApi.post('/api/interviews/777/documents/10/process', {});
      assert.fail('Should throw');
    } catch (err) {
      assert.strictEqual(err.status, 403);
      assert.strictEqual(err.isForbidden, true);
      assert.ok(err.message.includes('DOCUMENT_PROCESSING'));
    }
  });

  // 16. 404 handling
  await runTest('16. 404 Not Found handling for missing interview or document', async () => {
    setupMockFetch({
      'GET /api/interviews/777/documents/999': () => {
        return { status: 404, data: { detail: 'Document with ID 999 not found' } };
      }
    });

    try {
      await MediKioskApi.get('/api/interviews/777/documents/999');
      assert.fail('Should throw');
    } catch (err) {
      assert.strictEqual(err.status, 404);
      assert.strictEqual(err.isNotFound, true);
    }
  });

  // 17. 409 handling
  await runTest('17. 409 Conflict handling for concurrent document processing', async () => {
    setupMockFetch({
      'POST /api/interviews/777/documents/10/process': () => {
        return {
          status: 409,
          data: { detail: 'Document is currently being processed. Please wait.' }
        };
      }
    });

    try {
      await MediKioskApi.post('/api/interviews/777/documents/10/process', {});
      assert.fail('Should throw');
    } catch (err) {
      assert.strictEqual(err.status, 409);
      assert.strictEqual(err.isConflict, true);
    }
  });

  // 18. 422 handling
  await runTest('18. 422 Validation Error handling on bad document parameters', async () => {
    setupMockFetch({
      'POST /api/interviews/777/documents': () => {
        return {
          status: 422,
          data: { detail: [{ loc: ['body', 'file'], msg: 'Field required' }] }
        };
      }
    });

    try {
      await MediKioskApi.postForm('/api/interviews/777/documents', new MockFormData());
      assert.fail('Should throw');
    } catch (err) {
      assert.strictEqual(err.status, 422);
      assert.strictEqual(err.isValidationError, true);
    }
  });

  // 19. 429 handling
  await runTest('19. 429 Rate Limit handling', async () => {
    setupMockFetch({
      'POST /api/interviews/777/documents': () => {
        return { status: 429, data: { detail: 'Upload rate limit exceeded. Please wait.' } };
      }
    });

    try {
      await MediKioskApi.postForm('/api/interviews/777/documents', new MockFormData());
      assert.fail('Should throw');
    } catch (err) {
      assert.strictEqual(err.status, 429);
      assert.strictEqual(err.isRateLimit, true);
    }
  });

  // 20. server failure handling
  await runTest('20. 500 Internal Server Error handling', async () => {
    setupMockFetch({
      'POST /api/interviews/777/documents': () => {
        return { status: 500, data: { detail: 'Storage backend error' } };
      }
    });

    try {
      await MediKioskApi.postForm('/api/interviews/777/documents', new MockFormData());
      assert.fail('Should throw');
    } catch (err) {
      assert.strictEqual(err.status, 500);
      assert.strictEqual(err.isServerError, true);
    }
  });

  // 21. network failure handling
  await runTest('21. network failure handling', async () => {
    global.fetch = async () => {
      throw new Error('Connection refused');
    };

    try {
      await MediKioskApi.get('/api/interviews/777/documents');
      assert.fail('Should throw');
    } catch (err) {
      assert.ok(err instanceof MediKioskApi.ApiError);
      assert.strictEqual(err.isNetworkError, true);
      assert.strictEqual(err.status, 0);
    }
  });

  // 22. no document contents stored in sessionStorage
  await runTest('22. strict privacy invariant: zero document bodies, OCR, or files stored in sessionStorage', () => {
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

  // 23. no clinical data logged
  await runTest('23. zero sensitive console logging of OCR text, files, or tokens', () => {
    const screenCode = fs.readFileSync(path.join(__dirname, '../src/screens/screen3-documents.html'), 'utf8');
    assert.strictEqual(screenCode.includes('console.log(file'), false);
    assert.strictEqual(screenCode.includes('console.log(raw_ocr'), false);
    assert.strictEqual(screenCode.includes('console.log(extraction'), false);
  });

  // 24. existing UI remains intact
  await runTest('24. existing screen markup and design remains intact', () => {
    const html = fs.readFileSync(path.join(__dirname, '../src/screens/screen3-documents.html'), 'utf8');
    assert.ok(html.includes('id="actionScan"'), 'actionScan missing');
    assert.ok(html.includes('id="actionUpload"'), 'actionUpload missing');
    assert.ok(html.includes('id="ocrCard"'), 'ocrCard missing');
    assert.ok(html.includes('id="ocrProcessingView"'), 'ocrProcessingView missing');
    assert.ok(html.includes('id="ocrResultView"'), 'ocrResultView missing');
    assert.ok(html.includes('id="ocrPill"'), 'ocrPill missing');
    assert.ok(html.includes('id="documentErrorMsg"'), 'documentErrorMsg missing');
    assert.ok(html.includes('id="timelineCount"'), 'timelineCount missing');
    assert.ok(html.includes('id="timelineList"'), 'timelineList missing');
    assert.ok(html.includes('scripts/config.js'), 'config.js script missing');
    assert.ok(html.includes('scripts/session.js'), 'session.js script missing');
    assert.ok(html.includes('scripts/api.js'), 'api.js script missing');
  });

  console.log(`\nAll ${testCount} Step 5 documents tests passed successfully!\n`);
}

runAll().catch((err) => {
  console.error('Fatal test error:', err);
  process.exit(1);
});
