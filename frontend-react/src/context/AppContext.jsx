/**
 * AppContext — lightweight context for non-auth app-wide state.
 *
 * Auth (login/logout/token) is handled exclusively by AuthContext.
 * This context only holds userId (derived from the logged-in user)
 * and language preference.
 */
import React, { createContext, useContext, useState, useEffect } from 'react';
import { useAuth } from './AuthContext';

const AppContext = createContext();

export const AppProvider = ({ children }) => {
  const { user } = useAuth();

  // Basic userId logic (synced with AuthContext)
  const userId = user?.username ?? 'guest';

  // State-driven language preference (persists in localStorage)
  const [language, setLanguage] = useState(() => {
    return localStorage.getItem('mirai_language') || 'en';
  });

  // Sync state changes to localStorage
  useEffect(() => {
    localStorage.setItem('mirai_language', language);
  }, [language]);

  return (
    <AppContext.Provider value={{ userId, language, setLanguage }}>
      {children}
    </AppContext.Provider>
  );
};

export const useAppContext = () => useContext(AppContext);
