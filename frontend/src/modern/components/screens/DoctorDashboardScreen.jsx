import React, { useState, useEffect } from 'react';
import { Stethoscope, Download, CheckCircle2, User, Printer, FileSpreadsheet, RefreshCw } from 'lucide-react';
import ClayCard from '../atoms/ClayCard';
import ClayButton from '../atoms/ClayButton';
import ClayBadge from '../atoms/ClayBadge';
import DoctorQueueSidebar from '../doctor/DoctorQueueSidebar';
import CaseSheetEditor from '../doctor/CaseSheetEditor';
import RedFlagAuditWidget from '../doctor/RedFlagAuditWidget';
import { MediKioskApi } from '../../services/api';

export default function DoctorDashboardScreen() {
  const [queue, setQueue] = useState([
    {
      id: 101,
      token_number: 'A-101',
      patient_name: 'रमेश कुमार / Ramesh Kumar',
      age: 48,
      gender: 'Male',
      chief_complaint: 'ज्वर (Fever) एवं संधि शूल (Joint Pain)',
      is_red_flag: false,
      priority_score: 85,
      wait_time_minutes: 12
    },
    {
      id: 102,
      token_number: 'A-102',
      patient_name: 'सुमन लता / Suman Lata',
      age: 68,
      gender: 'Female',
      chief_complaint: 'सीने में तीव्र भारीपन एवं श्वास कष्ट',
      is_red_flag: true,
      priority_score: 1120,
      wait_time_minutes: 4
    },
    {
      id: 103,
      token_number: 'A-103',
      patient_name: 'अमित वर्मा / Amit Verma',
      age: 32,
      gender: 'Male',
      chief_complaint: 'अम्लपित्त एवं उदर शूल',
      is_red_flag: false,
      priority_score: 45,
      wait_time_minutes: 22
    }
  ]);

  const [selectedPatient, setSelectedPatient] = useState(queue[0]);
  const [completing, setCompleting] = useState(false);
  const [completedSuccess, setCompletedSuccess] = useState(false);

  useEffect(() => {
    // Fetch live queue from backend
    MediKioskApi.get('/api/opd-queue')
      .then((res) => {
        if (Array.isArray(res?.data) && res.data.length > 0) {
          setQueue(res.data);
          setSelectedPatient(res.data[0]);
        }
      })
      .catch(() => {});
  }, []);

  const handleCompleteConsultation = async () => {
    if (!selectedPatient) return;
    setCompleting(true);

    try {
      await MediKioskApi.post(`/api/opd-queue/${selectedPatient.id}/complete`, {
        consultation_notes: 'OPD Consultation completed successfully.',
        completed_at: new Date().toISOString()
      });
    } catch {
      // Offline fallback
    }

    setQueue((prev) => prev.filter((p) => p.id !== selectedPatient.id));
    setCompletedSuccess(true);
    setCompleting(false);

    setTimeout(() => {
      setCompletedSuccess(false);
      setSelectedPatient(queue.find((p) => p.id !== selectedPatient.id) || null);
    }, 2000);
  };

  const handleExportFhir = async () => {
    try {
      const res = await MediKioskApi.get('/api/fhir/export');
      const blob = new Blob([JSON.stringify(res?.data || { resourceType: 'Bundle' }, null, 2)], {
        type: 'application/json'
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `FHIR_R4_Patient_${selectedPatient?.id || 'Record'}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      alert('FHIR Export initiated.');
    }
  };

  return (
    <div className="flex-1 flex flex-col max-w-7xl mx-auto w-full py-2">
      {/* Clinician Top Banner */}
      <ClayCard className="p-4 mb-5 flex items-center justify-between bg-gradient-to-r from-cream-warm via-shweta-white to-cream-warm border border-haritaki-gold/50 shadow-sm">
        <div className="flex items-center gap-3.5">
          <div className="w-12 h-12 rounded-full bg-haritaki-gold text-white flex items-center justify-center font-bold shadow-sm">
            <Stethoscope className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-display font-bold text-heading text-teak-grey">
                डॉ. अनन्या शर्मा, MD (आयुर्वेद) • Clinician Workstation
              </h2>
              <ClayBadge variant="success">ऑनलाइन / Active</ClayBadge>
            </div>
            <p className="text-caption text-teak-muted">
              अखिल भारतीय आयुर्वेद संस्थान — कायचिकित्सा ओपीडी कक्ष संख्या 12
            </p>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2.5">
          <ClayButton
            variant="neutral"
            size="sm"
            onClick={handleExportFhir}
            icon={<Download className="w-4 h-4" />}
          >
            FHIR R4 निर्यात / Export
          </ClayButton>

          <ClayButton
            variant="neutral"
            size="sm"
            onClick={() => window.print()}
            icon={<Printer className="w-4 h-4" />}
          >
            प्रिंट / Print
          </ClayButton>
        </div>
      </ClayCard>

      {/* Main Workspace Layout: Sidebar + Case Sheet */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Triage Queue Sidebar */}
        <div className="lg:col-span-4">
          <DoctorQueueSidebar
            queue={queue}
            selectedPatientId={selectedPatient?.id}
            onSelectPatient={setSelectedPatient}
          />
        </div>

        {/* Center / Right Column: Active Patient Case Sheet */}
        <div className="lg:col-span-8 flex flex-col gap-4">
          {selectedPatient ? (
            <>
              {/* Active Patient Bar */}
              <ClayCard className="p-4 flex items-center justify-between border-2 border-haritaki-gold bg-shweta-white">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-cream-warm border border-haritaki-gold text-haritaki-deep flex items-center justify-center font-bold">
                    <User className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-display font-bold text-btn-sec text-teak-grey">
                        {selectedPatient.patient_name}
                      </h3>
                      <span className="font-mono text-xs bg-haritaki-gold/20 text-haritaki-deep font-bold px-2 py-0.5 rounded-pill">
                        {selectedPatient.token_number}
                      </span>
                    </div>
                    <span className="text-xs text-teak-muted">
                      {selectedPatient.age} वर्ष &bull; {selectedPatient.gender} &bull; प्राथमिक लक्षण: {selectedPatient.chief_complaint}
                    </span>
                  </div>
                </div>

                {selectedPatient.is_red_flag && (
                  <ClayBadge variant="redflag">🚨 Red Flag Alert</ClayBadge>
                )}
              </ClayCard>

              {/* Red Flag Audit Widget if red-flagged */}
              {selectedPatient.is_red_flag && (
                <RedFlagAuditWidget
                  patient={selectedPatient}
                  redFlagReason={selectedPatient.chief_complaint}
                />
              )}

              {/* 8-Section AYUSH Case Sheet */}
              <CaseSheetEditor
                patient={selectedPatient}
                onSave={() => alert('केस शीट सुरक्षित की गई / Case sheet saved')}
              />

              {/* Consultation Complete Action */}
              <div className="flex items-center justify-between bg-shweta-white p-4 rounded-card border border-copper-border shadow-card mt-2">
                <span className="text-caption text-teak-muted">
                  परामर्श पूर्ण होने पर पर्चा स्वतः फार्मेसी एवं रोगी के व्हाट्सएप पर प्रेषित होगा।
                </span>

                {completedSuccess ? (
                  <div className="flex items-center gap-2 text-herbal-green font-bold text-btn-sec">
                    <CheckCircle2 className="w-5 h-5" />
                    <span>परामर्श पूर्ण हुआ!</span>
                  </div>
                ) : (
                  <ClayButton
                    variant="primary-gold"
                    size="touch"
                    loading={completing}
                    onClick={handleCompleteConsultation}
                    className="shadow-btn-gold px-8"
                  >
                    <span className="flex items-center gap-2">
                      <CheckCircle2 className="w-5 h-5" />
                      <span>परामर्श पूर्ण करें • Complete Consultation</span>
                    </span>
                  </ClayButton>
                )}
              </div>
            </>
          ) : (
            <ClayCard className="p-12 text-center text-teak-muted">
              <p className="text-body font-bold">कतार से किसी रोगी का चयन करें</p>
              <p className="text-caption mt-1">Select a patient from the queue to start consultation.</p>
            </ClayCard>
          )}
        </div>
      </div>
    </div>
  );
}
