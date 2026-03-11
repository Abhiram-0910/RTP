import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { AuthProvider, useAuth } from './context/AuthContext';
import { AppProvider } from './context/AppContext';
import Layout from './components/Layout';
import Home from './pages/Home';
import Watchlist from './pages/Watchlist';
import Login from './pages/Login';

/** Redirect unauthenticated users to /login */
const ProtectedRoute = ({ children }) => {
  const { user, authReady } = useAuth();
  if (!authReady) return null; // Wait for localStorage restore
  return user ? children : <Navigate to="/login" replace />;
};

/** Redirect already-logged-in users away from /login */
const PublicRoute = ({ children }) => {
  const { user, authReady } = useAuth();
  if (!authReady) return null;
  return user ? <Navigate to="/" replace /> : children;
};

function App() {
  return (
    <AuthProvider>
      <AppProvider>
        <BrowserRouter>
          <Toaster
            position="top-right"
            toastOptions={{
              style: { background: '#1e293b', color: '#f8fafc', border: '1px solid #334155' },
              success: { iconTheme: { primary: '#3b82f6', secondary: '#fff' } },
            }}
          />
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
        </BrowserRouter>
      </AppProvider>
    </AuthProvider>
  );
}

export default App;
