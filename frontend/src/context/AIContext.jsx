import React, { createContext, useContext, useMemo, useState } from 'react';

const AIContext = createContext(null);

export function AIProvider({ children }) {
  const [aiEnabled, setAiEnabled] = useState(() => {
    const saved = localStorage.getItem('aiEnabled');
    return saved ? saved === 'true' : false;
  });

  const toggleAI = () => {
    setAiEnabled((prev) => {
      const next = !prev;
      localStorage.setItem('aiEnabled', String(next));
      return next;
    });
  };

  const setAIEnabled = (value) => {
    setAiEnabled(Boolean(value));
    localStorage.setItem('aiEnabled', String(Boolean(value)));
  };

  const value = useMemo(() => ({ aiEnabled, toggleAI, setAIEnabled }), [aiEnabled]);
  return <AIContext.Provider value={value}>{children}</AIContext.Provider>;
}

export function useAI() {
  const ctx = useContext(AIContext);
  if (!ctx) throw new Error('useAI must be used within AIProvider');
  return ctx;
}
