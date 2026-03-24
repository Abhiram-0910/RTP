import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { AnimatePresence } from 'framer-motion';
import { AuthProvider, useAuth } from './context/AuthContext';
import { AppProvider } from './context/AppContext';
import Layout from './components/Layout';
import CinematicIntro from './components/CinematicIntro';
import Home from './pages/Home';
import Watchlist from './pages/Watchlist';
import Login from './pages/Login';

/** Redirect unauthenticated users to /login */
const ProtectedRoute = ({ children }) => {
  const { user, authReady } = useAuth();
  if (!authReady) return null;
  return user ? children : <Navigate to="/login" replace />;
};

/** Redirect already-logged-in users away from /login */
const PublicRoute = ({ children }) => {
  const { user, authReady } = useAuth();
  if (!authReady) return null;
  return user ? <Navigate to="/" replace /> : children;
};

function App() {
  const [showIntro, setShowIntro] = useState(
    () => !localStorage.getItem('mirai_intro_seen')
  );

  return (
    <AuthProvider>
      <AppProvider>
        <BrowserRouter>
          <Toaster
            position="top-right"
            toastOptions={{
              style: {
                background: 'rgba(15, 20, 40, 0.9)',
                backdropFilter: 'blur(10px)',
                color: '#f8fafc',
                border: '1px solid rgba(245,158,11,0.2)',
                borderRadius: '12px',
                fontFamily: "'Space Grotesk', system-ui, sans-serif",
              },
              success: { iconTheme: { primary: '#f59e0b', secondary: '#0a0e1a' } },
              error:   { iconTheme: { primary: '#dc2626', secondary: '#0a0e1a' } },
            }}
          />

          {/* Cinematic intro — plays once on first visit */}
          <AnimatePresence>
            {showIntro && (
              <CinematicIntro onComplete={() => setShowIntro(false)} />
            )}
          </AnimatePresence>

          {/* Main routes — visible after intro or on subsequent visits */}
          {!showIntro && (
            <div className="film-grain">
              <Routes>
                <Route
                  path="/login"
                  element={<PublicRoute><Login /></PublicRoute>}
                />
                <Route
                  path="/"
                  element={<ProtectedRoute><Layout /></ProtectedRoute>}
                >
                  <Route index element={<Home />} />
                  <Route path="watchlist" element={<Watchlist />} />
                </Route>
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </div>
          )}
        </BrowserRouter>
      </AppProvider>
    </AuthProvider>
  );
}

export default App;
