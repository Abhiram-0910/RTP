import React, { useState } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Film, Bookmark, LogOut, User, Menu, X } from 'lucide-react';

const Layout = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const navLinkClass = ({ isActive }) =>
    `flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
      isActive
        ? 'bg-blue-600/20 text-blue-400'
        : 'text-slate-400 hover:text-white hover:bg-slate-800'
    }`;

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col">
      {/* ── Navbar ─────────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-50 bg-slate-950/80 backdrop-blur border-b border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          {/* Brand */}
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 bg-blue-600 rounded-lg">
              <Film size={18} className="text-white" />
            </div>
            <span className="text-white font-bold text-base tracking-tight">MRS</span>
            <span className="hidden sm:inline text-slate-500 text-xs ml-1">AI Recommendations</span>
          </div>

          {/* Desktop Nav */}
          <nav className="hidden sm:flex items-center gap-1">
            <NavLink to="/" end className={navLinkClass}>Discover</NavLink>
            <NavLink to="/watchlist" className={navLinkClass}>
              <Bookmark size={14} /> Watchlist
            </NavLink>
          </nav>

          {/* User + logout */}
          <div className="hidden sm:flex items-center gap-3">
            <div className="flex items-center gap-1.5 text-sm text-slate-400">
              <User size={14} />
              <span className="max-w-[120px] truncate">{user?.username}</span>
            </div>
            <button
              id="logout-btn"
              onClick={handleLogout}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-slate-400 hover:text-white hover:bg-slate-800 transition-all"
            >
              <LogOut size={14} /> Sign out
            </button>
          </div>

          {/* Mobile hamburger */}
          <button
            className="sm:hidden text-slate-400 hover:text-white"
            onClick={() => setMobileMenuOpen((v) => !v)}
          >
            {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>

        {/* Mobile dropdown */}
        {mobileMenuOpen && (
          <div className="sm:hidden px-4 pb-4 space-y-1 border-t border-slate-800 pt-3">
            <NavLink to="/" end className={navLinkClass} onClick={() => setMobileMenuOpen(false)}>Discover</NavLink>
            <NavLink to="/watchlist" className={navLinkClass} onClick={() => setMobileMenuOpen(false)}>
              <Bookmark size={14} /> Watchlist
            </NavLink>
            <div className="pt-2 border-t border-slate-800 mt-2 flex items-center justify-between">
              <span className="text-slate-400 text-sm flex items-center gap-1.5"><User size={14} />{user?.username}</span>
              <button onClick={handleLogout} className="text-sm text-slate-400 flex items-center gap-1.5 hover:text-white">
                <LogOut size={14} /> Sign out
              </button>
            </div>
          </div>
        )}
      </header>

      {/* ── Page content ───────────────────────────────────────────────────── */}
      <main className="flex-1">
        <Outlet />
      </main>

      {/* ── Footer ─────────────────────────────────────────────────────────── */}
      <footer className="border-t border-slate-800 py-4 text-center text-xs text-slate-600">
        MRS · Powered by Gemini AI & pgvector · Streaming data via JustWatch / TMDB
      </footer>
    </div>
  );
};

export default Layout;
