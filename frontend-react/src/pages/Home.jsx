import React, { useState, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Search, Star, Heart, ThumbsDown, BookmarkPlus,
  SlidersHorizontal, ChevronDown, ChevronUp, Loader2,
  Tv, Film, Globe, Layers, Sparkles, AlertCircle, X,
} from 'lucide-react';
import { getRecommendations, rateTitle } from '../services/api';
import { useAppContext } from '../context/AppContext';

// ── Filter options ─────────────────────────────────────────────────────────────
const GENRES = ['Action', 'Comedy', 'Drama', 'Horror', 'Romance', 'Sci-Fi', 'Thriller', 'Animation', 'Documentary'];
const MOODS  = ['Feel-good', 'Dark & gritty', 'Mind-bending', 'Emotional', 'Lighthearted', 'Suspenseful'];
const MEDIA_TYPES = [
  { label: 'All',    value: 'All',   icon: <Layers size={13} /> },
  { label: 'Movies', value: 'movie', icon: <Film size={13} /> },
  { label: 'TV',     value: 'tv',    icon: <Tv size={13} /> },
];
const LANGUAGES = [
  { label: 'All',     value: 'all' },
  { label: 'English', value: 'en' },
  { label: 'Hindi',   value: 'hi' },
  { label: 'Telugu',  value: 'te' },
];
const RATING_NONE = null;
const RATING_LIKE = 'like';
const RATING_DISLIKE = 'dislike';

// ── Stars component ────────────────────────────────────────────────────────────
const Stars = ({ rating }) => (
  <span className="flex items-center gap-1 text-accent text-xs font-semibold font-body">
    <Star size={11} fill="currentColor" />
    {rating?.toFixed(1) ?? '—'}
  </span>
);

// ── Provider badge ─────────────────────────────────────────────────────────────
const ProviderBadge = ({ name, type }) => {
  const colors = {
    flatrate: 'bg-cinema-neon/10 text-cinema-neon border-cinema-neon/20',
    free:     'bg-emerald-600/10 text-emerald-300 border-emerald-700/20',
    ads:      'bg-accent/10 text-accent border-accent/20',
    rent:     'bg-cinema-violet/10 text-cinema-violet border-cinema-violet/20',
    buy:      'bg-cinema-crimson/10 text-cinema-crimson border-cinema-crimson/20',
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium border font-body ${colors[type] || 'bg-white/5 text-slate-400 border-white/10'}`}>
      {name}
    </span>
  );
};

// ── Movie Card ─────────────────────────────────────────────────────────────────
const MovieCard = ({ movie, ratingState = {}, pending, onRate, index }) => {
  const [expanded, setExpanded] = useState(false);
  const [localExplanation, setLocalExplanation] = useState(movie.explanation);
  const [isExplanationReady, setIsExplanationReady] = useState(!!movie.explanation);
  const [isFadingIn, setIsFadingIn] = useState(false);
  const languagePref = useAppContext?.()?.language || 'en';

  useEffect(() => {
    if (isExplanationReady) return;
    const pollInterval = setInterval(async () => {
      try {
        const res = await fetch(`http://localhost:8005/api/explanation/${movie.id}?lang=${languagePref}`);
        if (!res.ok) return;
        const data = await res.json();
        if (data.ready) {
          clearInterval(pollInterval);
          setLocalExplanation(data.explanation || 'Highly relevant based on AI analysis.');
          setIsExplanationReady(true);
          setIsFadingIn(true);
          setTimeout(() => setIsFadingIn(false), 1000);
        }
      } catch (err) {
        console.error(`Polling error for ${movie.id}:`, err);
      }
    }, 1500);
    return () => clearInterval(pollInterval);
  }, [movie.id, isExplanationReady, languagePref]);

  const currentRating = ratingState[movie.id] ?? null;
  const isPending = pending.has(movie.id);
  const providers = movie.providers || [];
  const streamProviders = providers.filter((p) => p.type === 'flatrate');
  const otherProviders = providers.filter((p) => p.type !== 'flatrate').slice(0, 3);

  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.5, ease: 'easeOut' }}
      className="group glass-card gradient-border tilt-card rounded-2xl overflow-hidden flex flex-col"
    >
      {/* Poster */}
      <div className="relative aspect-[2/3] overflow-hidden bg-midnight-900">
        {movie.poster_path ? (
          <img
            src={movie.poster_path}
            alt={movie.title}
            loading="lazy"
            className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-700 ease-out"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-midnight-800">
            <Film size={40} className="text-slate-700" />
          </div>
        )}
        {/* Gradient overlay on poster */}
        <div className="absolute inset-0 bg-gradient-to-t from-midnight-950 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
        {/* Match score badge */}
        <div className="absolute top-2.5 right-2.5 bg-accent/90 backdrop-blur-sm text-midnight-950 text-[10px] font-bold font-display px-2.5 py-1 rounded-full shadow-glow-sm">
          {movie.match_score}%
        </div>
        {/* Media type badge */}
        <div className="absolute top-2.5 left-2.5 bg-midnight-950/70 backdrop-blur-sm text-slate-300 text-[10px] font-medium px-2.5 py-1 rounded-full flex items-center gap-1 border border-white/10">
          {movie.media_type === 'tv' ? <Tv size={9} /> : <Film size={9} />}
          {movie.media_type === 'tv' ? 'TV' : 'Movie'}
        </div>
      </div>

      {/* Body */}
      <div className="p-4 flex flex-col flex-1 gap-3">
        <div>
          <h3 className="text-white font-display font-semibold text-sm leading-tight line-clamp-2">{movie.title}</h3>
          <div className="flex items-center gap-2 mt-1.5 text-slate-500 text-[11px] font-body">
            <Stars rating={movie.rating} />
            {movie.release_date && <span>{movie.release_date.slice(0, 4)}</span>}
          </div>
        </div>

        {/* Overview toggle */}
        <div>
          <p className={`text-slate-400 text-xs leading-relaxed font-body ${expanded ? '' : 'line-clamp-3'}`}>
            {movie.overview || 'No overview available.'}
          </p>
          {movie.overview && movie.overview.length > 120 && (
            <button
              onClick={() => setExpanded((v) => !v)}
              className="text-accent/70 text-[11px] mt-1 hover:text-accent flex items-center gap-0.5 transition-colors font-body"
            >
              {expanded ? <><ChevronUp size={11} /> Less</> : <><ChevronDown size={11} /> More</>}
            </button>
          )}
        </div>

        {/* Streaming providers */}
        {streamProviders.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {streamProviders.slice(0, 4).map((p) => (
              <ProviderBadge key={p.provider + p.region} name={p.provider} type={p.type} />
            ))}
            {otherProviders.map((p) => (
              <ProviderBadge key={p.provider + p.type} name={p.provider} type={p.type} />
            ))}
          </div>
        )}

        {/* AI Insight Box */}
        <div className={`mt-2 pl-3 py-2 rounded-lg border-l-2 transition-all duration-700 ease-in-out ${
            isExplanationReady
              ? 'border-accent/60 bg-accent/5'
              : 'border-white/10 bg-white/[0.02]'
          } ${isFadingIn ? 'animate-fade-in' : ''}`}
        >
          {isExplanationReady ? (
            <>
              <p className="text-slate-300 text-[11px] leading-snug italic font-body">{localExplanation}</p>
              {/* Provider badge */}
              {movie.explanation_provider && (
                <span className={`inline-flex items-center gap-1 mt-1.5 text-[9px] font-semibold px-1.5 py-0.5 rounded-full border font-body ${
                  movie.explanation_provider === 'ollama'
                    ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                    : 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20'
                }`}>
                  {movie.explanation_provider === 'ollama' ? '⚡ Local AI' : '✦ Gemini'}
                </span>
              )}
            </>
          ) : (
            <p className="text-slate-500 text-[11px] leading-snug italic flex items-center gap-2 font-body">
               <span className="w-3 h-3 border-2 border-white/10 border-t-accent rounded-full animate-spin inline-block" />
               ✦ AI Insight — Generating...
            </p>
          )}
        </div>


        {/* Similarity Factors */}
        {movie.similarity_factors && (
          <div className="flex flex-col gap-1.5 mt-2 bg-midnight-900/50 rounded-xl p-2.5 border border-white/5">
            {['mood', 'genre', 'theme', 'rating'].map((factor) => {
              const val = movie.similarity_factors[factor] || 0;
              const pct = Math.round(val * 100);
              const colors = { mood: 'bg-accent', genre: 'bg-cinema-violet', theme: 'bg-cinema-neon', rating: 'bg-emerald-400' };
              return (
                <div key={factor} className="flex items-center text-[10px] font-body">
                  <span className="w-10 text-slate-500 capitalize">{factor}</span>
                  <div className="flex-1 bg-midnight-800 h-1.5 rounded-full overflow-hidden mx-2">
                    <motion.div
                      className={`h-full rounded-full ${colors[factor]}`}
                      initial={{ width: 0 }}
                      animate={{ width: `${pct}%` }}
                      transition={{ delay: 0.3, duration: 0.8, ease: 'easeOut' }}
                    />
                  </div>
                  <span className="w-6 text-right text-slate-300 font-medium">{pct}%</span>
                </div>
              );
            })}
          </div>
        )}

        {/* Action buttons */}
        <div className="flex gap-2 mt-auto pt-1">
          <motion.button
            whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}
            id={`like-${movie.id}`}
            disabled={isPending}
            onClick={() => onRate(movie.id, RATING_LIKE, movie.title)}
            className={`flex-1 flex items-center justify-center gap-1 py-2 rounded-xl text-xs font-semibold border transition-all font-body ${
              currentRating === RATING_LIKE
                ? 'bg-cinema-crimson/20 border-cinema-crimson/40 text-cinema-crimson shadow-lg shadow-red-600/10'
                : 'border-white/10 text-slate-400 hover:border-cinema-crimson/30 hover:text-cinema-crimson hover:bg-cinema-crimson/5'
            } ${isPending ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            <Heart size={12} fill={currentRating === RATING_LIKE ? 'currentColor' : 'none'} />
            Love
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}
            id={`dislike-${movie.id}`}
            disabled={isPending}
            onClick={() => onRate(movie.id, RATING_DISLIKE, movie.title)}
            className={`flex-1 flex items-center justify-center gap-1 py-2 rounded-xl text-xs font-semibold border transition-all font-body ${
              currentRating === RATING_DISLIKE
                ? 'bg-white/10 border-white/20 text-slate-200'
                : 'border-white/10 text-slate-400 hover:border-white/20 hover:text-slate-300 hover:bg-white/5'
            } ${isPending ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            <ThumbsDown size={12} />
            Pass
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
            id={`watchlist-${movie.id}`}
            disabled={isPending}
            onClick={() => onRate(movie.id, 'watchlist', movie.title)}
            className={`px-3 py-2 rounded-xl text-xs font-semibold border transition-all ${
              currentRating === 'watchlist'
                ? 'bg-accent/20 border-accent/40 text-accent shadow-glow-sm'
                : 'border-white/10 text-slate-400 hover:border-accent/30 hover:text-accent hover:bg-accent/5'
            } ${isPending ? 'opacity-50 cursor-not-allowed' : ''}`}
            title="Save to Watchlist"
          >
            <BookmarkPlus size={12} />
          </motion.button>
        </div>
      </div>
    </motion.div>
  );
};

// ── Home Page ──────────────────────────────────────────────────────────────────
const Home = () => {
  const [userId] = useState(() => localStorage.getItem('Movies and TV shows Recommendation Engine_user_id') || `user_${Date.now()}`);
  const [query, setQuery]         = useState('');
  const [loading, setLoading]     = useState(false);
  const [results, setResults]     = useState([]);
  const [explanation, setExpl]    = useState('');
  const [hasSearched, setHasSearched]= useState(false);
  const [isError, setError]       = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [deepAnalysis, setDeepAnalysis] = useState('');
  const [deepSources, setDeepSources] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [feedbackGiven, setFeedbackGiven] = useState(false);
  const [showFilters, setShowFilt]= useState(false);
  const [mediaType, setMediaType] = useState('All');
  const [language, setLanguage]   = useState('all');
  const [genre, setGenre]         = useState('');
  const [mood, setMood]           = useState('');
  const [minRating, setMinRating] = useState(0);
  const [ratingState, setRatingState] = useState({});
  const [pending, setPending]         = useState(new Set());

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 60000);
    return () => clearInterval(interval);
  }, []);

  const fetchMetrics = async () => {
    try {
      const res = await fetch('http://localhost:8005/api/metrics');
      if (res.ok) setMetrics(await res.json());
    } catch (err) {
      console.error('Failed to fetch metrics', err);
    }
  };

  const handleSearch = async (e) => {
    e?.preventDefault();
    const finalQuery = [query.trim(), mood].filter(Boolean).join(' — ');
    if (!finalQuery) return;
    setLoading(true);
    setHasSearched(true);
    setFeedbackGiven(false);
    setError(false);
    setResults([]);
    setExpl('');
    setRatingState({});
    setDeepAnalysis('');
    setDeepSources([]);
    try {
      const { data } = await getRecommendations({
        query: finalQuery,
        user_id: userId,
        media_type: mediaType,
        min_rating: minRating,
        genre: genre || null,
        language_pref: language,
      });
      setResults(data.movies || data.results || []);
      setExpl(data.explanation || '');
      if (!data.movies?.length) toast('No matches. Try a different search!', { icon: '🤔' });
    } catch (err) {
      console.error(err);
      setError(true);
      toast.error('Search failed. Check if backend is running.');
    } finally {
      setLoading(false);
    }
  };

  const handleDeepAnalyze = async () => {
    if (!query || results.length === 0) return;
    setIsAnalyzing(true);
    setDeepAnalysis('');
    setDeepSources([]);
    try {
      const candidateIds = results.slice(0, 8).map(r => r.id);
      const res = await fetch('http://localhost:8005/api/deep-analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, candidate_tmdb_ids: candidateIds })
      });
      if (!res.ok) throw new Error('Failed to analyze');
      const data = await res.json();
      setDeepAnalysis(data.analysis || 'Analysis unavailable.');
      setDeepSources(data.sources_used || []);
    } catch (err) {
      console.error('Deep analysis error:', err);
      toast.error('LangChain RAG analysis failed.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleRate = useCallback(async (tmdbId, type, title) => {
    const prev = ratingState[tmdbId] ?? null;
    const next = prev === type ? RATING_NONE : type;
    setRatingState((s) => ({ ...s, [tmdbId]: next }));
    setPending((s) => new Set(s).add(tmdbId));
    try {
      await rateTitle(tmdbId, next || 'remove');
      toast.success(
        next === RATING_LIKE ? `Loved "${title}"` :
        next === RATING_DISLIKE ? `Passed on "${title}"` :
        next === 'watchlist' ? `Added "${title}" to Watchlist` :
        `Removed rating for "${title}"`
      );
    } catch {
      setRatingState((s) => ({ ...s, [tmdbId]: prev }));
      toast.error('Could not save rating.');
    } finally {
      setPending((s) => { const n = new Set(s); n.delete(tmdbId); return n; });
    }
  }, [ratingState]);

  const activeFilters = [
    mediaType !== 'All', language !== 'all', !!genre, !!mood, minRating > 0
  ].filter(Boolean).length;

  // Pill button helper for filters
  const FilterPill = ({ active, onClick, children }) => (
    <motion.button
      whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }}
      onClick={onClick}
      className={`px-3 py-1.5 rounded-xl text-xs font-medium border transition-all font-body ${
        active
          ? 'bg-accent/15 border-accent/30 text-accent'
          : 'border-white/8 text-slate-400 hover:border-white/15 hover:text-white hover:bg-white/5'
      }`}
    >
      {children}
    </motion.button>
  );

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-10">

      {/* ── Hero ──────────────────────────────────────────────────────────── */}
      <motion.div
        className="text-center mb-12"
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7 }}
      >
        <div className="inline-flex items-center gap-2 bg-accent/5 border border-accent/15 rounded-full px-4 py-1.5 text-accent text-xs font-medium font-body mb-5">
          <Sparkles size={12} className="animate-glow-pulse" /> Powered by Gemini AI + pgvector
        </div>
        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-display font-bold text-white mb-4 tracking-tight leading-none">
          What do you want to{' '}
          <span className="text-gradient">watch</span>
          <span className="text-accent">?</span>
        </h1>
        <p className="text-slate-400 text-sm sm:text-base max-w-xl mx-auto font-body">
          Search in <span className="text-white font-medium">English, Hindi, or Telugu</span>.
          Describe a mood, a theme, or a specific title.
        </p>
      </motion.div>

      {/* ── Search box ──────────────────────────────────────────────────── */}
      <form onSubmit={handleSearch} className="mb-4">
        <motion.div
          className="relative flex items-center gap-3 max-w-3xl mx-auto"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.5 }}
        >
          <div className="relative flex-1">
            <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
            <input
              id="search-input"
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. dark psychological thriller, feel-good Bollywood, Akira Kurosawa style…"
              className="w-full glow-input text-white placeholder-slate-600 rounded-2xl pl-11 pr-4 py-4 text-sm outline-none font-body"
            />
          </div>
          <motion.button
            whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}
            id="search-btn"
            type="submit"
            disabled={loading || !query.trim()}
            className="flex items-center gap-2 bg-gradient-to-r from-accent to-accent-light hover:from-accent-light hover:to-accent disabled:opacity-50 disabled:cursor-not-allowed text-midnight-950 font-display font-bold rounded-2xl px-6 py-4 text-sm transition-all shadow-lg shadow-accent/20 whitespace-nowrap"
          >
            {loading ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />}
            <span className="hidden sm:inline">Search</span>
          </motion.button>
        </motion.div>
      </form>

      {/* ── Filter toggle ──────────────────────────────────────────────── */}
      <div className="flex justify-center mb-6">
        <motion.button
          whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}
          id="filter-toggle"
          onClick={() => setShowFilt((v) => !v)}
          className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm text-slate-400 hover:text-white hover:bg-white/5 border border-white/8 hover:border-white/15 transition-all font-body"
        >
          <SlidersHorizontal size={14} />
          Filters
          {activeFilters > 0 && (
            <span className="bg-accent text-midnight-950 text-[10px] font-bold rounded-full w-4 h-4 flex items-center justify-center">
              {activeFilters}
            </span>
          )}
          {showFilters ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </motion.button>
      </div>

      {/* ── Filter panel ─────────────────────────────────────────────── */}
      <AnimatePresence>
        {showFilters && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="max-w-3xl mx-auto mb-8 glass-card rounded-2xl p-6 space-y-5">
              {/* Media type */}
              <div>
                <label className="block text-[11px] font-semibold text-slate-400 uppercase tracking-[0.15em] mb-2.5 font-body">Media Type</label>
                <div className="flex gap-2">
                  {MEDIA_TYPES.map((mt) => (
                    <FilterPill key={mt.value} active={mediaType === mt.value} onClick={() => setMediaType(mt.value)}>
                      <span className="flex items-center gap-1.5">{mt.icon} {mt.label}</span>
                    </FilterPill>
                  ))}
                </div>
              </div>
              {/* Language */}
              <div>
                <label className="block text-[11px] font-semibold text-slate-400 uppercase tracking-[0.15em] mb-2.5 font-body">
                  <Globe size={12} className="inline mr-1.5" /> Language
                </label>
                <div className="flex flex-wrap gap-2">
                  {LANGUAGES.map((l) => (
                    <FilterPill key={l.value} active={language === l.value} onClick={() => setLanguage(l.value)}>
                      {l.label}
                    </FilterPill>
                  ))}
                </div>
              </div>
              {/* Genre */}
              <div>
                <label className="block text-[11px] font-semibold text-slate-400 uppercase tracking-[0.15em] mb-2.5 font-body">Genre</label>
                <div className="flex flex-wrap gap-2">
                  {GENRES.map((g) => (
                    <FilterPill key={g} active={genre === g} onClick={() => setGenre((v) => (v === g ? '' : g))}>
                      {g}
                    </FilterPill>
                  ))}
                </div>
              </div>
              {/* Mood */}
              <div>
                <label className="block text-[11px] font-semibold text-slate-400 uppercase tracking-[0.15em] mb-2.5 font-body">Mood</label>
                <div className="flex flex-wrap gap-2">
                  {MOODS.map((m) => (
                    <FilterPill key={m} active={mood === m} onClick={() => setMood((v) => (v === m ? '' : m))}>
                      {m}
                    </FilterPill>
                  ))}
                </div>
              </div>
              {/* Min Rating */}
              <div>
                <label className="block text-[11px] font-semibold text-slate-400 uppercase tracking-[0.15em] mb-2.5 font-body">
                  Min Rating: <span className="text-accent">{minRating > 0 ? `${minRating}+` : 'Any'}</span>
                </label>
                <input
                  id="min-rating-slider"
                  type="range" min={0} max={9} step={0.5}
                  value={minRating}
                  onChange={(e) => setMinRating(parseFloat(e.target.value))}
                  className="w-full accent-accent"
                />
              </div>
              {/* Clear */}
              {activeFilters > 0 && (
                <button
                  onClick={() => { setMediaType('All'); setLanguage('all'); setGenre(''); setMood(''); setMinRating(0); }}
                  className="text-xs text-slate-500 hover:text-accent transition-colors font-body flex items-center gap-1"
                >
                  <X size={12} /> Clear all filters
                </button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── AI Explanation ──────────────────────────────────────────────── */}
      {explanation && !results.some(r => r.explanation) && (
        <motion.div
          className="max-w-3xl mx-auto mb-8 ai-box-wrapper"
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="ai-box">
            <div className="flex items-center gap-2 mb-3">
              <Sparkles size={14} className="text-accent" />
              <span className="text-accent text-xs font-semibold uppercase tracking-[0.15em] font-body">Gemini AI Analysis</span>
            </div>
            <div className="ai-markdown">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{explanation}</ReactMarkdown>
            </div>
          </div>
        </motion.div>
      )}

      {/* ── Error state ──────────────────────────────────────────────── */}
      {isError && (
        <div className="max-w-3xl mx-auto mb-8 flex items-center gap-3 glass-card rounded-xl px-4 py-3 text-cinema-crimson text-sm border-cinema-crimson/20 font-body">
          <AlertCircle size={16} />
          Failed to reach the backend. Make sure the API server is running on port 8005.
        </div>
      )}

      {/* ── Deep Analysis Panel ──────────────────────────────────────── */}
      {results.length > 0 && (
        <div className="max-w-7xl mx-auto mb-8 flex flex-col items-center">
          {!deepAnalysis && !isAnalyzing && (
            <motion.button
              whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }}
              onClick={handleDeepAnalyze}
              className="px-6 py-2.5 bg-accent/5 border border-accent/20 rounded-full text-accent text-sm font-medium hover:bg-accent/10 transition-all flex items-center gap-2 font-body"
            >
              <Sparkles size={16} /> Deep Analysis
            </motion.button>
          )}
          {isAnalyzing && (
            <div className="flex items-center gap-3 text-accent/80 text-sm py-2 font-body">
              <div className="w-4 h-4 rounded-full border-2 border-accent/20 border-t-accent animate-spin" />
              Movies and TV shows Recommendation Engine is analyzing your results via LangChain...
            </div>
          )}
          {deepAnalysis && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="w-full glass-card rounded-2xl p-6 sm:p-8 relative overflow-hidden mt-4 border-t-2 border-accent/40"
            >
              <div className="absolute top-0 left-1/4 w-1/2 h-32 bg-accent/5 blur-[100px] pointer-events-none" />
              <div className="flex items-center gap-2 mb-4">
                <span className="text-accent text-[10px] font-bold tracking-[0.2em] uppercase border border-accent/20 px-2.5 py-1 rounded font-body">
                  ✦ LangChain RAG Analysis
                </span>
              </div>
              <div className="text-slate-200 text-lg sm:text-xl leading-relaxed tracking-wide font-display mb-6 ai-markdown">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{deepAnalysis}</ReactMarkdown>
              </div>
              {deepSources.length > 0 && (
                <div className="border-t border-white/5 pt-4 mt-2">
                  <p className="text-[11px] text-slate-500 uppercase tracking-widest mb-2 font-medium font-body">Context sources</p>
                  <div className="flex flex-wrap gap-2">
                    {deepSources.map((src, i) => (
                      <span key={i} className="text-xs text-slate-400 bg-midnight-900 px-2.5 py-1 rounded-md border border-white/5 font-body">
                        {src}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </motion.div>
          )}
        </div>
      )}

      {/* ── Results grid ───────────────────────────────────────────────── */}
      {results.length > 0 && (
        <div>
          <p className="text-slate-500 text-xs mb-4 text-center font-body">{results.length} recommendations</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-5">
            {results.map((movie, index) => (
              <MovieCard
                key={movie.id}
                movie={movie}
                ratingState={ratingState}
                pending={pending}
                onRate={handleRate}
                index={index}
              />
            ))}
          </div>
        </div>
      )}

      {/* ── Loading skeleton ─────────────────────────────────────────── */}
      {loading && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-5">
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="glass-card rounded-2xl overflow-hidden">
              <div className="aspect-[2/3] shimmer bg-midnight-800" />
              <div className="p-4 space-y-3">
                <div className="h-3.5 shimmer bg-midnight-800 rounded w-3/4" />
                <div className="h-2.5 shimmer bg-midnight-800 rounded w-1/2" />
                <div className="h-2 shimmer bg-midnight-800 rounded" />
                <div className="h-2 shimmer bg-midnight-800 rounded w-5/6" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Empty state ──────────────────────────────────────────────── */}
      {!loading && hasSearched && !isError && results.length === 0 && (
        <motion.div className="text-center py-20" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <div className="text-6xl mb-4">🎬</div>
          <p className="text-slate-400 text-sm font-body">No results found. Try a different query or relax the filters.</p>
        </motion.div>
      )}

      {/* ── Initial state ──────────────────────────────────────────────── */}
      {!hasSearched && !loading && (
        <motion.div
          className="text-center py-20"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4 }}
        >
          <Film size={56} className="mx-auto mb-5 text-white/10 animate-float" />
          <p className="text-sm text-slate-500 font-body">Enter a query above to get AI-powered recommendations.</p>
          <div className="flex flex-wrap justify-center gap-2 mt-4">
            {[
              { label: 'psychological thriller', query: 'psychological thriller with an unreliable narrator' },
              { label: 'Bollywood family drama', query: 'feel-good Bollywood family drama' },
              { label: 'Telugu action', query: 'Telugu action movie with strong female lead' },
            ].map((s) => (
              <button
                key={s.label}
                onClick={() => setQuery(s.query)}
                className="text-xs text-slate-500 hover:text-accent border border-white/8 hover:border-accent/20 px-3 py-1.5 rounded-full transition-all font-body"
              >
                {s.label}
              </button>
            ))}
          </div>
        </motion.div>
      )}
    </div>
  );
};

export default Home;
