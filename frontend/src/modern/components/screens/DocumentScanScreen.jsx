import React, { useState } from 'react';
import { UploadCloud, Camera, FileText, CheckCircle2, Trash2, Sparkles, AlertCircle } from 'lucide-react';
import { useKioskSession } from '../../context/KioskSessionContext';
import ClayCard from '../atoms/ClayCard';
import ClayButton from '../atoms/ClayButton';
import ClayBadge from '../atoms/ClayBadge';
import { MediKioskApi } from '../../services/api';

export default function DocumentScanScreen({ onProceed }) {
  const { documents, addDocument, removeDocument, patient } = useKioskSession();
  const [uploading, setUploading] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);

  const mockExtractDocument = (fileName) => {
    return {
      id: Date.now(),
      fileName: fileName || 'Prescription_AIIA_2026.jpg',
      docType: 'Prescription',
      confidence: '96%',
      extractedMeds: [
        { name: 'Sudarshan Vati', dosage: '2 tablets', freq: 'Twice daily', duration: '5 days' },
        { name: 'Mahasudarshan Churna', dosage: '3 grams', freq: 'After food with warm water', duration: '7 days' },
        { name: 'Ashwagandha Capsule', dosage: '1 cap', freq: 'At bedtime with milk', duration: '15 days' }
      ],
      doctorNotes: 'विगत 4 दिनों से हल्का ज्वर एवं अंगमर्द। वात-कफ शामक चिकित्सा परामर्श।',
      previewUrl: 'https://images.unsplash.com/photo-1584515979956-d9f6e5d09982?w=400&auto=format&fit=crop&q=80'
    };
  };

  const handleSimulateUpload = (name) => {
    setUploading(true);
    setTimeout(() => {
      const newDoc = mockExtractDocument(name);
      addDocument(newDoc);
      setUploading(false);
      setSelectedFile(null);
    }, 1800);
  };

  return (
    <div className="flex-1 flex flex-col max-w-5xl mx-auto w-full py-2">
      {/* Title */}
      <div className="text-center mb-6">
        <ClayBadge variant="ayush" className="mb-2">
          चरण 4 • Step 4
        </ClayBadge>
        <h2 className="font-display font-extrabold text-heading sm:text-title text-teak-grey">
          पुराने पर्चे व मेडिकल रिपोर्ट स्कैन • Document &amp; OCR
        </h2>
        <p className="text-caption text-teak-muted max-w-lg mx-auto">
          सर्वम विजन (Sarvam Vision OCR) द्वारा आपके पुराने पर्चों से दवाइयों और पूर्व उपचार का स्वतः विश्लेषण किया जाएगा।
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Upload Dropzone & Camera Trigger */}
        <div className="lg:col-span-5 flex flex-col gap-4">
          <ClayCard className="p-6 flex flex-col items-center text-center border-2 border-dashed border-haritaki-gold/60">
            <div className="w-16 h-16 rounded-full bg-cream-warm border border-haritaki-gold text-haritaki-deep flex items-center justify-center mb-3 shadow-pill">
              <UploadCloud className="w-8 h-8" />
            </div>

            <h3 className="font-display font-bold text-btn-sec text-teak-grey mb-1">
              दस्तावेज अपलोड करें • Upload Document
            </h3>
            <p className="text-caption text-teak-muted mb-4">
              पुराना पर्चा, लैब रिपोर्ट या डिस्चार्ज समरी की फोटो खींचें या अपलोड करें
            </p>

            <div className="flex flex-col w-full gap-2.5">
              <ClayButton
                variant="primary-gold"
                size="md"
                onClick={() => handleSimulateUpload('Prescription_Card_AIIA.jpg')}
                loading={uploading}
                icon={<Camera className="w-4 h-4" />}
                className="w-full"
              >
                कैमरा स्कैन / Camera Capture
              </ClayButton>

              <ClayButton
                variant="neutral"
                size="md"
                onClick={() => handleSimulateUpload('Lab_Report_Blood_Test.pdf')}
                loading={uploading}
                icon={<FileText className="w-4 h-4" />}
                className="w-full"
              >
                फ़ाइल अपलोड / Choose File
              </ClayButton>
            </div>
          </ClayCard>

          {/* Privacy Note */}
          <div className="bg-cream-recess p-3.5 rounded-card border border-copper-border/50 text-xs text-teak-muted flex items-start gap-2 shadow-inset-recess">
            <Sparkles className="w-4 h-4 text-haritaki-deep flex-shrink-0 mt-0.5" />
            <span>
              ओसीआर निष्कर्षण उपरांत मूल छवि को सुरक्षा कारणों से 24 घंटे में स्थायी रूप से हटा दिया जाता है।
            </span>
          </div>
        </div>

        {/* Right Column: Extracted Documents Preview List */}
        <div className="lg:col-span-7 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h3 className="font-display font-bold text-heading text-teak-grey">
              स्कैन किए गए दस्तावेज ({documents.length})
            </h3>
            {documents.length > 0 && (
              <ClayBadge variant="success">
                <CheckCircle2 className="w-3.5 h-3.5" /> OCR विश्लेषित
              </ClayBadge>
            )}
          </div>

          {documents.length === 0 ? (
            <ClayCard className="p-8 text-center flex flex-col items-center justify-center min-h-[260px] text-teak-muted border border-copper-border/60">
              <FileText className="w-12 h-12 text-copper-patina mb-2 opacity-50" />
              <p className="text-body font-semibold">कोई दस्तावेज स्कैन नहीं किया गया</p>
              <p className="text-caption mt-1">यदि आपके पास पुराना पर्चा नहीं है, तो आप 'छोड़ें / Skip' बटन दबा सकते हैं।</p>
            </ClayCard>
          ) : (
            <div className="flex flex-col gap-4">
              {documents.map((doc) => (
                <ClayCard key={doc.id} className="p-5 border border-haritaki-gold/50 shadow-card">
                  {/* Document Header */}
                  <div className="flex items-center justify-between border-b border-copper-border/40 pb-3 mb-3">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-btn bg-cream-warm border border-haritaki-gold flex items-center justify-center text-haritaki-deep font-bold">
                        <FileText className="w-5 h-5" />
                      </div>
                      <div>
                        <h4 className="font-display font-bold text-btn-sec text-teak-grey">
                          {doc.fileName}
                        </h4>
                        <div className="flex items-center gap-2 text-xs text-teak-muted">
                          <span>{doc.docType}</span>
                          <span>&bull;</span>
                          <span className="text-herbal-green font-bold font-mono">
                            सर्वम विजन विश्वसनीयता: {doc.confidence}
                          </span>
                        </div>
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={() => removeDocument(doc.id)}
                      className="text-copper-patina hover:text-manjistha-red p-1.5 rounded-full transition-all cursor-pointer"
                      title="हटाएं / Remove"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>

                  {/* Extracted Medicines */}
                  <div className="mb-3">
                    <span className="text-xs font-bold text-haritaki-deep block mb-1.5 uppercase tracking-wider">
                      पहचानी गई औषधियां (Extracted Medications):
                    </span>
                    <div className="flex flex-wrap gap-2">
                      {doc.extractedMeds.map((med, idx) => (
                        <div key={idx} className="bg-cream-warm/70 px-3 py-1.5 rounded-btn border border-haritaki-gold/30 text-xs">
                          <strong className="text-teak-grey font-display">{med.name}</strong>
                          <span className="text-teak-muted ml-1 font-mono">({med.dosage}, {med.freq})</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Doctor Notes */}
                  {doc.doctorNotes && (
                    <div className="bg-cream-recess p-2.5 rounded-btn border border-copper-border/40 text-xs text-teak-grey">
                      <span className="font-bold text-teak-muted mr-1">चिकित्सक टिप्पणी:</span>
                      <span>{doc.doctorNotes}</span>
                    </div>
                  )}
                </ClayCard>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
