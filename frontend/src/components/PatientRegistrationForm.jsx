import { useState } from 'react'
import { registerPatient } from '../api/patientApi'

const LANGUAGE_OPTIONS = [
  { value: 'en', label: 'English' },
  { value: 'hi', label: 'Hindi (हिंदी)' },
  { value: 'mr', label: 'Marathi (मराठी)' },
  { value: 'ta', label: 'Tamil (தமிழ்)' },
  { value: 'te', label: 'Telugu (తెలుగు)' },
  { value: 'bn', label: 'Bengali (বাংলা)' },
  { value: 'gu', label: 'Gujarati (ગુજરાતી)' },
]

export default function PatientRegistrationForm({ onSuccess }) {
  const [formData, setFormData] = useState({
    name: '',
    phone_number: '',
    date_of_birth: '',
    gender: 'Male',
    preferred_language: 'en',
  })

  const [errors, setErrors] = useState({})
  const [apiError, setApiError] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleChange = (e) => {
    const { name, value } = e.target
    setFormData((prev) => ({ ...prev, [name]: value }))
    if (errors[name]) {
      setErrors((prev) => ({ ...prev, [name]: null }))
    }
    if (apiError) {
      setApiError(null)
    }
  }

  const validateForm = () => {
    const newErrors = {}

    if (!formData.name.trim()) {
      newErrors.name = 'Full name is required'
    }

    const trimmedPhone = formData.phone_number.trim()
    if (!trimmedPhone) {
      newErrors.phone_number = 'Phone number is required'
    } else if (trimmedPhone.length < 10 || trimmedPhone.length > 20) {
      newErrors.phone_number = 'Phone number must be between 10 and 20 characters'
    }

    if (!formData.date_of_birth) {
      newErrors.date_of_birth = 'Date of birth is required'
    } else {
      const selectedDate = new Date(formData.date_of_birth)
      const today = new Date()
      if (selectedDate > today) {
        newErrors.date_of_birth = 'Date of birth cannot be in the future'
      }
    }

    if (!formData.gender) {
      newErrors.gender = 'Gender selection is required'
    }

    if (!formData.preferred_language) {
      newErrors.preferred_language = 'Preferred language is required'
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSubmit = async (e) => {
    e.preventDefault()

    if (!validateForm()) {
      return
    }

    setIsSubmitting(true)
    setApiError(null)

    try {
      const payload = {
        name: formData.name.trim(),
        phone_number: formData.phone_number.trim(),
        date_of_birth: formData.date_of_birth,
        gender: formData.gender,
        preferred_language: formData.preferred_language,
      }

      const result = await registerPatient(payload)
      if (onSuccess) {
        onSuccess(result)
      }
    } catch (err) {
      setApiError(err.message || 'An unexpected error occurred during registration.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const maxDate = new Date().toISOString().split('T')[0]

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-6">
      {apiError && (
        <div
          role="alert"
          className="rounded-lg border border-red-500/50 bg-red-950/40 p-4 text-sm text-red-300"
        >
          <div className="font-semibold text-red-200">Registration Failed</div>
          <p className="mt-1">{apiError}</p>
        </div>
      )}

      {/* Full Name */}
      <div>
        <label htmlFor="name" className="block text-sm font-medium text-slate-200">
          Full Name <span className="text-red-400">*</span>
        </label>
        <input
          id="name"
          name="name"
          type="text"
          autoComplete="name"
          value={formData.name}
          onChange={handleChange}
          disabled={isSubmitting}
          placeholder="e.g. Aarav Sharma"
          className={`mt-1 block w-full rounded-md border bg-slate-900 px-3.5 py-2.5 text-sm text-white placeholder-slate-500 shadow-sm transition focus:outline-none focus:ring-2 focus:ring-emerald-500 ${
            errors.name ? 'border-red-500 focus:border-red-500' : 'border-slate-700'
          }`}
        />
        {errors.name && <p className="mt-1 text-xs text-red-400">{errors.name}</p>}
      </div>

      {/* Phone Number */}
      <div>
        <label htmlFor="phone_number" className="block text-sm font-medium text-slate-200">
          Phone Number <span className="text-red-400">*</span>
        </label>
        <input
          id="phone_number"
          name="phone_number"
          type="tel"
          autoComplete="tel"
          value={formData.phone_number}
          onChange={handleChange}
          disabled={isSubmitting}
          placeholder="e.g. +919876543210"
          className={`mt-1 block w-full rounded-md border bg-slate-900 px-3.5 py-2.5 text-sm text-white placeholder-slate-500 shadow-sm transition focus:outline-none focus:ring-2 focus:ring-emerald-500 ${
            errors.phone_number ? 'border-red-500 focus:border-red-500' : 'border-slate-700'
          }`}
        />
        {errors.phone_number && (
          <p className="mt-1 text-xs text-red-400">{errors.phone_number}</p>
        )}
      </div>

      {/* Date of Birth */}
      <div>
        <label htmlFor="date_of_birth" className="block text-sm font-medium text-slate-200">
          Date of Birth <span className="text-red-400">*</span>
        </label>
        <input
          id="date_of_birth"
          name="date_of_birth"
          type="date"
          max={maxDate}
          value={formData.date_of_birth}
          onChange={handleChange}
          disabled={isSubmitting}
          className={`mt-1 block w-full rounded-md border bg-slate-900 px-3.5 py-2.5 text-sm text-white placeholder-slate-500 shadow-sm transition focus:outline-none focus:ring-2 focus:ring-emerald-500 ${
            errors.date_of_birth ? 'border-red-500 focus:border-red-500' : 'border-slate-700'
          }`}
        />
        {errors.date_of_birth && (
          <p className="mt-1 text-xs text-red-400">{errors.date_of_birth}</p>
        )}
      </div>

      {/* Gender */}
      <div>
        <label className="block text-sm font-medium text-slate-200">
          Gender <span className="text-red-400">*</span>
        </label>
        <div className="mt-2 grid grid-cols-3 gap-3">
          {['Male', 'Female', 'Other'].map((option) => (
            <label
              key={option}
              className={`flex cursor-pointer items-center justify-center rounded-md border px-3 py-2.5 text-sm font-medium transition ${
                formData.gender === option
                  ? 'border-emerald-500 bg-emerald-500/10 text-emerald-400'
                  : 'border-slate-700 bg-slate-900 text-slate-300 hover:border-slate-600'
              }`}
            >
              <input
                type="radio"
                name="gender"
                value={option}
                checked={formData.gender === option}
                onChange={handleChange}
                disabled={isSubmitting}
                className="sr-only"
              />
              {option}
            </label>
          ))}
        </div>
        {errors.gender && <p className="mt-1 text-xs text-red-400">{errors.gender}</p>}
      </div>

      {/* Preferred Language */}
      <div>
        <label htmlFor="preferred_language" className="block text-sm font-medium text-slate-200">
          Preferred Language <span className="text-red-400">*</span>
        </label>
        <select
          id="preferred_language"
          name="preferred_language"
          value={formData.preferred_language}
          onChange={handleChange}
          disabled={isSubmitting}
          className={`mt-1 block w-full rounded-md border bg-slate-900 px-3.5 py-2.5 text-sm text-white shadow-sm transition focus:outline-none focus:ring-2 focus:ring-emerald-500 ${
            errors.preferred_language
              ? 'border-red-500 focus:border-red-500'
              : 'border-slate-700'
          }`}
        >
          {LANGUAGE_OPTIONS.map((lang) => (
            <option key={lang.value} value={lang.value}>
              {lang.label}
            </option>
          ))}
        </select>
        {errors.preferred_language && (
          <p className="mt-1 text-xs text-red-400">{errors.preferred_language}</p>
        )}
      </div>

      {/* Submit Button */}
      <div className="pt-2">
        <button
          type="submit"
          disabled={isSubmitting}
          className="flex w-full items-center justify-center rounded-md bg-emerald-600 px-4 py-3 text-sm font-semibold text-white shadow-md transition hover:bg-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:ring-offset-2 focus:ring-offset-slate-950 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isSubmitting ? (
            <span className="inline-flex items-center gap-2">
              <svg
                className="h-4 w-4 animate-spin text-white"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                ></circle>
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                ></path>
              </svg>
              Registering Patient...
            </span>
          ) : (
            'Complete Registration'
          )}
        </button>
      </div>
    </form>
  )
}
