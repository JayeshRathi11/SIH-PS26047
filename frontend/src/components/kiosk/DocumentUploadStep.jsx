import React, { useState } from 'react';
import { Upload, FileText, Camera, CheckCircle2, Clock, Trash2, ArrowRight, ArrowLeft, ShieldAlert } from 'lucide-react';

const DOC_TYPES = [
  { value: 'PRESCRIPTION', label: 'पर्चा / Prescription' },
  { value: 'DISCHARGE_SUMMARY', label: 'डिस्चार्ज सारांश / Discharge Summary' },
  { value: 'LAB_REPORT', label: 'लैब रिपोर्ट / Lab Report' },
  { value: 'OTHER', label: 'अन्य / Other' }
];

export default function DocumentUploadStep({ patient, onComplete, onBack }) {
  const [documents, setDocuments] = useState([]);
  const [selectedType, setSelectedType] = useState('PRESCRIPTION');
  const [isProcessing, setIsProcessing] = useState(false);

  const handleFileUpload = (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;

    setIsProcessing(true);
    // Simulate OCR pipeline steps
    setTimeout(() => {
      const newDocs = files.map((file, idx) => ({
        id: `doc-${Date.now()}-${idx}`,
        name: file.name,
        size: `${(file.size / 1024).toFixed(1)} KB`,
        type: selectedType,
        uploadedAt: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        ocrStatus: 'COMPLETED',
        extractedEntities: [
          'Tab Ashwagandha 500mg (BD)',
          'Paracetamol 650mg SOS',
          'BP: 130/85 mmHg'
        ]
      }));

      setDocuments(prev => [...prev, ...newDocs]);
      setIsProcessing(false);
    }, 1200);
  };

  const removeDoc = (id) => {
    setDocuments(prev => prev.filter(d => d.id !== id));
  };

  const handleProceed = () => {
    onComplete({
      documents,
      count: documents.length
    });
  };

  return (
    <div className="max-w-3xl mx-auto py-6 px-4">
      <div className="bg-white rounded-2xl shadow-xl border border-stone-200 overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-ayush-primary to-ayush-primary-dark text-white p-6 sm:p-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl bg-white/10 backdrop-blur flex items-center justify-center border border-white/20">
                <Upload className="w-7 h-7 text-ayush-accent" />
              </div>
              <div>
                <h2 className="text-2xl sm:text-3xl font-bold font-serif">
                  दस्तावेज़ अपलोड / Prior Medical Records
                </h2>
                <p className="text-emerald-100 text-sm mt-1">
                  पुराने पर्चे, लैब रिपोर्ट या डिस्चार्ज सारांश स्कैन करें (वैकल्पिक)
                </p>
              </div>
            </div>
            <span className="text-xs bg-white/10 px-3 py-1.5 rounded-full border border-white/20">
              Zero-Retention Policy
            </span>
          </div>
        </div>

        <div className="p-6 sm:p-8 space-y-6">
          {/* Document Type Selector */}
          <div>
            <label className="block text-sm font-semibold text-stone-700 mb-2">
              दस्तावेज़ का प्रकार चुनें / Select Document Category:
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {DOC_TYPES.map((dt) => (
                <button
                  key={dt.value}
                  type="button"
                  onClick={() => setSelectedType(dt.value)}
                  className={`min-h-[44px] px-3 py-2 rounded-xl text-xs font-medium border transition-all ${
                    selectedType === dt.value
                      ? 'bg-ayush-primary text-white border-ayush-primary shadow-sm ring-2 ring-ayush-primary/20'
                      : 'bg-stone-50 text-stone-700 border-stone-200 hover:bg-stone-100'
                  }`}
                >
                  {dt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Upload Dropzone */}
          <div className="border-2 border-dashed border-stone-300 rounded-2xl p-6 sm:p-8 text-center hover:border-ayush-primary/60 transition bg-stone-50/50">
            <input
              type="file"
              id="doc-upload-input"
              multiple
              accept="image/*,application/pdf"
              onChange={handleFileUpload}
              className="hidden"
            />
            <label
              htmlFor="doc-upload-input"
              className="cursor-pointer flex flex-col items-center justify-center space-y-3"
            >
              <div className="w-16 h-16 rounded-full bg-emerald-50 border border-emerald-200 flex items-center justify-center text-ayush-primary">
                <Upload className="w-8 h-8" />
              </div>
              <div>
                <p className="text-base font-bold text-stone-800">
                  फाइल चुनें या यहाँ खींचें / Choose File or Drag & Drop
                </p>
                <p className="text-xs text-stone-500 mt-1">
                  JPG, PNG, PDF (अधिकतम 10MB) • Supported formats
                </p>
              </div>
              <span className="min-h-[44px] px-5 py-2 rounded-xl bg-white border border-stone-300 text-stone-700 font-semibold text-sm shadow-sm hover:bg-stone-100 transition inline-flex items-center gap-2">
                <Camera className="w-4 h-4 text-ayush-primary" />
                कैमरा / ब्राउज़ करें / Browse Files
              </span>
            </label>
          </div>

          {/* OCR Processing State */}
          {isProcessing && (
            <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 flex items-center gap-3 text-sm text-emerald-800">
              <Clock className="w-5 h-5 animate-spin text-ayush-primary" />
              <span>
                दस्तावेज़ का ओसीआर और आयुष शब्द सामान्यीकरण हो रहा है... / Extracting entities via OCR & AFI Normalizer...
              </span>
            </div>
          )}

          {/* Uploaded Documents List */}
          {documents.length > 0 && (
            <div className="space-y-3">
              <h4 className="text-sm font-bold text-stone-800">
                अपलोड किए गए दस्तावेज़ / Processed Documents ({documents.length}):
              </h4>
              <div className="space-y-2">
                {documents.map((doc) => (
                  <div
                    key={doc.id}
                    className="p-3.5 rounded-xl border border-stone-200 bg-white flex items-center justify-between gap-3 shadow-sm"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-emerald-50 border border-emerald-200 flex items-center justify-center text-ayush-primary">
                        <FileText className="w-5 h-5" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-sm text-stone-900">{doc.name}</span>
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-medium">
                            {doc.type}
                          </span>
                        </div>
                        <p className="text-xs text-stone-500">
                          {doc.size} • {doc.uploadedAt} • OCR विश्लेषित
                        </p>
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={() => removeDoc(doc.id)}
                      className="p-2 text-stone-400 hover:text-rose-600 rounded-lg hover:bg-stone-50 transition"
                      title="हटाएं / Remove"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Navigation Controls */}
          <div className="pt-6 border-t border-stone-200 flex items-center justify-between gap-4">
            <button
              type="button"
              onClick={onBack}
              className="min-h-[48px] px-6 py-2.5 rounded-xl border border-stone-300 text-stone-700 font-semibold hover:bg-stone-100 transition flex items-center gap-2"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>पीछे / Back</span>
            </button>

            <button
              type="button"
              onClick={handleProceed}
              className="min-h-[52px] px-8 py-3 bg-ayush-primary hover:bg-ayush-primary-dark text-white rounded-xl font-bold text-base shadow-lg shadow-ayush-primary/20 flex items-center gap-3 transition-all transform active:scale-95"
            >
              <span>
                {documents.length > 0 ? 'पुष्टि करें / Review & Confirm' : 'छोड़ें और आगे बढ़ें / Skip & Continue'}
              </span>
              <ArrowRight className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
