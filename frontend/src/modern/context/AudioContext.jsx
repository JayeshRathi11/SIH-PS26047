import React, { createContext, useContext, useState, useRef, useEffect } from 'react';
import { MediKioskApi } from '../services/api';

const AudioContext = createContext(null);

export function AudioProvider({ children }) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [audioEnabled, setAudioEnabled] = useState(true);
  const audioRef = useRef(null);

  const stopAudio = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    setIsPlaying(false);
  };

  const playTts = async (text, languageCode = 'hi') => {
    if (!audioEnabled || !text || typeof text !== 'string') return;
    stopAudio();

    try {
      setIsPlaying(true);
      const res = await MediKioskApi.tts(text, languageCode);
      if (res && res.data instanceof Blob) {
        const audioUrl = URL.createObjectURL(res.data);
        const audio = new Audio(audioUrl);
        audioRef.current = audio;

        audio.onended = () => {
          setIsPlaying(false);
          URL.revokeObjectURL(audioUrl);
          audioRef.current = null;
        };

        audio.onerror = () => {
          setIsPlaying(false);
          URL.revokeObjectURL(audioUrl);
          audioRef.current = null;
          fallbackSpeech(text, languageCode);
        };

        await audio.play();
        return;
      }
    } catch {
      // Backend TTS failed or offline -> fallback to browser speech synthesis
    }

    fallbackSpeech(text, languageCode);
  };

  const fallbackSpeech = (text, languageCode) => {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      try {
        const cleanText = text.replace(/<[^>]*>?/gm, '');
        const utterance = new SpeechSynthesisUtterance(cleanText);
        utterance.lang = languageCode === 'hi' ? 'hi-IN' : languageCode === 'mr' ? 'mr-IN' : 'en-IN';
        utterance.rate = 0.95;

        utterance.onend = () => setIsPlaying(false);
        utterance.onerror = () => setIsPlaying(false);

        setIsPlaying(true);
        window.speechSynthesis.speak(utterance);
      } catch {
        setIsPlaying(false);
      }
    } else {
      setIsPlaying(false);
    }
  };

  useEffect(() => {
    return () => stopAudio();
  }, []);

  return (
    <AudioContext.Provider
      value={{
        isPlaying,
        audioEnabled,
        setAudioEnabled,
        playTts,
        stopAudio
      }}
    >
      {children}
    </AudioContext.Provider>
  );
}

export function useAudio() {
  const context = useContext(AudioContext);
  if (!context) {
    throw new Error('useAudio must be used within an AudioProvider');
  }
  return context;
}

export default AudioContext;
