import React from 'react';
import { AlertTriangle, RotateCcw } from 'lucide-react';
import ClayCard from '../atoms/ClayCard';
import ClayButton from '../atoms/ClayButton';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('MediKiosk ErrorBoundary caught error:', error, errorInfo);
  }

  handleReset = () => {
    try {
      sessionStorage.clear();
      window.location.reload();
    } catch {
      window.location.href = '/';
    }
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-bg text-teak-grey flex items-center justify-center p-6">
          <ClayCard elevated className="max-w-lg w-full p-8 text-center border-2 border-manjistha-red flex flex-col items-center gap-4">
            <div className="w-16 h-16 rounded-full bg-manjistha-red/15 text-manjistha-red flex items-center justify-center">
              <AlertTriangle className="w-8 h-8" />
            </div>
            <h2 className="font-display font-bold text-heading text-manjistha-red">
              कियोस्क सिस्टम त्रुटि • System Error
            </h2>
            <p className="text-caption text-teak-muted">
              इंटरफ़ेस रेंडरिंग में एक अनपेक्षित समस्या आई है। आपका डेटा सुरक्षित है।
            </p>
            <ClayButton
              variant="primary-gold"
              size="md"
              onClick={this.handleReset}
              className="mt-2"
            >
              <span className="flex items-center gap-2">
                <RotateCcw className="w-4 h-4" />
                <span>कियोस्क पुनः प्रारंभ करें / Restart Kiosk</span>
              </span>
            </ClayButton>
          </ClayCard>
        </div>
      );
    }

    return this.props.children;
  }
}
