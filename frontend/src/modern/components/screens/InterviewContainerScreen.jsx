import React, { useState } from 'react';
import StandardInterviewScreen from './StandardInterviewScreen';
import AyushParikshaScreen from './AyushParikshaScreen';
import RedFlagAlertScreen from './RedFlagAlertScreen';
import { useKioskSession } from '../../context/KioskSessionContext';

export default function InterviewContainerScreen({ onComplete }) {
  const { interview, updateInterview } = useKioskSession();
  const [subTab, setSubTab] = useState(interview.is_red_flag ? 'RED_FLAG' : 'STANDARD'); // 'STANDARD' | 'AYUSH' | 'RED_FLAG'

  const handleTriggerRedFlag = (reason) => {
    updateInterview({
      is_red_flag: true,
      red_flag_reason: reason
    });
    setSubTab('RED_FLAG');
  };

  const handleDismissRedFlag = () => {
    updateInterview({
      is_red_flag: false,
      red_flag_reason: null
    });
    setSubTab('STANDARD');
  };

  if (subTab === 'RED_FLAG') {
    return <RedFlagAlertScreen onDismiss={handleDismissRedFlag} />;
  }

  if (subTab === 'AYUSH') {
    return (
      <div className="flex-1 flex flex-col">
        <AyushParikshaScreen onProceedDocs={onComplete} />
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col">
      <StandardInterviewScreen
        onProceedAyush={() => setSubTab('AYUSH')}
        onTriggerRedFlag={handleTriggerRedFlag}
      />
    </div>
  );
}
