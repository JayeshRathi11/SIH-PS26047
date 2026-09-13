import { useState } from 'react'
import PatientRegistrationForm from '../components/PatientRegistrationForm'

export default function PatientRegistrationPage() {
  const [registeredPatient, setRegisteredPatient] = useState(null)

  const handleSuccess = (patientData) => {
    setRegisteredPatient(patientData)
  }

  const handleReset = () => {
    setRegisteredPatient(null)
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <div className="text-center">
          <span className="inline-block rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-emerald-400 border border-emerald-500/20">
            MediKiosk Identity
          </span>
          <h1 className="mt-3 text-3xl font-extrabold tracking-tight text-white">
            Patient Registration
          </h1>
          <p className="mt-2 text-sm text-slate-400">
            Enter patient demographic details to initiate the kiosk session.
          </p>
        </div>

        <div className="mt-8 rounded-xl border border-slate-800 bg-slate-900/80 p-6 sm:p-8 shadow-2xl backdrop-blur-sm">
          {!registeredPatient ? (
            <PatientRegistrationForm onSuccess={handleSuccess} />
          ) : (
            <div className="space-y-6" role="region" aria-label="Registration Summary">
              <div className="flex items-center gap-3 rounded-lg border border-emerald-500/30 bg-emerald-950/40 p-4 text-emerald-300">
                <svg
                  className="h-6 w-6 text-emerald-400 flex-shrink-0"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                <div>
                  <h2 className="text-base font-semibold text-emerald-200">
                    Registration Completed
                  </h2>
                  <p className="text-xs text-emerald-400/90">
                    Patient successfully registered in the system.
                  </p>
                </div>
              </div>

              {/* Patient Card Details */}
              <div className="divide-y divide-slate-800 rounded-lg border border-slate-800 bg-slate-950/60 p-4 text-sm">
                <div className="flex justify-between py-2">
                  <span className="text-slate-400">Patient ID</span>
                  <span className="font-mono font-bold text-emerald-400">
                    #{registeredPatient.id}
                  </span>
                </div>
                <div className="flex justify-between py-2">
                  <span className="text-slate-400">Full Name</span>
                  <span className="font-medium text-white">{registeredPatient.name}</span>
                </div>
                <div className="flex justify-between py-2">
                  <span className="text-slate-400">Phone Number</span>
                  <span className="font-mono text-white">{registeredPatient.phone_number}</span>
                </div>
                <div className="flex justify-between py-2">
                  <span className="text-slate-400">Date of Birth</span>
                  <span className="text-white">{registeredPatient.date_of_birth}</span>
                </div>
                <div className="flex justify-between py-2">
                  <span className="text-slate-400">Gender</span>
                  <span className="text-white">{registeredPatient.gender}</span>
                </div>
                <div className="flex justify-between py-2">
                  <span className="text-slate-400">Preferred Language</span>
                  <span className="uppercase text-white">
                    {registeredPatient.preferred_language}
                  </span>
                </div>
                <div className="flex justify-between py-2">
                  <span className="text-slate-400">Registered At</span>
                  <span className="text-xs text-slate-400">
                    {new Date(registeredPatient.created_at).toLocaleString()}
                  </span>
                </div>
              </div>

              <div className="pt-2">
                <button
                  type="button"
                  onClick={handleReset}
                  className="w-full rounded-md border border-slate-700 bg-slate-800 px-4 py-2.5 text-sm font-semibold text-slate-200 shadow transition hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-400"
                >
                  Register Another Patient
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
