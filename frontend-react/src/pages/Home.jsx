import React, { useState, useCallback } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Search, CornerDownLeft, Star, ChevronDown, ChevronUp, AlertCircle, Heart, ThumbsDown, BookmarkPlus } from 'lucide-react';
import { useAppContext } from '../context/AppContext';

const API_BASE = import.meta.env.VITE_BACKEND_URL || 'http://127.0.0.1:8000';

// ── Rating state constants ────────────────────────────────────────────────────
const RATING = { NONE: null, LIKE: 'like', DISLIKE: 'dislike', WATCHLIST: 'watchlist' };

const Home = () => {
    const { userId, language } = useAppContext();
    const [query, setQuery] = useState('');
    const [mediaType] = useState('All');
    const [minRating] = useState(6.0);
    const [genre] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const [recommendations, setRecommendations] = useState([]);
    const [aiExplanation, setAiExplanation] = useState('');
    const [hasSearched, setHasSearched] = useState(false);
    const [isError, setIsError] = useState(false);
    const [expandedId, setExpandedId] = useState(null);

    // Optimistic rating state: { [tmdbId]: 'like' | 'dislike' | 'watchlist' | null }
    const [ratingState, setRatingState] = useState({});
    // Tracks IDs currently in-flight so we disable the button to avoid double-clicks
    const [pendingIds, setPendingIds] = useState(new Set());

    const handleSearch = async (e) => {
        e?.preventDefault();
        if (!query.trim()) return;

        setIsLoading(true);
        setHasSearched(true);
        setIsError(false);
        setRecommendations([]);
        setAiExplanation('');
        setRatingState({});

        try {
            const { data } = await axios.post(`${API_BASE}/api/recommend`, {
                query,
                user_id: userId,
                media_type: mediaType,
                min_rating: minRating,
                language_pref: language,
                genre,
            });

            setRecommendations(data.movies || []);
            setAiExplanation(data.explanation || '');
            if (data.movies && data.movies.length === 0) {
                toast('No matches found. Try adjusting your search!', { icon: '🤔' });
            }
            if (data.cached) {
                console.info('[cache] Served from Redis cache.');
            }
        } catch (error) {
            console.error('Search error:', error);
            if (error.response?.status === 429) {
                toast.error(error.response?.data?.detail || 'Too many requests. Please wait a moment.', { duration: 5000 });
            } else {
                setIsError(true);
                toast.error('Failed to get recommendations. Please try again.');
            }
        } finally {
            setIsLoading(false);
        }
    };

    /**
     * Optimistic rating handler.
     * 1. Immediately update local UI state (button highlights/grays out).
     * 2. Fire the API in the background.
     * 3. On failure: revert state and show error toast.
     */
    const handleRate = useCallback(async (tmdbId, type, title) => {
        if (pendingIds.has(tmdbId)) return; // debounce rapid taps

        // Optimistic update
        setRatingState(prev => ({ ...prev, [tmdbId]: type }));
        setPendingIds(prev => new Set(prev).add(tmdbId));

        try {
            await axios.post(
                `${API_BASE}/api/rate`,
                { tmdb_id: tmdbId, interaction_type: type },
                { headers: { Authorization: `Bearer ${localStorage.getItem('jwt_token') || ''}` } }
            );
            if (type === RATING.LIKE) {
                toast.success(`❤️ Loved ${title}!`);
            } else {
                toast(`👎 Passed on ${title}`);
            }
        } catch (error) {
            // Revert on failure
            setRatingState(prev => ({ ...prev, [tmdbId]: null }));
            if (error.response?.status === 401) {
                toast.error('Sign in to save your preferences.');
            } else {
                toast.error('Failed to save rating. Please try again.');
            }
        } finally {
            setPendingIds(prev => {
                const next = new Set(prev);
                next.delete(tmdbId);
                return next;
            });
        }
    }, [pendingIds]);

    const addToWatchlist = useCallback(async (tmdbId, title) => {
        if (pendingIds.has(`wl-${tmdbId}`)) return;

        // Optimistic update
        setRatingState(prev => ({ ...prev, [tmdbId]: RATING.WATCHLIST }));
        setPendingIds(prev => new Set(prev).add(`wl-${tmdbId}`));

        try {
            await axios.post(`${API_BASE}/api/watchlist`, {
                user_id: userId,
                tmdb_id: tmdbId,
                action: 'add',
            });
            toast.success(`📋 Added ${title} to Watchlist!`);
        } catch (error) {
            setRatingState(prev => ({ ...prev, [tmdbId]: null }));
            toast.error('Failed to add to watchlist.');
        } finally {
            setPendingIds(prev => {
                const next = new Set(prev);
                next.delete(`wl-${tmdbId}`);
                return next;
            });
        }
    }, [pendingIds, userId]);

    return (
        <div className="w-full flex-1 flex flex-col items-center">
            {/* Hero Search */}
            <div className="w-full flex justify-start mb-8 mt-12 px-4 sm:px-8">
                <h1 className="text-slate-400 tracking-tighter text-[32px] sm:text-[48px] lg:text-[60px] font-black leading-none uppercase">
                    MOVIE &amp; TV SHOWS RECOMMENDING ENGINE.
                </h1>
            </div>
            <div className="w-full max-w-3xl px-4 sm:px-8 flex flex-col items-start gap-4">
                <form onSubmit={handleSearch} className="w-full">
                    <div className="flex w-full items-stretch rounded-2xl h-14 sm:h-16 border border-slate-800 bg-[#151a2e] overflow-hidden shadow-inner focus-within:border-blue-500/50 transition-colors">
                        <div className="text-slate-500 flex items-center justify-center pl-4 sm:pl-6">
                            <Search size={20} />
                        </div>
                        <input
                            type="text"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            className="flex-1 bg-transparent border-none text-white focus:ring-0 px-4 sm:px-6 text-base sm:text-xl font-light outline-none"
                            placeholder="Search movies, directors, or genres..."
                        />
                        <button
                            type="submit"
                            disabled={isLoading}
                            className="bg-slate-800 text-slate-400 hover:text-white transition-colors rounded-lg px-3 sm:px-4 py-2 m-2 gap-2 text-sm font-medium border border-slate-700 flex items-center disabled:opacity-50"
                        >
                            Return <CornerDownLeft size={16} />
                        </button>
                    </div>
                </form>
            </div>

            {/* ── AI Analysis Box ─────────────────────────────────────────────── */}
            {aiExplanation && !isLoading && !isError && (
                <div className="ai-box-wrapper w-full max-w-4xl px-4 sm:px-8 mt-8">
                    <div className="ai-box border-l-2 border-blue-500/60 bg-slate-900/70 p-4 sm:p-6 rounded-r-xl shadow-lg backdrop-blur-sm">
                        <p className="text-blue-400 font-bold text-xs uppercase tracking-widest mb-2 flex items-center gap-2">
                            <span>⚡</span> AI Recommendation Analysis
                        </p>
                        {/* ReactMarkdown renders Gemini's **bold** markers as proper <strong> elements */}
                        <div className="ai-markdown text-slate-300 text-sm sm:text-base leading-relaxed font-mono">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {aiExplanation}
                            </ReactMarkdown>
                        </div>
                    </div>
                </div>
            )}

            {/* ── Results Bento Grid ──────────────────────────────────────────── */}
            <div className="w-full max-w-6xl px-4 sm:px-8 mt-12 pb-12">
                {isLoading ? (
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
                        {[...Array(10)].map((_, i) => (
                            <div key={i} className="aspect-[2/3] rounded-xl bg-slate-800/50 animate-pulse border border-slate-700/50"></div>
                        ))}
                    </div>
                ) : isError ? (
                    <div className="flex flex-col items-center justify-center p-12 border border-dashed border-slate-700 rounded-2xl bg-slate-900/30">
                        <AlertCircle size={48} className="text-red-500 mb-4" />
                        <h3 className="text-xl font-bold text-white mb-2">System Error</h3>
                        <p className="text-slate-400">Failed to connect to the recommendation engine. Please try again.</p>
                    </div>
                ) : hasSearched && recommendations.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-16 px-4 bg-slate-900/30 rounded-2xl border border-dashed border-slate-700">
                        <div className="relative size-32 mb-2">
                            <div className="absolute inset-0 bg-blue-500/10 rounded-full blur-2xl"></div>
                            <div className="relative bg-slate-800 size-full rounded-full flex items-center justify-center shadow-lg border border-slate-700">
                                <Search className="text-6xl text-blue-500" size={48} />
                            </div>
                        </div>
                        <h3 className="text-white text-2xl font-bold mt-4">No movies found in this universe</h3>
                        <p className="text-slate-400 text-base mt-2">Try adjusting your filters or search query.</p>
                    </div>
                ) : (
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
                        {recommendations.map((movie) => {
                            const poster = movie.poster_path || 'https://via.placeholder.com/500x750/1e293b/94a3b8?text=No+Poster';
                            const isExpanded = expandedId === movie.id;
                            const currentRating = ratingState[movie.id] ?? null;
                            const isPending = pendingIds.has(movie.id) || pendingIds.has(`wl-${movie.id}`);

                            const isLiked = currentRating === RATING.LIKE;
                            const isDisliked = currentRating === RATING.DISLIKE;
                            const isWatchlisted = currentRating === RATING.WATCHLIST;

                            return (
                                <div key={movie.id} className="relative group rounded-xl border border-slate-800 overflow-hidden bg-[#1a1f35] flex flex-col h-full transform transition-transform hover:scale-[1.02] hover:z-10 hover:shadow-2xl">
                                    {/* Poster Area */}
                                    <div className="relative aspect-[2/3] overflow-hidden">
                                        <img src={poster} alt={movie.title} className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110" />

                                        {/* Hover Overlay with Optimistic Buttons */}
                                        <div className="absolute inset-0 bg-black/60 backdrop-blur-sm opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex flex-col items-center justify-center gap-3 p-4">
                                            {/* Love it */}
                                            <button
                                                onClick={() => handleRate(movie.id, RATING.LIKE, movie.title)}
                                                disabled={isPending}
                                                className={`w-full py-2 font-bold rounded-lg transition-all duration-200 flex items-center justify-center gap-2 border
                                                    ${isLiked
                                                        ? 'bg-blue-500 border-blue-400 text-white shadow-lg shadow-blue-500/40 scale-[1.02]'
                                                        : 'bg-blue-600/80 border-blue-600 hover:bg-blue-500 text-white'
                                                    } disabled:opacity-60 disabled:cursor-not-allowed`}
                                            >
                                                <Heart size={14} fill={isLiked ? 'currentColor' : 'none'} />
                                                {isLiked ? 'Loved!' : 'Love it'}
                                            </button>

                                            {/* Watchlist */}
                                            <button
                                                onClick={() => addToWatchlist(movie.id, movie.title)}
                                                disabled={isPending}
                                                className={`w-full py-2 font-bold rounded-lg transition-all duration-200 flex items-center justify-center gap-2 border
                                                    ${isWatchlisted
                                                        ? 'bg-emerald-600 border-emerald-500 text-white shadow-lg shadow-emerald-500/30 scale-[1.02]'
                                                        : 'bg-slate-700/80 border-slate-600 hover:bg-slate-600 text-white'
                                                    } disabled:opacity-60 disabled:cursor-not-allowed`}
                                            >
                                                <BookmarkPlus size={14} />
                                                {isWatchlisted ? 'Added!' : 'Watchlist'}
                                            </button>

                                            {/* Pass */}
                                            <button
                                                onClick={() => handleRate(movie.id, RATING.DISLIKE, movie.title)}
                                                disabled={isPending}
                                                className={`w-full py-2 font-bold rounded-lg transition-all duration-200 flex items-center justify-center gap-2 border
                                                    ${isDisliked
                                                        ? 'bg-slate-600 border-slate-400 text-slate-300 opacity-70 scale-[0.98]'
                                                        : 'bg-slate-800/80 border-slate-600 hover:bg-slate-700 text-white'
                                                    } disabled:opacity-60 disabled:cursor-not-allowed`}
                                            >
                                                <ThumbsDown size={14} />
                                                {isDisliked ? 'Passed' : 'Pass'}
                                            </button>
                                        </div>

                                        {/* Meta badges */}
                                        <div className="absolute top-2 right-2 bg-black/80 backdrop-blur px-2 py-1 rounded text-xs font-bold text-yellow-500 flex items-center gap-1 border border-yellow-500/30">
                                            <Star size={12} fill="currentColor" /> {movie.rating?.toFixed(1) || 'N/A'}
                                        </div>
                                        {movie.match_score && (
                                            <div className="absolute top-2 left-2 bg-blue-600/90 backdrop-blur px-2 py-1 rounded text-xs font-bold text-white shadow-lg">
                                                {movie.match_score}% Match
                                            </div>
                                        )}
                                    </div>

                                    {/* Info Area */}
                                    <div className="p-3 flex flex-col flex-1 bg-gradient-to-t from-slate-900 to-slate-900/90 z-10">
                                        <h3 className="text-sm font-bold text-slate-100 line-clamp-1" title={movie.title}>{movie.title}</h3>

                                        <button
                                            onClick={() => setExpandedId(isExpanded ? null : movie.id)}
                                            className="text-xs text-slate-400 hover:text-white flex items-center gap-1 mt-2 focus:outline-none"
                                        >
                                            {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                                            {isExpanded ? 'Hide' : 'Synopsis'}
                                        </button>

                                        <div className={`text-xs text-slate-400 mt-2 transition-all duration-300 overflow-hidden ${isExpanded ? 'max-h-48' : 'max-h-0'}`}>
                                            {movie.overview || 'No synopsis available.'}
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
};

export default Home;
