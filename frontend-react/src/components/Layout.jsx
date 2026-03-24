import React, { useState, useEffect } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import { Bookmark, LogOut, User, Menu, X, Compass, Sparkles } from 'lucide-react';
import MiraiLogo from './MiraiLogo';

const Layout = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const navLinkClass = ({ isActive }) =>
    `relative flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all duration-300 ${
      isActive
        ? 'text-accent bg-accent/10 border border-accent/20'
        : 'text-slate-400 hover:text-white hover:bg-white/5 border border-transparent'
    }`;

  return (
    <div className="min-h-screen bg-midnight-950 flex flex-col">
      {/* ── Navbar ─────────────────────────────────────────────────────────── */}
      <motion.header
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        className={`sticky top-0 z-50 transition-all duration-500 ${
          scrolled
            ? 'bg-midnight-950/90 backdrop-blur-xl border-b border-white/5 shadow-lg shadow-black/20'
            : 'bg-transparent border-b border-transparent'
        }`}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          {/* Brand */}
          <NavLink to="/" className="flex items-center gap-3 group">
            <MiraiLogo size={32} className="group-hover:drop-shadow-[0_0_8px_rgba(245,158,11,0.4)] transition-all duration-300" />
            <div className="flex flex-col">
              <span className="font-display font-bold text-lg text-white tracking-tight leading-none">MIRAI</span>
              <span className="text-[9px] text-accent/60 tracking-[0.25em] uppercase font-body leading-none mt-0.5">Intelligence</span>
            </div>
          </NavLink>

          {/* Desktop Nav */}
          <nav className="hidden sm:flex items-center gap-2">
            <NavLink to="/" end className={navLinkClass}>
              <Compass size={14} /> Discover
            </NavLink>
            <NavLink to="/watchlist" className={navLinkClass}>
              <Bookmark size={14} /> Watchlist
            </NavLink>
          </nav>

          {/* User + logout */}
          <div className="hidden sm:flex items-center gap-4">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/5 border border-white/5">
              <div className="w-6 h-6 rounded-full bg-gradient-to-br from-accent to-cinema-violet flex items-center justify-center">
                <User size={12} className="text-white" />
              </div>
              <span className="text-sm text-slate-300 max-w-[100px] truncate font-medium">{user?.username}</span>
            </div>
            <button
              id="logout-btn"
              onClick={handleLogout}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-slate-500 hover:text-red-400 hover:bg-red-500/10 border border-transparent hover:border-red-500/20 transition-all duration-300"
            >
              <LogOut size={14} /> Sign out
            </button>
          </div>

          {/* Mobile hamburger */}
          <button
            className="sm:hidden text-slate-400 hover:text-accent transition-colors"
            onClick={() => setMobileMenuOpen((v) => !v)}
          >
            {mobileMenuOpen ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>

        {/* Mobile dropdown */}
        <AnimatePresence>
          {mobileMenuOpen && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="sm:hidden overflow-hidden border-t border-white/5"
            >
              <div className="px-4 pb-4 pt-3 space-y-2 bg-midnight-950/95 backdrop-blur-xl">
                <NavLink to="/" end className={navLinkClass} onClick={() => setMobileMenuOpen(false)}>
                  <Compass size={14} /> Discover
                </NavLink>
                <NavLink to="/watchlist" className={navLinkClass} onClick={() => setMobileMenuOpen(false)}>
                  <Bookmark size={14} /> Watchlist
                </NavLink>
                <div className="pt-3 border-t border-white/5 mt-2 flex items-center justify-between">
                  <span className="text-slate-400 text-sm flex items-center gap-2">
                    <User size={14} />{user?.username}
                  </span>
                  <button onClick={handleLogout} className="text-sm text-red-400 flex items-center gap-1.5">
                    <LogOut size={14} /> Sign out
                  </button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Animated gradient line at bottom of header */}
        <div className="h-[1px] w-full bg-gradient-to-r from-transparent via-accent/20 to-transparent" />
      </motion.header>

      {/* ── Page content ───────────────────────────────────────────────────── */}
      <main className="flex-1">
        <Outlet />
      </main>

      {/* ── Footer ─────────────────────────────────────────────────────────── */}
      <footer className="border-t border-white/5 py-6 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <MiraiLogo size={18} />
            <span className="text-xs text-slate-500 font-body">MIRAI Cinematic Intelligence</span>
          </div>
          <div className="flex items-center gap-1.5 text-[10px] text-slate-600">
            <Sparkles size={10} className="text-accent/40" />
            <span>Powered by Gemini AI & pgvector · Data via TMDB</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Layout;
