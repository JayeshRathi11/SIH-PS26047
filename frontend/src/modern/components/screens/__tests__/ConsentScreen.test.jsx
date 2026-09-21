import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ConsentScreen from '../ConsentScreen';

// Mock contexts and services
const mockUpdateConsent = vi.fn();
const mockPlayTts = vi.fn();

let mockKioskContext = {
  consent: { triage_consent: true, ai_consent: true, ocr_consent: true },
  updateConsent: mockUpdateConsent,
  language: 'hi',
  patient: { id: 101, name: 'Ramesh Patel' },
};

let mockAudioContext = {
  playTts: mockPlayTts,
  isPlaying: false,
};

vi.mock('../../../context/KioskSessionContext', () => ({
  useKioskSession: () => mockKioskContext,
}));

vi.mock('../../../context/AudioContext', () => ({
  useAudio: () => mockAudioContext,
}));

vi.mock('../../../services/api', () => ({
  MediKioskApi: {
    post: vi.fn().mockResolvedValue({ data: { success: true } }),
  },
}));

import { MediKioskApi } from '../../../services/api';

describe('ConsentScreen Component Exhaustive Tests', () => {
  const onAgree = vi.fn();
  const onDecline = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockKioskContext = {
      consent: { triage_consent: true, ai_consent: true, ocr_consent: true },
      updateConsent: mockUpdateConsent,
      language: 'hi',
      patient: { id: 101, name: 'Ramesh Patel' },
    };
    mockAudioContext = {
      playTts: mockPlayTts,
      isPlaying: false,
    };
  });

  it('renders DPDP Act 2023 title and all three granular consent clauses', () => {
    render(<ConsentScreen onAgree={onAgree} onDecline={onDecline} />);

    expect(screen.getByText(/DPDP Digital Consent/i)).toBeInTheDocument();
    expect(screen.getByText(/1\. आयुष क्लिनिकल ट्राइएज/i)).toBeInTheDocument();
    expect(screen.getByText(/2\. एआई वॉयस ट्रांसक्रिप्शन/i)).toBeInTheDocument();
    expect(screen.getByText(/3\. पुराने पर्चे व रिपोर्ट/i)).toBeInTheDocument();
  });

  it('toggles granular triage consent and disables Agree button when false', () => {
    render(<ConsentScreen onAgree={onAgree} onDecline={onDecline} />);

    const agreeButton = screen.getByRole('button', { name: /सहमति दें एवं आगे बढ़ें/i });
    expect(agreeButton).not.toBeDisabled();

    // Click Clause 1 (Triage) to uncheck
    const triageCard = screen.getByText(/1\. आयुष क्लिनिकल ट्राइएज/i).closest('.cursor-pointer');
    fireEvent.click(triageCard);

    // Agree button should now be disabled because triage consent is mandatory
    expect(agreeButton).toBeDisabled();

    // Click Clause 1 again to re-enable
    fireEvent.click(triageCard);
    expect(agreeButton).not.toBeDisabled();
  });

  it('toggles all clauses using Select All button', () => {
    render(<ConsentScreen onAgree={onAgree} onDecline={onDecline} />);

    const selectAllBtn = screen.getByText(/सभी चुनें \/ Select All/i);
    const agreeButton = screen.getByRole('button', { name: /सहमति दें एवं आगे बढ़ें/i });

    // Currently all are selected -> clicking Select All should unselect all
    fireEvent.click(selectAllBtn);
    expect(agreeButton).toBeDisabled();

    // Clicking Select All again should select all
    fireEvent.click(selectAllBtn);
    expect(agreeButton).not.toBeDisabled();
  });

  it('plays audio readout in current language when Read Out button is clicked', () => {
    render(<ConsentScreen onAgree={onAgree} onDecline={onDecline} />);

    const readOutBtn = screen.getByText(/सहमति सुनें \/ Read Out/i);
    fireEvent.click(readOutBtn);

    expect(mockPlayTts).toHaveBeenCalledTimes(1);
    expect(mockPlayTts).toHaveBeenCalledWith(
      expect.stringContaining('डिजिटल व्यक्तिगत डेटा संरक्षण अधिनियम 2023'),
      'hi'
    );
  });

  it('posts consent payload, updates context, and triggers onAgree on successful agreement', async () => {
    render(<ConsentScreen onAgree={onAgree} onDecline={onDecline} />);

    const agreeButton = screen.getByRole('button', { name: /सहमति दें एवं आगे बढ़ें/i });
    fireEvent.click(agreeButton);

    await waitFor(() => {
      expect(MediKioskApi.post).toHaveBeenCalledWith('/api/consents', expect.objectContaining({
        patient_id: 101,
        triage_consent: true,
        ai_consent: true,
        ocr_consent: true,
        granted: true,
      }));
      expect(mockUpdateConsent).toHaveBeenCalledTimes(1);
      expect(onAgree).toHaveBeenCalledTimes(1);
    });
  });

  it('opens decline modal when Decline button is clicked', () => {
    render(<ConsentScreen onAgree={onAgree} onDecline={onDecline} />);

    const declineBtn = screen.getByText(/अस्वीकार करें \/ Decline/i);
    fireEvent.click(declineBtn);

    expect(screen.getByText(/सहमति अस्वीकार\? \/ Decline Consent\?/i)).toBeInTheDocument();
    expect(screen.getByText(/वापस जाएं \/ Go Back/i)).toBeInTheDocument();
    expect(screen.getByText(/पुष्टि करें \/ Confirm Exit/i)).toBeInTheDocument();
  });

  it('closes decline modal when Go Back is clicked without calling onDecline', () => {
    render(<ConsentScreen onAgree={onAgree} onDecline={onDecline} />);

    fireEvent.click(screen.getByText(/अस्वीकार करें \/ Decline/i));
    fireEvent.click(screen.getByText(/वापस जाएं \/ Go Back/i));

    expect(screen.queryByText(/सहमति अस्वीकार\? \/ Decline Consent\?/i)).not.toBeInTheDocument();
    expect(onDecline).not.toHaveBeenCalled();
  });

  it('calls onDecline when Confirm Exit is clicked inside decline modal', () => {
    render(<ConsentScreen onAgree={onAgree} onDecline={onDecline} />);

    fireEvent.click(screen.getByText(/अस्वीकार करें \/ Decline/i));
    fireEvent.click(screen.getByText(/पुष्टि करें \/ Confirm Exit/i));

    expect(onDecline).toHaveBeenCalledTimes(1);
  });
});
