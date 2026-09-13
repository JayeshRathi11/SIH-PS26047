const API_BASE_URL = import.meta.env.VITE_API_URL || ''

export async function registerPatient(patientData) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/patients`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(patientData),
    })

    const data = await response.json().catch(() => null)

    if (!response.ok) {
      const error = new Error()
      error.status = response.status

      if (response.status === 409) {
        error.message = data?.detail || 'This phone number is already registered.'
      } else if (response.status === 422) {
        if (Array.isArray(data?.detail)) {
          error.message = data.detail.map((err) => `${err.loc.at(-1)}: ${err.msg}`).join(', ')
          error.validationErrors = data.detail
        } else {
          error.message = data?.detail || 'Please check your input values.'
        }
      } else if (response.status >= 500) {
        error.message = 'A server error occurred. Please try again later.'
      } else {
        error.message = data?.detail || `Registration failed with status ${response.status}.`
      }

      throw error
    }

    return data
  } catch (err) {
    if (err.status) {
      throw err
    }
    const networkError = new Error('Unable to connect to the server. Please check your connection.')
    networkError.status = 0
    throw networkError
  }
}

export async function getPatientById(patientId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/patients/${patientId}`, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
      },
    })

    const data = await response.json().catch(() => null)

    if (!response.ok) {
      const error = new Error(data?.detail || `Failed to fetch patient (status ${response.status}).`)
      error.status = response.status
      throw error
    }

    return data
  } catch (err) {
    if (err.status) {
      throw err
    }
    const networkError = new Error('Unable to connect to the server.')
    networkError.status = 0
    throw networkError
  }
}
