import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ManualEntryScreen from '../ManualEntryScreen';
import { MediKioskApi } from '../../../services/api';
import * as KioskContext from '../../../context/KioskSessionContext';

// Mock MediKioskApi
vi.mock('../../../services/api', () => ({
  MediKioskApi: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

describe('ManualEntryScreen Component', () => {
  let mockUpdatePatient;
  let mockOnComplete;
  let mockOnBack;

  beforeEach(() => {
    vi.clearAllMocks();
    mockUpdatePatient = vi.fn();
    mockOnComplete = vi.fn();
    mockOnBack = vi.fn();

    vi.spyOn(KioskContext, 'useKioskSession').mockReturnValue({
      language: 'hi',
      updatePatient: mockUpdatePatient,
    });
  });

  it('renders all demographic input fields and default values', () => {
    render(<ManualEntryScreen onComplete={mockOnComplete} onBack={mockOnBack} />);

    expect(screen.getByText(/रोगी विवरण प्रविष्टि/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/सीमा देवी/i)).toBeInTheDocument(); // Name input
    expect(screen.getByPlaceholderText(/e\.g\. 45/i)).toBeInTheDocument(); // Age input
    expect(screen.getByPlaceholderText(/10 अंकों का नंबर/i)).toBeInTheDocument(); // Mobile input
    expect(screen.getByDisplayValue('South Delhi')).toBeInTheDocument(); // Default district
    expect(screen.getByDisplayValue('Delhi')).toBeInTheDocument(); // Default state

    // Gender buttons
    expect(screen.getByRole('button', { name: /पुरुष/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /महिला/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /अन्य/i })).toBeInTheDocument();

    // Proceed button
    expect(screen.getByRole('button', { name: /सहमति पृष्ठ पर जाएं/i })).toBeInTheDocument();
  });

  it('allows selecting different gender options', async () => {
    render(<ManualEntryScreen onComplete={mockOnComplete} onBack={mockOnBack} />);
    const user = userEvent.setup();

    const femaleBtn = screen.getByRole('button', { name: /महिला/i });
    await user.click(femaleBtn);
    expect(femaleBtn).toHaveClass('bg-cream-warm');

    const otherBtn = screen.getByRole('button', { name: /अन्य/i });
    await user.click(otherBtn);
    expect(otherBtn).toHaveClass('bg-cream-warm');
  });

  it('activates age keypad on focus and enters numbers via keypad', async () => {
    render(<ManualEntryScreen onComplete={mockOnComplete} onBack={mockOnBack} />);
    const user = userEvent.setup();

    const ageInput = screen.getByPlaceholderText(/e\.g\. 45/i);
    fireEvent.focus(ageInput);

    // Header updates to active age keypad
    expect(screen.getByText(/आयु दर्ज करें \(Age Keypad\)/i)).toBeInTheDocument();

    // Press '4' and '2' on keypad
    await user.click(screen.getByRole('button', { name: '4' }));
    await user.click(screen.getByRole('button', { name: '2' }));

    expect(ageInput).toHaveValue('42');

    // Backspace on keypad
    const backspaceBtn = document.querySelector('button .text-manjistha-red')?.closest('button');
    await user.click(backspaceBtn);
    expect(ageInput).toHaveValue('4');

    // Clear on keypad
    await user.click(screen.getByRole('button', { name: /साफ़/i }));
    expect(ageInput).toHaveValue('');
  });

  it('activates mobile keypad on focus and enters up to 10 digits', async () => {
    render(<ManualEntryScreen onComplete={mockOnComplete} onBack={mockOnBack} />);
    const user = userEvent.setup();

    const mobileInput = screen.getByPlaceholderText(/10 अंकों का नंबर/i);
    fireEvent.focus(mobileInput);

    expect(screen.getByText(/मोबाइल नंबर दर्ज करें \(Mobile Keypad\)/i)).toBeInTheDocument();

    // Press 10 digits: 9 8 7 6 5 4 3 2 1 0
    const digits = ['9', '8', '7', '6', '5', '4', '3', '2', '1', '0'];
    for (const d of digits) {
      await user.click(screen.getByRole('button', { name: d }));
    }
    expect(mobileInput).toHaveValue('9876543210');

    // Attempting 11th digit is ignored by the max 10 boundary
    await user.click(screen.getByRole('button', { name: '9' }));
    expect(mobileInput).toHaveValue('9876543210');
  });

  it('validates mandatory fields and blocks submission when empty', async () => {
    render(<ManualEntryScreen onComplete={mockOnComplete} onBack={mockOnBack} />);
    const user = userEvent.setup();

    const proceedBtn = screen.getByRole('button', { name: /सहमति पृष्ठ पर जाएं/i });
    await user.click(proceedBtn);

    expect(screen.getByText(/कृपया पूरा नाम दर्ज करें/i)).toBeInTheDocument();
    expect(screen.getByText(/मान्य आयु दर्ज करें/i)).toBeInTheDocument();
    expect(screen.getByText(/10 अंकों का मोबाइल नंबर दर्ज करें/i)).toBeInTheDocument();
    expect(MediKioskApi.post).not.toHaveBeenCalled();
    expect(mockOnComplete).not.toHaveBeenCalled();
  });

  it('validates age boundaries (<= 0 or > 120)', async () => {
    render(<ManualEntryScreen onComplete={mockOnComplete} onBack={mockOnBack} />);
    const user = userEvent.setup();

    const nameInput = screen.getByPlaceholderText(/सीमा देवी/i);
    await user.type(nameInput, 'Rajesh Kumar');

    // Set age to 0 via keypad
    const ageInput = screen.getByPlaceholderText(/e\.g\. 45/i);
    fireEvent.focus(ageInput);
    await user.click(screen.getByRole('button', { name: '0' }));

    const proceedBtn = screen.getByRole('button', { name: /सहमति पृष्ठ पर जाएं/i });
    await user.click(proceedBtn);

    expect(screen.getByText(/मान्य आयु दर्ज करें/i)).toBeInTheDocument();
  });

  it('handles successful patient registration happy path', async () => {
    MediKioskApi.post.mockResolvedValueOnce({
      data: {
        id: 101,
        name: 'Sunita Sharma',
        phone_number: '+919876543210',
        date_of_birth: '1996-01-01',
        gender: 'Female',
        preferred_language: 'hi',
      },
    });

    render(<ManualEntryScreen onComplete={mockOnComplete} onBack={mockOnBack} />);
    const user = userEvent.setup();

    // Fill Name
    await user.type(screen.getByPlaceholderText(/सीमा देवी/i), 'Sunita Sharma');

    // Select Gender Female
    await user.click(screen.getByRole('button', { name: /महिला/i }));

    // Fill Age
    const ageInput = screen.getByPlaceholderText(/e\.g\. 45/i);
    fireEvent.focus(ageInput);
    await user.click(screen.getByRole('button', { name: '3' }));
    await user.click(screen.getByRole('button', { name: '0' }));

    // Fill Mobile
    const mobileInput = screen.getByPlaceholderText(/10 अंकों का नंबर/i);
    fireEvent.focus(mobileInput);
    for (const d of ['9', '8', '7', '6', '5', '4', '3', '2', '1', '0']) {
      await user.click(screen.getByRole('button', { name: d }));
    }

    // Submit
    await user.click(screen.getByRole('button', { name: /सहमति पृष्ठ पर जाएं/i }));

    await waitFor(() => {
      expect(MediKioskApi.post).toHaveBeenCalledWith(
        '/api/patients',
        expect.objectContaining({
          name: 'Sunita Sharma',
          phone_number: '+919876543210',
          gender: 'Female',
          preferred_language: 'hi',
        })
      );
      expect(mockUpdatePatient).toHaveBeenCalledWith(
        expect.objectContaining({
          id: 101,
          name: 'Sunita Sharma',
          age: 30,
          gender: 'Female',
          mobile: '9876543210',
        })
      );
      expect(mockOnComplete).toHaveBeenCalledTimes(1);
    });
  });

  it('handles 409 conflict gracefully by resolving existing patient via phone lookup', async () => {
    const conflictError = new Error('Conflict');
    conflictError.status = 409;
    conflictError.isConflict = true;

    MediKioskApi.post.mockRejectedValueOnce(conflictError);
    MediKioskApi.get.mockResolvedValueOnce({
      ok: true,
      data: {
        id: 77,
        name: 'Existing Patient',
        phone_number: '+919876543210',
      },
    });

    render(<ManualEntryScreen onComplete={mockOnComplete} onBack={mockOnBack} />);
    const user = userEvent.setup();

    await user.type(screen.getByPlaceholderText(/सीमा देवी/i), 'Existing Patient');
    const ageInput = screen.getByPlaceholderText(/e\.g\. 45/i);
    fireEvent.focus(ageInput);
    await user.click(screen.getByRole('button', { name: '4' }));
    await user.click(screen.getByRole('button', { name: '0' }));

    const mobileInput = screen.getByPlaceholderText(/10 अंकों का नंबर/i);
    fireEvent.focus(mobileInput);
    for (const d of ['9', '8', '7', '6', '5', '4', '3', '2', '1', '0']) {
      await user.click(screen.getByRole('button', { name: d }));
    }

    await user.click(screen.getByRole('button', { name: /सहमति पृष्ठ पर जाएं/i }));

    await waitFor(() => {
      expect(MediKioskApi.get).toHaveBeenCalledWith('/api/patients/by-phone/%2B919876543210');
      expect(mockUpdatePatient).toHaveBeenCalledWith(
        expect.objectContaining({
          id: 77,
          name: 'Existing Patient',
        })
      );
      expect(mockOnComplete).toHaveBeenCalledTimes(1);
    });
  });

  it('displays error banner without crashing when registration fails with network or 500 error', async () => {
    const serverError = new Error('Server Error');
    serverError.status = 500;
    serverError.detail = 'Database connection error';

    MediKioskApi.post.mockRejectedValueOnce(serverError);

    render(<ManualEntryScreen onComplete={mockOnComplete} onBack={mockOnBack} />);
    const user = userEvent.setup();

    await user.type(screen.getByPlaceholderText(/सीमा देवी/i), 'Amit Verma');
    const ageInput = screen.getByPlaceholderText(/e\.g\. 45/i);
    fireEvent.focus(ageInput);
    await user.click(screen.getByRole('button', { name: '2' }));
    await user.click(screen.getByRole('button', { name: '5' }));

    const mobileInput = screen.getByPlaceholderText(/10 अंकों का नंबर/i);
    fireEvent.focus(mobileInput);
    for (const d of ['9', '8', '7', '6', '5', '4', '3', '2', '1', '0']) {
      await user.click(screen.getByRole('button', { name: d }));
    }

    await user.click(screen.getByRole('button', { name: /सहमति पृष्ठ पर जाएं/i }));

    await waitFor(() => {
      expect(screen.getByText(/Database connection error/i)).toBeInTheDocument();
      expect(mockOnComplete).not.toHaveBeenCalled();
    });
  });
});
