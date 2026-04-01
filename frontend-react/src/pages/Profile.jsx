import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { motion } from 'framer-motion';
import { Sparkles, Film, Globe, Clock, TrendingUp, Loader2 } from 'lucide-react';

const LANG_NAMES = {
  en: 'English', hi: 'Hindi', te: 'Telugu', ta: 'Tamil',
  ko: 'Korean', ja: 'Japanese', fr: 'French', es: 'Spanish',
  de: 'German', it: 'Italian', pt: 'Portuguese', zh: 'Chinese',
  ru: 'Russian', ar: 'Arabic', tr: 'Turkish',
};

const GENRE_COLORS = [
  'from-amber-500 to-orange-500',
  'from-violet-500 to-purple-600',
  'from-cyan-500 to-blue-500',
  'from-emerald-500 to-teal-500',
  'from-rose-500 to-pink-500',
  'from-yellow-400 to-amber-400',
  'from-indigo-500 to-violet-500',
  'from-sky-500 to-cyan-400',
];

const DECADE_COLOR = 'from-cinema-violet to-accent';

function StatCard({ icon, label, value, sub, delay = 0 }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.5 }}
      className="glass-card rounded-2xl p-5 flex flex-col gap-1.5 border border-white/5"
    >
      <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center mb-1">
        {icon}
      </div>
      <p className="text-2xl font-display font-bold text-white">{value}</p>
      <p className="text-sm font-semibold text-slate-300 font-body">{label}</p>
      {sub && <p className="text-xs text-slate-500 font-body">{sub}</p>}
    </motion.div>
  );
}

function BarRow({ name, count, maxCount, color, delay }) {
  const pct = maxCount > 0 ? (count / maxCount) * 100 : 0;
  return (
    <div>
      <div className="flex justify-between text-xs mb-1.5">
        <span className="text-slate-300 font-medium font-body">{name}</span>
        <span className="text-slate-500 font-body">{count}</span>
      </div>
      <div className="w-full bg-midnight-900 rounded-full h-2 overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 1, delay, ease: 'easeOut' }}
          className={`h-full rounded-full bg-gradient-to-r ${color}`}
        />
      </div>
    </div>
  );
}

export default function Profile() {
  const { user } = useAuth();
  const [profileData, setProfileData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchProfile = async () => {
      if (!user) return;
      const userId = user.username || user.userId || user.user_id;
      try {
        const res = await fetch(`/api/taste-profile/${userId}`);
        if (res.ok) setProfileData(await res.json());
      } catch (err) {
        console.error('Failed to fetch profile:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchProfile();
  }, [user]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4 text-slate-400">
        <Loader2 size={32} className="animate-spin text-accent" />
        <p className="font-body text-sm">Loading your Cinematic DNA…</p>
      </div>
    );
  }

  if (!profileData || profileData.total_interactions === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
        <div className="w-16 h-16 rounded-2xl bg-accent/10 flex items-center justify-center mb-5">
          <Film size={28} className="text-accent" />
        </div>
        <h2 className="text-2xl font-display font-bold text-white mb-2">No Data Yet</h2>
        <p className="text-slate-400 text-sm font-body max-w-xs">
          Like or save movies on the Discover page to build your Taste Profile!
        </p>
      </div>
    );
  }

  const maxGenre = Math.max(...profileData.genres.map((g) => g.count), 1);
  const maxDecade = Math.max(...profileData.decades.map((d) => d.count), 1);
  const maxLang = Math.max(...profileData.languages.map((l) => l.count), 1);

  const topGenre = profileData.genres[0]?.name ?? '—';
  const topDecade = profileData.decades.sort((a, b) => b.count - a.count)[0]?.name ?? '—';
  const topLang = LANG_NAMES[profileData.languages[0]?.name] ?? profileData.languages[0]?.name ?? '—';

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-12 space-y-10">

      {/* ── Hero ─────────────────────────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center"
      >
        {/* Avatar */}
        <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-accent via-cinema-violet to-cinema-neon mx-auto mb-5 flex items-center justify-center shadow-lg shadow-accent/20">
          <span className="text-3xl font-display font-bold text-midnight-950">
            {(user?.username?.[0] ?? 'M').toUpperCase()}
          </span>
        </div>
        <h1 className="text-4xl sm:text-5xl font-display font-bold text-white mb-2 tracking-tight">
          Your Cinematic DNA
        </h1>
        <div className="inline-flex items-center gap-2 bg-accent/5 border border-accent/15 rounded-full px-4 py-1.5 text-accent text-xs font-medium font-body mt-2">
          <Sparkles size={12} className="animate-glow-pulse" />
          {profileData.total_interactions} interactions analysed
        </div>
      </motion.div>

      {/* ── Quick Stats ──────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <StatCard icon={<Film size={16} className="text-accent" />}  label="Favourite Genre"  value={topGenre}  delay={0} />
        <StatCard icon={<Clock size={16} className="text-cinema-violet" />} label="Favourite Era" value={topDecade} delay={0.05} />
        <StatCard icon={<Globe size={16} className="text-cinema-neon" />}   label="Top Language"  value={topLang}   delay={0.1} />
        <StatCard
          icon={<TrendingUp size={16} className="text-emerald-400" />}
          label="Total Interactions"
          value={profileData.total_interactions}
          sub="Likes + Watchlists"
          delay={0.15}
        />
      </div>

      {/* ── Charts Grid ──────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

        {/* Genre Distribution */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="glass-card rounded-2xl p-6 border border-white/5"
        >
          <div className="flex items-center gap-2 mb-6">
            <Film size={15} className="text-accent" />
            <h3 className="text-base font-display font-semibold text-white">Genre Taste Map</h3>
          </div>
          <div className="space-y-4">
            {profileData.genres.map((g, i) => (
              <BarRow
                key={g.name}
                name={g.name}
                count={g.count}
                maxCount={maxGenre}
                color={GENRE_COLORS[i % GENRE_COLORS.length]}
                delay={0.3 + i * 0.07}
              />
            ))}
          </div>
        </motion.div>

        {/* Decade + Language stacked */}
        <div className="flex flex-col gap-6">

          {/* Favourite Decades */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25 }}
            className="glass-card rounded-2xl p-6 border border-white/5 flex-1"
          >
            <div className="flex items-center gap-2 mb-5">
              <Clock size={15} className="text-cinema-violet" />
              <h3 className="text-base font-display font-semibold text-white">Favourite Decades</h3>
            </div>
            <div className="space-y-4">
              {profileData.decades.length > 0 ? profileData.decades.map((d, i) => (
                <BarRow
                  key={d.name}
                  name={d.name}
                  count={d.count}
                  maxCount={maxDecade}
                  color={DECADE_COLOR}
                  delay={0.35 + i * 0.07}
                />
              )) : (
                <p className="text-slate-500 text-xs font-body">No decade data yet.</p>
              )}
            </div>
          </motion.div>

          {/* Language Palette */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="glass-card rounded-2xl p-6 border border-white/5"
          >
            <div className="flex items-center gap-2 mb-5">
              <Globe size={15} className="text-cinema-neon" />
              <h3 className="text-base font-display font-semibold text-white">Language Palette</h3>
            </div>
            <div className="flex flex-wrap gap-2">
              {profileData.languages.map((l, i) => {
                const pct = Math.round((l.count / maxLang) * 100);
                return (
                  <motion.span
                    key={l.name}
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.4 + i * 0.08 }}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border font-body"
                    style={{
                      background: `rgba(245,158,11,${0.05 + (pct / 100) * 0.2})`,
                      borderColor: `rgba(245,158,11,${0.1 + (pct / 100) * 0.3})`,
                      color: `rgba(255,255,255,${0.5 + (pct / 100) * 0.5})`,
                    }}
                  >
                    <span className="w-2 h-2 rounded-full bg-accent inline-block opacity-70" />
                    {LANG_NAMES[l.name] ?? l.name}
                    <span className="text-slate-500 text-[10px]">{l.count}</span>
                  </motion.span>
                );
              })}
            </div>
          </motion.div>

        </div>
      </div>

    </div>
  );
}
