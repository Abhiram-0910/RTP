import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import toast from 'react-hot-toast';
import { Film, Loader2, LogIn, UserPlus, Eye, EyeOff } from 'lucide-react';

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
    <div className="min-h-screen bg-slate-950 flex items-center justify-center px-4">
      {/* Ambient glow */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -left-40 w-96 h-96 bg-blue-600/10 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-purple-600/10 rounded-full blur-3xl" />
      </div>

      <div className="relative w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-3 mb-3">
            <div className="p-2.5 bg-blue-600 rounded-xl shadow-lg shadow-blue-600/30">
              <Film size={24} className="text-white" />
            </div>
            <h1 className="text-2xl font-bold text-white tracking-tight">MRS</h1>
          </div>
          <p className="text-slate-400 text-sm">Your AI-powered recommendation engine</p>
        </div>

        {/* Card */}
        <div className="bg-slate-900/80 backdrop-blur border border-slate-800 rounded-2xl p-8 shadow-2xl">
          {/* Tabs */}
          <div className="flex rounded-xl bg-slate-800/60 p-1 mb-7">
            {[TABS.LOGIN, TABS.REGISTER].map((t) => (
              <button
                key={t}
                onClick={() => { setTab(t); setPassword(''); }}
                className={`flex-1 py-2 rounded-lg text-sm font-medium capitalize transition-all duration-200 ${
                  tab === t
                    ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/30'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {t === TABS.LOGIN ? 'Sign In' : 'Sign Up'}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Username */}
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                Username
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="your_username"
                autoComplete="username"
                className="w-full bg-slate-800/80 border border-slate-700 focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30 text-white placeholder-slate-500 rounded-xl px-4 py-3 text-sm outline-none transition-all"
              />
            </div>

            {/* Password */}
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
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
                  className="w-full bg-slate-800/80 border border-slate-700 focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30 text-white placeholder-slate-500 rounded-xl px-4 py-3 pr-12 text-sm outline-none transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {/* Submit */}
            <button
              id="auth-submit"
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-60 disabled:cursor-not-allowed text-white font-semibold rounded-xl py-3 text-sm transition-all shadow-lg shadow-blue-600/20 hover:shadow-blue-500/30 mt-2"
            >
              {loading ? (
                <Loader2 size={16} className="animate-spin" />
              ) : tab === TABS.LOGIN ? (
                <><LogIn size={16} /> Sign In</>
              ) : (
                <><UserPlus size={16} /> Create Account</>
              )}
            </button>
          </form>

          {/* Demo hint */}
          {tab === TABS.LOGIN && (
            <p className="text-center text-xs text-slate-500 mt-5">
              Default admin: <span className="text-slate-400 font-mono">admin / mirai2024</span>
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

export default Login;
