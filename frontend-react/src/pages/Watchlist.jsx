import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import { Star, Film, X, AlertCircle, Loader2, Heart, ThumbsDown, Bookmark, Compass } from 'lucide-react';
import api from '../services/api';

const StatCard = ({ label, value, icon: Icon, color, loading }) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    className="glass-card rounded-2xl p-6 transition-all hover:shadow-card-hover group"
  >
    {loading ? (
      <div className="h-12 shimmer bg-midnight-800 rounded" />
    ) : (
      <>
        <div className="flex items-center gap-2 mb-3">
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${color} bg-opacity-10`}>
            <Icon size={16} />
          </div>
          <p className="text-slate-500 text-[11px] font-semibold uppercase tracking-[0.15em] font-body">{label}</p>
        </div>
        <p className={`text-4xl font-display font-bold ${color}`}>{value}</p>
      </>
    )}
  </motion.div>
);

const Watchlist = () => {
  const [stats, setStats]       = useState({ movies_liked: 0, movies_disliked: 0, watchlist_size: 0 });
  const [watchlist, setWatchlist] = useState([]);
  const [loading, setLoading]   = useState(true);
  const [isError, setError]     = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const [statsRes, listRes] = await Promise.all([
        api.get('/api/user_stats'),
        api.get('/api/watchlist'),
      ]);
      setStats(statsRes.data);
      setWatchlist(listRes.data.watchlist || []);
    } catch (err) {
      console.error('Watchlist fetch error:', err);
      setError(true);
      toast.error('Failed to load watchlist.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const removeItem = async (tmdbId, title) => {
    try {
      await api.post('/api/watchlist', { tmdb_id: tmdbId, action: 'remove' });
      setWatchlist((prev) => prev.filter((i) => i.id !== tmdbId));
      setStats((prev) => ({ ...prev, watchlist_size: Math.max(0, prev.watchlist_size - 1) }));
      toast.success(`Removed "${title}" from Watchlist`);
    } catch {
      toast.error('Failed to remove item.');
    }
  };

  if (isError) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center py-24 px-4 gap-4">
        <AlertCircle size={48} className="text-cinema-crimson" />
        <h3 className="text-xl font-display font-bold text-white">Failed to load watchlist</h3>
        <button onClick={fetchData} className="text-accent hover:text-accent-light text-sm underline font-body">
          Try again
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-10">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-8"
      >
        <h1 className="text-3xl font-display font-bold text-white mb-2">
          Your <span className="text-gradient">Archive</span>
        </h1>
        <p className="text-slate-500 text-sm font-body">Track your cinematic journey</p>
      </motion.div>

      {/* ── Stats ─────────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-10">
        <StatCard label="Loved" value={stats.movies_liked} icon={Heart} color="text-cinema-crimson" loading={loading} />
        <StatCard label="Passed" value={stats.movies_disliked} icon={ThumbsDown} color="text-slate-400" loading={loading} />
        <StatCard label="Watchlist" value={stats.watchlist_size} icon={Bookmark} color="text-accent" loading={loading} />
      </div>

      {/* ── Watchlist grid ────────────────────────────────────────────────── */}
      {loading ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="aspect-[2/3] shimmer bg-midnight-800 rounded-2xl" />
          ))}
        </div>
      ) : watchlist.length === 0 ? (
        <motion.section
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="flex flex-col items-center justify-center py-24 glass-card rounded-3xl gap-6"
        >
          <div className="relative w-28 h-28">
            <div className="absolute inset-0 bg-accent/10 rounded-full blur-2xl animate-glow-pulse" />
            <div className="relative w-full h-full rounded-full bg-midnight-800 border border-white/10 flex items-center justify-center">
              <Film size={44} className="text-accent animate-float" />
            </div>
          </div>
          <div className="text-center">
            <h3 className="text-white text-xl font-display font-bold mb-2">Your watchlist is empty</h3>
            <p className="text-slate-400 text-sm font-body">Save movies to watch later using the 🔖 button on any card.</p>
          </div>
          <Link
            to="/"
            className="bg-gradient-to-r from-accent to-accent-light hover:from-accent-light hover:to-accent text-midnight-950 font-display font-bold px-6 py-2.5 rounded-xl transition-all shadow-glow-sm flex items-center gap-2"
          >
            <Compass size={16} /> Discover Movies
          </Link>
        </motion.section>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-5">
          <AnimatePresence>
            {watchlist.map((item, index) => (
              <motion.div
                key={item.id}
                layout
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.8, transition: { duration: 0.3 } }}
                transition={{ delay: index * 0.04 }}
                className="group relative aspect-[2/3] glass-card gradient-border rounded-2xl overflow-hidden"
              >
                {item.poster_path ? (
                  <img
                    src={item.poster_path}
                    alt={item.title}
                    className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-700 ease-out"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center bg-midnight-800">
                    <Film size={36} className="text-slate-700" />
                  </div>
                )}
                {/* Hover overlay */}
                <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex flex-col items-center justify-end p-4 text-center gap-2">
                  <p className="text-white font-display font-semibold text-sm leading-tight line-clamp-2">{item.title}</p>
                  {item.rating && (
                    <span className="flex items-center gap-1 text-accent text-xs font-body">
                      <Star size={10} fill="currentColor" /> {item.rating?.toFixed(1)}
                    </span>
                  )}
                  <motion.button
                    whileHover={{ scale: 1.1 }}
                    whileTap={{ scale: 0.9 }}
                    onClick={() => removeItem(item.id, item.title)}
                    className="w-9 h-9 rounded-full bg-white/10 hover:bg-cinema-crimson border border-white/10 hover:border-cinema-crimson flex items-center justify-center text-white transition-all mt-1"
                    title="Remove from Watchlist"
                  >
                    <X size={16} />
                  </motion.button>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
};

export default Watchlist;
