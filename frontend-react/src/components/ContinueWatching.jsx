import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { motion, AnimatePresence } from 'framer-motion';
import { Play } from 'lucide-react';

export default function ContinueWatching() {
  const { user } = useAuth();
  const [activeMedia, setActiveMedia] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) return;
    const fetchProgress = async () => {
      try {
        const userId = user.username || user.userId || user.user_id;
        const response = await fetch(`/api/progress/${userId}`);
        if (response.ok) {
          const data = await response.json();
          setActiveMedia(data);
        }
      } catch (error) {
        console.error("Failed to fetch progress", error);
      } finally {
        setLoading(false);
      }
    };
    
    fetchProgress();
    
    // Listen for custom event to trigger re-fetch
    window.addEventListener('progress:updated', fetchProgress);
    return () => window.removeEventListener('progress:updated', fetchProgress);
  }, [user]);

  if (loading || activeMedia.length === 0) return null;

  return (
    <motion.div 
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, height: 0 }}
      className="mb-8 w-full max-w-7xl mx-auto px-4 sm:px-6"
    >
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-display font-bold text-white flex items-center gap-2">
          <span className="w-1.5 h-6 bg-accent rounded-full inline-block"></span>
          Continue Watching
        </h2>
      </div>
      
      <div className="flex gap-4 overflow-x-auto pb-4 scrollbar-thin scrollbar-thumb-white/10" style={{ scrollbarWidth: 'thin' }}>
        {activeMedia.map((movie) => (
          <motion.div 
            key={movie.tmdb_id} 
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            whileHover={{ y: -5 }}
            className="w-[200px] flex-shrink-0 relative group cursor-pointer"
          >
            <div className="relative rounded-xl overflow-hidden shadow-lg border border-white/10 aspect-[16/9]">
              <img 
                src={movie.poster_path || '/placeholder.png'} 
                alt={movie.title} 
                className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700 ease-out"
                loading="lazy"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent opacity-80 group-hover:opacity-90 transition-opacity" />
              
              {/* Play Button Overlay */}
              <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                <div className="w-12 h-12 rounded-full bg-accent/90 flex items-center justify-center backdrop-blur-md shadow-[0_0_15px_rgba(245,158,11,0.5)] transition-transform group-hover:scale-110">
                  <Play size={20} className="text-midnight-950 ml-1" fill="currentColor" />
                </div>
              </div>

              {/* Title overlay */}
              <div className="absolute bottom-3 left-3 right-3">
                <p className="text-white font-medium text-sm truncate font-body drop-shadow-md">
                  {movie.title}
                </p>
              </div>
            </div>
            
            {/* Progress Bar (sleek design) */}
            <div className="mt-3 flex items-center gap-3 px-1">
              <div className="flex-1 bg-midnight-800 rounded-full h-1.5 overflow-hidden">
                <motion.div 
                  initial={{ width: 0 }}
                  animate={{ width: `${movie.progress_percent}%` }}
                  transition={{ duration: 1, ease: "easeOut" }}
                  className="bg-gradient-to-r from-accent to-cinema-neon h-full rounded-full" 
                />
              </div>
              <span className="text-[10px] text-slate-400 font-body shrink-0 font-medium w-8">
                {Math.round(movie.progress_percent)}%
              </span>
            </div>
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}
