import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import CaseSheetEditor from '../CaseSheetEditor';

// Mock HerbNormalizerSearch to simulate adding herbs
vi.mock('../HerbNormalizerSearch', () => ({
  default: ({ onSelectHerb }) => (
    <div data-testid="mock-herb-search">
      <button
        type="button"
        onClick={() =>
          onSelectHerb({
            sanskrit: 'त्रिफला चूर्ण (Triphala Churna)',
            dosage: '5 ग्राम',
            anupana: 'कोष्ण जल',
            kala: 'शयन पूर्व',
          })
        }
      >
        Add Triphala Mock
      </button>
    </div>
  ),
}));

describe('CaseSheetEditor Component Exhaustive Tests', () => {
  const mockPatient = {
    id: 1,
    name: 'Ramesh Patel',
    chief_complaint: 'तीव्र कास (Severe Cough), श्वास कष्टता (Dyspnea)',
  };

  it('renders initial sections with patient complaints and default prescriptions', () => {
    render(<CaseSheetEditor patient={mockPatient} onSave={vi.fn()} />);

    // Section headings
    expect(screen.getByText(/प्रधान लक्षण • Chief Complaints/i)).toBeInTheDocument();
    expect(screen.getByText(/वर्तमान व्याधि इतिहास • History of Present Illness/i)).toBeInTheDocument();
    expect(screen.getByText(/अष्टविध परीक्षा निष्कर्ष • Ashtavidha Pariksha Findings/i)).toBeInTheDocument();
    expect(screen.getByText(/आयुर्वेदिक निदान • Ayurvedic Diagnosis/i)).toBeInTheDocument();
    expect(screen.getByText(/चिकित्सा सूत्र एवं औषधि पर्ची • Treatment & Prescriptions/i)).toBeInTheDocument();

    // Prescriptions count and items
    expect(screen.getByText(/पर्चे में शामिल औषधियां \(2\):/i)).toBeInTheDocument();
    expect(screen.getByText(/सुदर्शन वटी \(Sudarshan Vati\)/i)).toBeInTheDocument();
    expect(screen.getByText(/अश्वगंधा चूर्ण \(Ashwagandha Churna\)/i)).toBeInTheDocument();
  });

  it('toggles collapsible sections open and closed', () => {
    render(<CaseSheetEditor patient={mockPatient} onSave={vi.fn()} />);

    // Ashtavidha Pariksha starts closed
    expect(screen.queryByText(/नाड़ी:/i)).not.toBeInTheDocument();

    // Click Ashtavidha Pariksha header to expand
    const parikshaHeader = screen.getByText(/अष्टविध परीक्षा निष्कर्ष • Ashtavidha Pariksha Findings/i);
    fireEvent.click(parikshaHeader);

    // Now Ashtavidha Pariksha findings should be visible
    expect(screen.getByText(/नाड़ी:/i)).toBeInTheDocument();
    expect(screen.getByText(/जिह्वा:/i)).toBeInTheDocument();

    // Click again to collapse
    fireEvent.click(parikshaHeader);
    expect(screen.queryByText(/नाड़ी:/i)).not.toBeInTheDocument();
  });

  it('allows editing chief complaints and diagnosis fields', () => {
    render(<CaseSheetEditor patient={mockPatient} onSave={vi.fn()} />);

    const complaintTextarea = screen.getByDisplayValue(mockPatient.chief_complaint);
    fireEvent.change(complaintTextarea, { target: { value: 'Updated chief complaint text' } });
    expect(screen.getByDisplayValue('Updated chief complaint text')).toBeInTheDocument();

    const diagnosisInput = screen.getByDisplayValue(/वात-कफज ज्वर/i);
    fireEvent.change(diagnosisInput, { target: { value: 'अम्लपित्त (Hyperacidity)' } });
    expect(screen.getByDisplayValue('अम्लपित्त (Hyperacidity)')).toBeInTheDocument();
  });

  it('adds a new herb prescription and allows removing existing prescriptions', () => {
    render(<CaseSheetEditor patient={mockPatient} onSave={vi.fn()} />);

    // Add new herb via mock search
    const addHerbBtn = screen.getByRole('button', { name: /Add Triphala Mock/i });
    fireEvent.click(addHerbBtn);

    // Prescriptions count should now be 3
    expect(screen.getByText(/पर्चे में शामिल औषधियां \(3\):/i)).toBeInTheDocument();
    expect(screen.getByText(/त्रिफला चूर्ण \(Triphala Churna\)/i)).toBeInTheDocument();

    // Remove first prescription (Sudarshan Vati)
    const removeSudarshanBtn = screen.getByRole('button', {
      name: /Remove prescription सुदर्शन वटी/i,
    });
    fireEvent.click(removeSudarshanBtn);

    // Prescriptions count should now be 2, and Sudarshan Vati removed
    expect(screen.getByText(/पर्चे में शामिल औषधियां \(2\):/i)).toBeInTheDocument();
    expect(screen.queryByText(/सुदर्शन वटी \(Sudarshan Vati\)/i)).not.toBeInTheDocument();
  });
});
