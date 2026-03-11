import React, { useState, useCallback } from 'react';
import toast from 'react-hot-toast';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Search, Star, Heart, ThumbsDown, BookmarkPlus,
  SlidersHorizontal, ChevronDown, ChevronUp, Loader2,
  Tv, Film, Globe, Layers, Sparkles, AlertCircle,
} from 'lucide-react';
import { getRecommendations, rateTitle } from '../services/api';
import { useAppContext } from '../context/AppContext';

// ── Filter options ─────────────────────────────────────────────────────────────
const GENRES = ['Action', 'Comedy', 'Drama', 'Horror', 'Romance', 'Sci-Fi', 'Thriller', 'Animation', 'Documentary'];
const MOODS  = ['Feel-good', 'Dark & gritty', 'Mind-bending', 'Emotional', 'Lighthearted', 'Suspenseful'];
const MEDIA_TYPES = [
  { label: 'All', value: 'All', icon: <Layers size={13} /> },
  { label: 'Movies', value: 'movie', icon: <Film size={13} /> },
  { label: 'TV Shows', value: 'tv', icon: <Tv size={13} /> },
];
const LANGUAGES = [
  { label: 'All', value: 'all' },
  { label: 'English', value: 'en' },
  { label: 'Hindi', value: 'hi' },
  { label: 'Telugu', value: 'te' },
];
const RATING_NONE = null;
const RATING_LIKE = 'like';
const RATING_DISLIKE = 'dislike';

// ── Helper: star display ───────────────────────────────────────────────────────
const Stars = ({ rating }) => (
  <span className="flex items-center gap-1 text-amber-400 text-xs font-semibold">
    <Star size={11} fill="currentColor" />
    {rating?.toFixed(1) ?? '—'}
  </span>
);

// ── Provider badge ─────────────────────────────────────────────────────────────
const ProviderBadge = ({ name, type }) => {
  const colors = {
    flatrate: 'bg-blue-600/20 text-blue-300 border-blue-700/40',
    free:     'bg-emerald-600/20 text-emerald-300 border-emerald-700/40',
    ads:      'bg-amber-600/20 text-amber-300 border-amber-700/40',
    rent:     'bg-purple-600/20 text-purple-300 border-purple-700/40',
    buy:      'bg-rose-600/20 text-rose-300 border-rose-700/40',
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium border ${colors[type] || 'bg-slate-700/40 text-slate-400 border-slate-600/40'}`}>
      {name}
    </span>
  );
};

// ── Card ───────────────────────────────────────────────────────────────────────
const MovieCard = ({ movie, ratingState, pending, onRate }) => {
  const [expanded, setExpanded] = useState(false);
  const currentRating = ratingState[movie.id] ?? null;
  const isPending = pending.has(movie.id);

  const providers = movie.providers || [];
  const streamProviders = providers.filter((p) => p.type === 'flatrate');
  const otherProviders = providers.filter((p) => p.type !== 'flatrate').slice(0, 3);

  return (
    <div className="group bg-slate-900/60 border border-slate-800 hover:border-slate-700 rounded-2xl overflow-hidden transition-all duration-300 hover:shadow-xl hover:shadow-blue-900/10 flex flex-col">
      {/* Poster */}
      <div className="relative aspect-[2/3] overflow-hidden bg-slate-800">
        {movie.poster_path ? (
          <img
            src={movie.poster_path}
            alt={movie.title}
            loading="lazy"
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Film size={40} className="text-slate-600" />
          </div>
        )}
        {/* Match score badge */}
        <div className="absolute top-2 right-2 bg-blue-600/90 backdrop-blur text-white text-[10px] font-bold px-2 py-1 rounded-full shadow">
          {movie.match_score}% match
        </div>
        {/* Media type badge */}
        <div className="absolute top-2 left-2 bg-slate-900/80 backdrop-blur text-slate-300 text-[10px] font-medium px-2 py-1 rounded-full flex items-center gap-1">
          {movie.media_type === 'tv' ? <Tv size={9} /> : <Film size={9} />}
          {movie.media_type === 'tv' ? 'TV' : 'Movie'}
        </div>
      </div>

      {/* Body */}
      <div className="p-4 flex flex-col flex-1 gap-3">
        <div>
          <h3 className="text-white font-semibold text-sm leading-tight line-clamp-2">{movie.title}</h3>
          <div className="flex items-center gap-2 mt-1.5 text-slate-500 text-[11px]">
            <Stars rating={movie.rating} />
            {movie.release_date && <span>{movie.release_date.slice(0, 4)}</span>}
          </div>
        </div>

        {/* Overview toggle */}
        <div>
          <p className={`text-slate-400 text-xs leading-relaxed ${expanded ? '' : 'line-clamp-3'}`}>
            {movie.overview || 'No overview available.'}
          </p>
          {movie.overview && movie.overview.length > 120 && (
            <button
              onClick={() => setExpanded((v) => !v)}
              className="text-blue-400 text-[11px] mt-1 hover:text-blue-300 flex items-center gap-0.5 transition-colors"
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

        {/* Action buttons */}
        <div className="flex gap-2 mt-auto pt-1">
          <button
            id={`like-${movie.id}`}
            disabled={isPending}
            onClick={() => onRate(movie.id, RATING_LIKE, movie.title)}
            className={`flex-1 flex items-center justify-center gap-1 py-2 rounded-xl text-xs font-semibold border transition-all ${
              currentRating === RATING_LIKE
                ? 'bg-rose-600 border-rose-500 text-white shadow-lg shadow-rose-600/20'
                : 'border-slate-700 text-slate-400 hover:border-rose-600/50 hover:text-rose-400 hover:bg-rose-600/10'
            } ${isPending ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            <Heart size={12} fill={currentRating === RATING_LIKE ? 'currentColor' : 'none'} />
            Love it
          </button>
          <button
            id={`dislike-${movie.id}`}
            disabled={isPending}
            onClick={() => onRate(movie.id, RATING_DISLIKE, movie.title)}
            className={`flex-1 flex items-center justify-center gap-1 py-2 rounded-xl text-xs font-semibold border transition-all ${
              currentRating === RATING_DISLIKE
                ? 'bg-slate-600 border-slate-500 text-white'
                : 'border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-300 hover:bg-slate-800'
            } ${isPending ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            <ThumbsDown size={12} />
            Pass
          </button>
          <button
            id={`watchlist-${movie.id}`}
            disabled={isPending}
            onClick={() => onRate(movie.id, 'watchlist', movie.title)}
            className={`px-3 py-2 rounded-xl text-xs font-semibold border transition-all ${
              currentRating === 'watchlist'
                ? 'bg-blue-600 border-blue-500 text-white shadow-lg shadow-blue-600/20'
                : 'border-slate-700 text-slate-400 hover:border-blue-600/50 hover:text-blue-400 hover:bg-blue-600/10'
            } ${isPending ? 'opacity-50 cursor-not-allowed' : ''}`}
            title="Save to Watchlist"
          >
            <BookmarkPlus size={12} />
          </button>
        </div>
      </div>
    </div>
  );
};

// ── Home ───────────────────────────────────────────────────────────────────────
const Home = () => {
  const { userId } = useAppContext();

  // Search state
  const [query, setQuery]         = useState('');
  const [loading, setLoading]     = useState(false);
  const [results, setResults]     = useState([]);
  const [explanation, setExpl]    = useState('');
  const [hasSearched, setSearched]= useState(false);
  const [isError, setError]       = useState(false);

  // Filter state
  const [showFilters, setShowFilt]= useState(false);
  const [mediaType, setMediaType] = useState('All');
  const [language, setLanguage]   = useState('all');
  const [genre, setGenre]         = useState('');
  const [mood, setMood]           = useState('');
  const [minRating, setMinRating] = useState(0);

  // Interaction state
  const [ratingState, setRatingState] = useState({});
  const [pending, setPending]         = useState(new Set());

  const handleSearch = async (e) => {
    e?.preventDefault();
    const finalQuery = [query.trim(), mood].filter(Boolean).join(' — ');
    if (!finalQuery) return;

    setLoading(true);
    setSearched(true);
    setError(false);
    setResults([]);
    setExpl('');
    setRatingState({});

    try {
      const { data } = await getRecommendations({
        query: finalQuery,
        user_id: userId,
        media_type: mediaType,
        min_rating: minRating,
        genre: genre || null,
        language_pref: language,
      });
      setResults(data.movies || []);
      setExpl(data.explanation || '');
      if (!data.movies?.length) toast('No matches. Try a different search!', { icon: '🤔' });
      if (data.cached) console.info('[cache] Redis hit');
    } catch (err) {
      setError(true);
      toast.error(err.response?.data?.detail || 'Could not fetch recommendations.');
    } finally {
      setLoading(false);
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
      toast.error('Could not save rating. Please try again.');
    } finally {
      setPending((s) => { const n = new Set(s); n.delete(tmdbId); return n; });
    }
  }, [ratingState]);

  // Active filter count for badge
  const activeFilters = [
    mediaType !== 'All', language !== 'all', !!genre, !!mood, minRating > 0
  ].filter(Boolean).length;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8">

      {/* ── Hero ────────────────────────────────────────────────────────────── */}
      <div className="text-center mb-10">
        <div className="inline-flex items-center gap-2 bg-blue-600/10 border border-blue-600/20 rounded-full px-4 py-1.5 text-blue-400 text-xs font-medium mb-4">
          <Sparkles size={12} /> Powered by Gemini AI + pgvector
        </div>
        <h1 className="text-3xl sm:text-4xl font-bold text-white mb-3 tracking-tight">
          What do you want to watch?
        </h1>
        <p className="text-slate-400 text-sm sm:text-base max-w-xl mx-auto">
          Search in <span className="text-white font-medium">English, Hindi, or Telugu</span>.
          Describe a mood, a theme, or a specific title.
        </p>
      </div>

      {/* ── Search box ──────────────────────────────────────────────────────── */}
      <form onSubmit={handleSearch} className="mb-3">
        <div className="relative flex items-center gap-2 max-w-3xl mx-auto">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
            <input
              id="search-input"
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. dark psychological thriller, feel-good Bollywood, Akira Kurosawa style…"
              className="w-full bg-slate-900 border border-slate-700 focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30 text-white placeholder-slate-500 rounded-2xl pl-10 pr-4 py-3.5 text-sm outline-none transition-all"
            />
          </div>
          <button
            id="search-btn"
            type="submit"
            disabled={loading || !query.trim()}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold rounded-2xl px-5 py-3.5 text-sm transition-all shadow-lg shadow-blue-600/20 whitespace-nowrap"
          >
            {loading ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />}
            <span className="hidden sm:inline">Search</span>
          </button>
        </div>
      </form>

      {/* ── Filter toggle ────────────────────────────────────────────────────── */}
      <div className="flex justify-center mb-6">
        <button
          id="filter-toggle"
          onClick={() => setShowFilt((v) => !v)}
          className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm text-slate-400 hover:text-white hover:bg-slate-800 border border-slate-800 hover:border-slate-700 transition-all"
        >
          <SlidersHorizontal size={14} />
          Filters
          {activeFilters > 0 && (
            <span className="bg-blue-600 text-white text-[10px] font-bold rounded-full w-4 h-4 flex items-center justify-center">
              {activeFilters}
            </span>
          )}
          {showFilters ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>
      </div>

      {/* ── Filter panel ─────────────────────────────────────────────────────── */}
      {showFilters && (
        <div className="max-w-3xl mx-auto mb-8 bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-5 animate-in fade-in">
          {/* Media type */}
          <div>
            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-2">
              Media Type
            </label>
            <div className="flex gap-2">
              {MEDIA_TYPES.map((mt) => (
                <button
                  key={mt.value}
                  id={`media-${mt.value}`}
                  onClick={() => setMediaType(mt.value)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium border transition-all ${
                    mediaType === mt.value
                      ? 'bg-blue-600 border-blue-500 text-white'
                      : 'border-slate-700 text-slate-400 hover:border-slate-600 hover:text-white'
                  }`}
                >
                  {mt.icon} {mt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Language */}
          <div>
            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-2">
              <Globe size={12} className="inline mr-1" /> Language
            </label>
            <div className="flex flex-wrap gap-2">
              {LANGUAGES.map((l) => (
                <button
                  key={l.value}
                  id={`lang-${l.value}`}
                  onClick={() => setLanguage(l.value)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-medium border transition-all ${
                    language === l.value
                      ? 'bg-blue-600 border-blue-500 text-white'
                      : 'border-slate-700 text-slate-400 hover:border-slate-600 hover:text-white'
                  }`}
                >
                  {l.label}
                </button>
              ))}
            </div>
          </div>

          {/* Genre */}
          <div>
            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-2">Genre</label>
            <div className="flex flex-wrap gap-2">
              {GENRES.map((g) => (
                <button
                  key={g}
                  id={`genre-${g}`}
                  onClick={() => setGenre((v) => (v === g ? '' : g))}
                  className={`px-3 py-1.5 rounded-xl text-xs font-medium border transition-all ${
                    genre === g
                      ? 'bg-purple-600 border-purple-500 text-white'
                      : 'border-slate-700 text-slate-400 hover:border-slate-600 hover:text-white'
                  }`}
                >
                  {g}
                </button>
              ))}
            </div>
          </div>

          {/* Mood */}
          <div>
            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-2">Mood</label>
            <div className="flex flex-wrap gap-2">
              {MOODS.map((m) => (
                <button
                  key={m}
                  id={`mood-${m.replace(/\s+/g, '-')}`}
                  onClick={() => setMood((v) => (v === m ? '' : m))}
                  className={`px-3 py-1.5 rounded-xl text-xs font-medium border transition-all ${
                    mood === m
                      ? 'bg-amber-600 border-amber-500 text-white'
                      : 'border-slate-700 text-slate-400 hover:border-slate-600 hover:text-white'
                  }`}
                >
                  {m}
                </button>
              ))}
            </div>
          </div>

          {/* Min Rating */}
          <div>
            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-2">
              Min Rating: <span className="text-amber-400">{minRating > 0 ? `${minRating}+` : 'Any'}</span>
            </label>
            <input
              id="min-rating-slider"
              type="range"
              min={0}
              max={9}
              step={0.5}
              value={minRating}
              onChange={(e) => setMinRating(parseFloat(e.target.value))}
              className="w-full accent-blue-500"
            />
            <div className="flex justify-between text-[10px] text-slate-600 mt-1">
              <span>Any</span><span>5</span><span>7</span><span>9</span>
            </div>
          </div>

          {/* Clear filters */}
          {activeFilters > 0 && (
            <button
              onClick={() => { setMediaType('All'); setLanguage('all'); setGenre(''); setMood(''); setMinRating(0); }}
              className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
            >
              ✕ Clear all filters
            </button>
          )}
        </div>
      )}

      {/* ── AI Explanation ──────────────────────────────────────────────────── */}
      {explanation && (
        <div className="max-w-3xl mx-auto mb-8 ai-box-wrapper">
          <div className="ai-box">
            <div className="flex items-center gap-2 mb-3">
              <Sparkles size={14} className="text-blue-400" />
              <span className="text-blue-400 text-xs font-semibold uppercase tracking-wider">Gemini AI Analysis</span>
            </div>
            <div className="ai-markdown">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{explanation}</ReactMarkdown>
            </div>
          </div>
        </div>
      )}

      {/* ── Error state ────────────────────────────────────────────────────── */}
      {isError && (
        <div className="max-w-3xl mx-auto mb-8 flex items-center gap-3 bg-red-950/40 border border-red-800/40 rounded-xl px-4 py-3 text-red-400 text-sm">
          <AlertCircle size={16} />
          Failed to reach the backend. Make sure the API server is running on port 8000.
        </div>
      )}

      {/* ── Results grid ───────────────────────────────────────────────────── */}
      {results.length > 0 && (
        <div>
          <p className="text-slate-500 text-xs mb-4 text-center">{results.length} recommendations</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-4">
            {results.map((movie) => (
              <MovieCard
                key={movie.id}
                movie={movie}
                ratingState={ratingState}
                pending={pending}
                onRate={handleRate}
              />
            ))}
          </div>
        </div>
      )}

      {/* ── Loading skeleton ────────────────────────────────────────────────── */}
      {loading && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden animate-pulse">
              <div className="aspect-[2/3] bg-slate-800" />
              <div className="p-4 space-y-2">
                <div className="h-3 bg-slate-800 rounded w-3/4" />
                <div className="h-2.5 bg-slate-800 rounded w-1/2" />
                <div className="h-2 bg-slate-800 rounded" />
                <div className="h-2 bg-slate-800 rounded w-5/6" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Empty state ──────────────────────────────────────────────────────── */}
      {!loading && hasSearched && !isError && results.length === 0 && (
        <div className="text-center py-20">
          <div className="text-5xl mb-4">🎬</div>
          <p className="text-slate-400 text-sm">No results found. Try a different query or relax the filters.</p>
        </div>
      )}

      {/* ── Initial state ────────────────────────────────────────────────────── */}
      {!hasSearched && !loading && (
        <div className="text-center py-20 text-slate-600">
          <Film size={48} className="mx-auto mb-4 opacity-30" />
          <p className="text-sm">Enter a query above to get AI-powered recommendations.</p>
          <p className="text-xs mt-1 text-slate-700">
            Try: <span className="text-slate-500 cursor-pointer hover:text-slate-400" onClick={() => setQuery('psychological thriller with an unreliable narrator')}>psychological thriller</span>
            {' · '}
            <span className="text-slate-500 cursor-pointer hover:text-slate-400" onClick={() => setQuery('feel-good Bollywood family drama')}>Bollywood family drama</span>
            {' · '}
            <span className="text-slate-500 cursor-pointer hover:text-slate-400" onClick={() => setQuery('Telugu action movie with strong female lead')}>Telugu action</span>
          </p>
        </div>
      )}
    </div>
  );
};

export default Home;
