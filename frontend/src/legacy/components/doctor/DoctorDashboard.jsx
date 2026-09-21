import React, { useState, useEffect } from 'react';
import QueueSidebar from './QueueSidebar';
import CaseSheetEditor from './CaseSheetEditor';
import { Activity, ShieldAlert, Users, Clock, Stethoscope } from 'lucide-react';

export default function DoctorDashboard() {
  const [queue, setQueue] = useState([]);
  const [selectedItem, setSelectedItem] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  const fetchQueue = async () => {
    setIsLoading(true);
    try {
      const res = await fetch('/api/opd-queue/');
      if (res.ok) {
        const data = await res.json();
        setQueue(data);
        if (data.length > 0 && !selectedItem) {
          setSelectedItem(data[0]);
        }
      } else {
        throw new Error('Failed to fetch queue');
      }
    } catch (err) {
      console.warn('Backend queue fetch failed, using fallback doctor mock data:', err);
      // Fallback mock queue
      const mockQueue = [
        {
          id: 'q-1',
          queue_number: 101,
          patient_id: 'p-1',
          patient: {
            id: 'p-1',
            name: 'राजेश कुमार / Rajesh Kumar',
            age: 68,
            gender: 'Male',
            phone: '9876543210',
            emergency_contact_phone: '9876500000'
          },
          status: 'WAITING',
          is_red_flag: true,
          priority_score: 1085.0,
          wait_time_minutes: 23,
          interview_id: 'int-101'
        },
        {
          id: 'q-2',
          queue_number: 102,
          patient_id: 'p-2',
          patient: {
            id: 'p-2',
            name: 'सुमन शर्मा / Suman Sharma',
            age: 42,
            gender: 'Female',
            phone: '9123456780',
            emergency_contact_phone: null
          },
          status: 'WAITING',
          is_red_flag: false,
          priority_score: 15.0,
          wait_time_minutes: 10,
          interview_id: 'int-102'
        },
        {
          id: 'q-3',
          queue_number: 103,
          patient_id: 'p-3',
          patient: {
            id: 'p-3',
            name: 'हरिप्रसाद वर्मा / Hariprasad Varma',
            age: 72,
            gender: 'Male',
            phone: '9988776655',
            emergency_contact_phone: '9988770000'
          },
          status: 'WAITING',
          is_red_flag: false,
          priority_score: 57.5,
          wait_time_minutes: 5,
          interview_id: 'int-103'
        }
      ];
      setQueue(mockQueue);
      if (!selectedItem) {
        setSelectedItem(mockQueue[0]);
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchQueue();
    const interval = setInterval(fetchQueue, 30000); // Polling every 30s
    return () => clearInterval(interval);
  }, []);

  const handleSelectPatient = (item) => {
    setSelectedItem(item);
  };

  const handleSaveCaseSheet = async (formData) => {
    console.log('Saved Case Sheet for patient:', selectedItem?.patient?.id, formData);
  };

  const totalWaiting = queue.filter(q => q.status === 'WAITING').length;
  const totalRedFlags = queue.filter(q => q.is_red_flag).length;
  const avgWaitTime = queue.length
    ? Math.round(queue.reduce((acc, curr) => acc + (curr.wait_time_minutes || 0), 0) / queue.length)
    : 0;

  return (
    <div className="flex flex-col h-full min-h-screen bg-stone-100">
      {/* Top Navbar */}
      <header className="bg-white border-b border-stone-200 px-6 py-3 flex items-center justify-between shadow-xs">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-ayush-primary text-white flex items-center justify-center font-bold">
            <Stethoscope className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-stone-900 font-serif">
              आयुष डॉक्टर वर्कस्टेशन / AYUSH Clinician Dashboard
            </h1>
            <p className="text-xs text-stone-500">
              राष्ट्रीय आयुष मिशन • AI-Assisted Clinical Triage & E-Prescription
            </p>
          </div>
        </div>

        {/* Real-time stats */}
        <div className="hidden sm:flex items-center gap-4 text-xs">
          <div className="flex items-center gap-2 bg-stone-50 px-3 py-1.5 rounded-lg border border-stone-200">
            <Users className="w-4 h-4 text-ayush-primary" />
            <span>Waiting: <strong>{totalWaiting}</strong></span>
          </div>

          <div className="flex items-center gap-2 bg-rose-50 px-3 py-1.5 rounded-lg border border-rose-200 text-rose-800">
            <ShieldAlert className="w-4 h-4 text-rose-600" />
            <span>Red Flags: <strong>{totalRedFlags}</strong></span>
          </div>

          <div className="flex items-center gap-2 bg-stone-50 px-3 py-1.5 rounded-lg border border-stone-200">
            <Clock className="w-4 h-4 text-amber-600" />
            <span>Avg Wait: <strong>{avgWaitTime}m</strong></span>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
        {/* Queue Sidebar */}
        <QueueSidebar
          queue={queue}
          selectedPatientId={selectedItem?.patient_id || selectedItem?.id}
          onSelectPatient={handleSelectPatient}
          onRefresh={fetchQueue}
          isLoading={isLoading}
        />

        {/* Case Sheet Main Workspace */}
        <main className="flex-1 flex flex-col overflow-y-auto">
          {selectedItem ? (
            <CaseSheetEditor
              patient={selectedItem.patient}
              interviewId={selectedItem.interview_id || selectedItem.id}
              caseSheetData={selectedItem.case_sheet}
              onSaveCaseSheet={handleSaveCaseSheet}
            />
          ) : (
            <div className="flex-1 flex items-center justify-center text-stone-400 text-sm">
              Select a patient from the queue to view and audit their case sheet.
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
