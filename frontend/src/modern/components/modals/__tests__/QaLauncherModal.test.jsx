import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import QaLauncherModal from '../QaLauncherModal';

const mockSetCurrentScreen = vi.fn();
const mockSetCurrentStep = vi.fn();
const mockSetAppMode = vi.fn();
const mockUpdatePatient = vi.fn();
const mockUpdateInterview = vi.fn();
const mockAddDocument = vi.fn();
const mockResetSession = vi.fn();

vi.mock('../../../context/KioskSessionContext', () => ({
  useKioskSession: () => ({
    setCurrentScreen: mockSetCurrentScreen,
    setCurrentStep: mockSetCurrentStep,
    setAppMode: mockSetAppMode,
    updatePatient: mockUpdatePatient,
    updateInterview: mockUpdateInterview,
    addDocument: mockAddDocument,
    resetSession: mockResetSession,
  }),
}));

describe('QaLauncherModal Component Exhaustive Tests', () => {
  const onClose = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders nothing when isOpen is false', () => {
    const { container } = render(<QaLauncherModal isOpen={false} onClose={onClose} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders title, screen buttons, scenario buttons, and close buttons when isOpen is true', () => {
    render(<QaLauncherModal isOpen={true} onClose={onClose} />);

    expect(screen.getByText('Developer / QA Screen Launcher Matrix')).toBeInTheDocument();
    expect(screen.getByText(/0\. Welcome Portal/i)).toBeInTheDocument();
    expect(screen.getByText(/5\. Doctor Workstation/i)).toBeInTheDocument();
    expect(screen.getByText(/6\. Analytics Dashboard/i)).toBeInTheDocument();
    expect(screen.getByText(/1\. Standard Adult/i)).toBeInTheDocument();
    expect(screen.getByText(/2\. Red Flag Emergency/i)).toBeInTheDocument();
    expect(screen.getByText(/3\. Loaded Prescription OCR/i)).toBeInTheDocument();
  });

  it('jumps to selected screen and closes modal on screen click', () => {
    render(<QaLauncherModal isOpen={true} onClose={onClose} />);

    const doctorScreenBtn = screen.getByText(/5\. Doctor Workstation/i).closest('button');
    fireEvent.click(doctorScreenBtn);

    expect(mockSetAppMode).toHaveBeenCalledWith('DOCTOR');
    expect(mockSetCurrentStep).toHaveBeenCalledWith(5);
    expect(mockSetCurrentScreen).toHaveBeenCalledWith('DOCTOR');
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('injects standard adult preset data and navigates to INTERVIEW_STANDARD', () => {
    render(<QaLauncherModal isOpen={true} onClose={onClose} />);

    const standardPresetBtn = screen.getByText(/1\. Standard Adult/i).closest('button');
    fireEvent.click(standardPresetBtn);

    expect(mockUpdatePatient).toHaveBeenCalledWith(expect.objectContaining({
      name: 'रमेश कुमार / Ramesh Kumar',
      age: 48,
      mobile: '9876543210',
    }));
    expect(mockUpdateInterview).toHaveBeenCalledWith(expect.objectContaining({
      is_red_flag: false,
    }));
    expect(mockSetCurrentScreen).toHaveBeenCalledWith('INTERVIEW_STANDARD');
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('injects red flag emergency preset data and navigates to RED_FLAG', () => {
    render(<QaLauncherModal isOpen={true} onClose={onClose} />);

    const redFlagPresetBtn = screen.getByText(/2\. Red Flag Emergency/i).closest('button');
    fireEvent.click(redFlagPresetBtn);

    expect(mockUpdatePatient).toHaveBeenCalledWith(expect.objectContaining({
      name: 'सुमन लता / Suman Lata',
      age: 68,
    }));
    expect(mockUpdateInterview).toHaveBeenCalledWith(expect.objectContaining({
      is_red_flag: true,
      red_flag_reason: expect.stringContaining('Severe Chest Pain'),
    }));
    expect(mockSetCurrentScreen).toHaveBeenCalledWith('RED_FLAG');
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('injects document OCR preset and navigates to DOCS screen', () => {
    render(<QaLauncherModal isOpen={true} onClose={onClose} />);

    const docsPresetBtn = screen.getByText(/3\. Loaded Prescription OCR/i).closest('button');
    fireEvent.click(docsPresetBtn);

    expect(mockAddDocument).toHaveBeenCalledWith(expect.objectContaining({
      fileName: 'Prescription_AIIA_2026.jpg',
      docType: 'Prescription',
      confidence: '96%',
    }));
    expect(mockSetCurrentScreen).toHaveBeenCalledWith('DOCS');
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('resets all session state and returns to welcome screen when Reset button is clicked', () => {
    render(<QaLauncherModal isOpen={true} onClose={onClose} />);

    const resetBtn = screen.getByText(/सत्र रीसेट करें \/ Reset All State/i);
    fireEvent.click(resetBtn);

    expect(mockResetSession).toHaveBeenCalledTimes(1);
    expect(mockSetAppMode).toHaveBeenCalledWith('KIOSK');
    expect(mockSetCurrentStep).toHaveBeenCalledWith(1);
    expect(mockSetCurrentScreen).toHaveBeenCalledWith('WELCOME');
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('calls onClose when close button is clicked', () => {
    render(<QaLauncherModal isOpen={true} onClose={onClose} />);

    const closeBtn = screen.getByRole('button', { name: /बंद करें \/ Close/i });
    fireEvent.click(closeBtn);

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
