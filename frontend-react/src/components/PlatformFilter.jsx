import React from 'react';
import { motion } from 'framer-motion';

// TMDB provider logo IDs (network logos from TMDB's image service)
const PLATFORMS = [
  {
    id: 'Netflix',
    label: 'Netflix',
    logo: 'https://image.tmdb.org/t/p/original/t2yyOv40HZeVlLjYsCsPHnWLk4W.jpg',
  },
  {
    id: 'Amazon Prime Video',
    label: 'Prime Video',
    logo: 'https://image.tmdb.org/t/p/original/68MNrwlkpF7WnmNPXLah69CR5cb.jpg',
  },
  {
    id: 'Disney Plus',
    label: 'Disney+',
    logo: 'https://image.tmdb.org/t/p/original/7rwgEs15tFwyR9NPQ5nlzez1cIl.jpg',
  },
  {
    id: 'Hulu',
    label: 'Hulu',
    logo: 'https://image.tmdb.org/t/p/original/zxrVdFjIjLqkfnwyghnfywTn3Lh.jpg',
  },
  {
    id: 'Apple TV Plus',
    label: 'Apple TV+',
    logo: 'https://image.tmdb.org/t/p/original/6uhKBfmtzFqOcLousHwZuzcrScK.jpg',
  },
  {
    id: 'Max',
    label: 'Max',
    logo: 'https://image.tmdb.org/t/p/original/Ajqyt5aNxNvaG1Uz9q3ABCrGaOg.jpg',
  },
];

/**
 * PlatformFilter
 * @param {string|null} selected  — currently active platform id (or null for any)
 * @param {Function}    onChange  — called with new platform id, or null to deselect
 */
export default function PlatformFilter({ selected, onChange }) {
  return (
    <div className="flex items-center gap-3 flex-wrap mt-3">
      <span className="text-[10px] text-slate-500 uppercase tracking-widest font-body shrink-0">
        Stream on
      </span>

      {PLATFORMS.map((p, i) => {
        const active = selected === p.id;
        return (
          <motion.button
            key={p.id}
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: i * 0.04 }}
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => onChange(active ? null : p.id)}
            title={active ? `Remove ${p.label} filter` : `Filter by ${p.label}`}
            className={`relative w-11 h-11 rounded-xl overflow-hidden border-2 transition-all duration-300 focus:outline-none ${
              active
                ? 'border-accent shadow-[0_0_14px_rgba(245,158,11,0.55)] scale-110'
                : 'border-white/10 opacity-40 hover:opacity-90 hover:border-white/25'
            }`}
          >
            <img
              src={p.logo}
              alt={p.label}
              className="w-full h-full object-cover"
              onError={(e) => {
                // Graceful fallback to text initials if TMDB logo fails
                e.target.style.display = 'none';
                e.target.nextSibling.style.display = 'flex';
              }}
            />
            {/* Fallback initials badge — hidden by default */}
            <span
              className="absolute inset-0 items-center justify-center text-[9px] font-bold text-white bg-midnight-800 font-body"
              style={{ display: 'none' }}
            >
              {p.label.slice(0, 3).toUpperCase()}
            </span>

            {/* Active checkmark ring */}
            {active && (
              <motion.span
                layoutId="platform-ring"
                className="absolute inset-0 rounded-[10px] border-2 border-accent pointer-events-none"
              />
            )}
          </motion.button>
        );
      })}

      {/* Clear filter pill */}
      {selected && (
        <motion.button
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -8 }}
          onClick={() => onChange(null)}
          className="text-[10px] text-accent/70 hover:text-accent transition-colors font-body flex items-center gap-1 px-2 py-1 rounded-lg border border-accent/15 hover:border-accent/30"
        >
          ✕ Clear
        </motion.button>
      )}
    </div>
  );
}
