import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import WelcomeScreen from '../WelcomeScreen';

let mockLanguage = 'en';

vi.mock('../../../context/KioskSessionContext', () => ({
  useKioskSession: () => ({
    language: mockLanguage,
  }),
}));

describe('WelcomeScreen Component Exhaustive Tests', () => {
  const onBegin = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockLanguage = 'en';
  });

  it('renders default English welcome title, subtext, and 4 journey steps', () => {
    render(<WelcomeScreen onBegin={onBegin} />);

    expect(screen.getByText('Welcome to AIIA OPD Check-in')).toBeInTheDocument();
    expect(screen.getByText('All India Institute of Ayurveda — New Delhi')).toBeInTheDocument();

    // 4 Steps
    expect(screen.getByText('Identity Check')).toBeInTheDocument();
    expect(screen.getByText('AI Doctor Interview')).toBeInTheDocument();
    expect(screen.getByText('Records & OCR')).toBeInTheDocument();
    expect(screen.getByText('OPD Queue Token')).toBeInTheDocument();

    // Helpdesk notice
    expect(screen.getByText(/Hospital Sahayak staff available at Helpdesk 1/i)).toBeInTheDocument();
  });

  it('renders Hindi localized content when language is hi', () => {
    mockLanguage = 'hi';
    render(<WelcomeScreen onBegin={onBegin} />);

    expect(screen.getByText('AIIA ओपीडी में आपका स्वागत है')).toBeInTheDocument();
    expect(screen.getByText('अखिल भारतीय आयुर्वेद संस्थान — नई दिल्ली')).toBeInTheDocument();
    expect(screen.getByText('पहचान सत्यापन')).toBeInTheDocument();
    expect(screen.getByText('एआई डॉक्टर साक्षात्कार')).toBeInTheDocument();
  });

  it('renders Marathi localized content when language is mr', () => {
    mockLanguage = 'mr';
    render(<WelcomeScreen onBegin={onBegin} />);

    expect(screen.getByText('AIIA ओपीडी मध्ये आपले स्वागत आहे')).toBeInTheDocument();
    expect(screen.getByText('अखिल भारतीय आयुर्वेद संस्था — नवी दिल्ली')).toBeInTheDocument();
    expect(screen.getByText('ओळख पडताळणी')).toBeInTheDocument();
  });

  it('invokes onBegin callback when Begin CTA button is clicked', () => {
    render(<WelcomeScreen onBegin={onBegin} />);

    const beginBtn = screen.getByRole('button', { name: /Begin \/ प्रारंभ करें/i });
    fireEvent.click(beginBtn);

    expect(onBegin).toHaveBeenCalledTimes(1);
  });
});
