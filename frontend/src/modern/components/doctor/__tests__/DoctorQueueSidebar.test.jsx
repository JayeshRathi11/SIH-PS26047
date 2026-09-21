import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import DoctorQueueSidebar from '../DoctorQueueSidebar';

const mockQueue = [
  {
    id: 1,
    patient_name: 'Aarav Sharma',
    token_number: 'OPD-101',
    age: 45,
    gender: 'M',
    chief_complaint: 'Severe headache and nausea',
    is_red_flag: false,
    priority_score: 50,
  },
  {
    id: 2,
    patient_name: 'Devaki Patel',
    token_number: 'OPD-102',
    age: 72,
    gender: 'F',
    chief_complaint: 'Knee pain and stiffness',
    is_red_flag: false,
    priority_score: 80,
  },
  {
    id: 3,
    patient_name: 'Rajesh Kumar',
    token_number: 'OPD-103',
    age: 58,
    gender: 'M',
    chief_complaint: 'Chest pain with breathlessness',
    is_red_flag: true,
    priority_score: 100,
  },
];

describe('DoctorQueueSidebar Component Exhaustive Tests', () => {
  it('renders all patients sorted by priority score descending by default', () => {
    const onSelect = vi.fn();
    render(<DoctorQueueSidebar queue={mockQueue} onSelectPatient={onSelect} />);

    expect(screen.getByText(/3 प्रतीक्षा में/i)).toBeInTheDocument();
    expect(screen.getByText('Rajesh Kumar')).toBeInTheDocument();
    expect(screen.getByText('Devaki Patel')).toBeInTheDocument();
    expect(screen.getByText('Aarav Sharma')).toBeInTheDocument();

    // Verify ordering: Rajesh Kumar (priority 100) should appear before Aarav Sharma (priority 50)
    const patientCards = screen.getAllByText(/OPD-10[1-3]/);
    expect(patientCards[0]).toHaveTextContent('OPD-103'); // Rajesh
    expect(patientCards[1]).toHaveTextContent('OPD-102'); // Devaki
    expect(patientCards[2]).toHaveTextContent('OPD-101'); // Aarav
  });

  it('filters queue by RED_FLAG when Red Flag pill is clicked', () => {
    const onSelect = vi.fn();
    render(<DoctorQueueSidebar queue={mockQueue} onSelectPatient={onSelect} />);

    const redFlagBtn = screen.getByRole('button', { name: /🚨 Red Flag/i });
    fireEvent.click(redFlagBtn);

    expect(screen.getByText(/1 प्रतीक्षा में/i)).toBeInTheDocument();
    expect(screen.getByText('Rajesh Kumar')).toBeInTheDocument();
    expect(screen.queryByText('Aarav Sharma')).not.toBeInTheDocument();
    expect(screen.queryByText('Devaki Patel')).not.toBeInTheDocument();
  });

  it('filters queue by SENIOR (65+) when Senior pill is clicked', () => {
    const onSelect = vi.fn();
    render(<DoctorQueueSidebar queue={mockQueue} onSelectPatient={onSelect} />);

    const seniorBtn = screen.getByRole('button', { name: /वरिष्ठ \(65\+\)/i });
    fireEvent.click(seniorBtn);

    expect(screen.getByText(/1 प्रतीक्षा में/i)).toBeInTheDocument();
    expect(screen.getByText('Devaki Patel')).toBeInTheDocument();
    expect(screen.queryByText('Aarav Sharma')).not.toBeInTheDocument();
    expect(screen.queryByText('Rajesh Kumar')).not.toBeInTheDocument();
  });

  it('filters queue by search query across name, token, and complaint', () => {
    const onSelect = vi.fn();
    render(<DoctorQueueSidebar queue={mockQueue} onSelectPatient={onSelect} />);

    const searchInput = screen.getByPlaceholderText(/नाम, टोकन या लक्षण खोजें\.\.\./i);

    // Search by complaint
    fireEvent.change(searchInput, { target: { value: 'breathlessness' } });
    expect(screen.getByText('Rajesh Kumar')).toBeInTheDocument();
    expect(screen.queryByText('Aarav Sharma')).not.toBeInTheDocument();

    // Search by token
    fireEvent.change(searchInput, { target: { value: 'OPD-101' } });
    expect(screen.getByText('Aarav Sharma')).toBeInTheDocument();
    expect(screen.queryByText('Rajesh Kumar')).not.toBeInTheDocument();
  });

  it('invokes onSelectPatient when a patient card is clicked', () => {
    const onSelect = vi.fn();
    render(<DoctorQueueSidebar queue={mockQueue} onSelectPatient={onSelect} selectedPatientId={2} />);

    const aaravCard = screen.getByText('Aarav Sharma').closest('.cursor-pointer');
    fireEvent.click(aaravCard);

    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith(mockQueue[0]);
  });

  it('displays empty state message when filtered results are empty', () => {
    const onSelect = vi.fn();
    render(<DoctorQueueSidebar queue={[]} onSelectPatient={onSelect} />);

    expect(screen.getByText(/कोई रोगी कतार में नहीं है/i)).toBeInTheDocument();
  });
});
