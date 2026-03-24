import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import toast from 'react-hot-toast';
import { Loader2, LogIn, UserPlus, Eye, EyeOff } from 'lucide-react';
import MiraiLogo from '../components/MiraiLogo';

const TABS = { LOGIN: 'login', REGISTER: 'register' };

const Login = () => {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const [tab, setTab] = useState(TABS.LOGIN);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      toast.error('Please fill in all fields.');
      return;
    }
    setLoading(true);
    try {
      if (tab === TABS.LOGIN) {
        await login(username.trim(), password);
        toast.success(`Welcome back, ${username}!`);
        navigate('/');
      } else {
        await register(username.trim(), password);
        toast.success('Account created! Please log in.');
        setTab(TABS.LOGIN);
        setPassword('');
      }
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (Array.isArray(detail)) {
        toast.error(detail[0]?.msg || 'Validation error.');
      } else {
        toast.error(detail || (tab === TABS.LOGIN ? 'Login failed.' : 'Registration failed.'));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-midnight-950 flex items-center justify-center px-4 relative overflow-hidden">
      {/* Animated ambient orbs */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <motion.div
          className="absolute -top-32 -left-32 w-[500px] h-[500px] rounded-full"
          style={{ background: 'radial-gradient(circle, rgba(245,158,11,0.08) 0%, transparent 70%)' }}
          animate={{ x: [0, 30, 0], y: [0, -20, 0] }}
          transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
        />
        <motion.div
          className="absolute -bottom-48 -right-32 w-[600px] h-[600px] rounded-full"
          style={{ background: 'radial-gradient(circle, rgba(139,92,246,0.06) 0%, transparent 70%)' }}
          animate={{ x: [0, -25, 0], y: [0, 30, 0] }}
          transition={{ duration: 10, repeat: Infinity, ease: 'easeInOut' }}
        />
        <motion.div
          className="absolute top-1/3 right-1/4 w-[300px] h-[300px] rounded-full"
          style={{ background: 'radial-gradient(circle, rgba(6,182,212,0.04) 0%, transparent 70%)' }}
          animate={{ x: [0, 15, 0], y: [0, -15, 0] }}
          transition={{ duration: 12, repeat: Infinity, ease: 'easeInOut' }}
        />
      </div>

      <motion.div
        className="relative w-full max-w-md"
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, ease: 'easeOut' }}
      >
        {/* Logo */}
        <div className="text-center mb-10">
          <div className="inline-flex flex-col items-center gap-3">
            <MiraiLogo size={56} animate />
            <h1 className="text-3xl font-display font-bold text-gradient tracking-tight">MIRAI</h1>
            <p className="text-slate-500 text-sm font-body tracking-wide">Cinematic Intelligence Engine</p>
          </div>
        </div>

        {/* Card */}
        <div className="glass-card rounded-3xl p-8 relative overflow-hidden">
          {/* Subtle gradient accent at top */}
          <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-accent/40 to-transparent" />

          {/* Tabs */}
          <div className="flex rounded-2xl bg-midnight-900/60 p-1 mb-8 border border-white/5">
            {[TABS.LOGIN, TABS.REGISTER].map((t) => (
              <button
                key={t}
                onClick={() => { setTab(t); setPassword(''); }}
                className={`relative flex-1 py-2.5 rounded-xl text-sm font-medium capitalize transition-all duration-300 font-display ${
                  tab === t
                    ? 'text-midnight-950 shadow-md'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {tab === t && (
                  <motion.div
                    layoutId="activeTab"
                    className="absolute inset-0 bg-gradient-to-r from-accent to-accent-light rounded-xl"
                    transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                  />
                )}
                <span className="relative z-10">{t === TABS.LOGIN ? 'Sign In' : 'Sign Up'}</span>
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Username */}
            <div>
              <label className="block text-[11px] font-semibold text-slate-400 uppercase tracking-[0.15em] mb-2 font-body">
                Username
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="your_username"
                autoComplete="username"
                className="w-full glow-input text-white placeholder-slate-600 rounded-xl px-4 py-3.5 text-sm outline-none font-body"
              />
            </div>

            {/* Password */}
            <div>
              <label className="block text-[11px] font-semibold text-slate-400 uppercase tracking-[0.15em] mb-2 font-body">
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={tab === TABS.REGISTER ? 'Min. 8 characters' : '••••••••'}
                  autoComplete={tab === TABS.LOGIN ? 'current-password' : 'new-password'}
                  className="w-full glow-input text-white placeholder-slate-600 rounded-xl px-4 py-3.5 pr-12 text-sm outline-none font-body"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-accent transition-colors"
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {/* Submit */}
            <motion.button
              id="auth-submit"
              type="submit"
              disabled={loading}
              whileHover={{ scale: loading ? 1 : 1.02 }}
              whileTap={{ scale: loading ? 1 : 0.98 }}
              className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-accent to-accent-light hover:from-accent-light hover:to-accent disabled:opacity-60 disabled:cursor-not-allowed text-midnight-950 font-display font-bold rounded-xl py-3.5 text-sm transition-all shadow-lg shadow-accent/20 hover:shadow-accent/30 mt-3"
            >
              {loading ? (
                <Loader2 size={16} className="animate-spin" />
              ) : tab === TABS.LOGIN ? (
                <><LogIn size={16} /> Sign In</>
              ) : (
                <><UserPlus size={16} /> Create Account</>
              )}
            </motion.button>
          </form>

          {/* Demo hint */}
          {tab === TABS.LOGIN && (
            <p className="text-center text-[11px] text-slate-500 mt-6 font-body">
              Demo: <span className="text-accent/60 font-mono text-[10px]">admin / mirai2024</span>
            </p>
          )}
        </div>
      </motion.div>
    </div>
  );
};

export default Login;
