import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import MiraiLogo from './MiraiLogo';

/* ── Indian cinema hero backdrops from TMDB ───────────────────────────────── */
const HEROES = [
  {
    url: 'https://image.tmdb.org/t/p/w1280/5mVFSRoxFEQKSc6LxcJq4CMRhOD.jpg',
    label: 'Baahubali: The Beginning',
    fallbackBg: '#1a0a00',
  },
  {
    url: 'https://image.tmdb.org/t/p/w1280/nEufeZlyAsvMxKeZl5Vs7WEpRST.jpg',
    label: 'RRR',
    fallbackBg: '#0a1a10',
  },
  {
    url: 'https://image.tmdb.org/t/p/w1280/iEe3jDMqaGD2GP2hbRfNAuQsOEt.jpg',
    label: 'Salaar: Part 1 – Ceasefire',
    fallbackBg: '#0a0a1a',
  },
  {
    url: 'https://image.tmdb.org/t/p/w1280/xDMIl84Qo5Tmu6LA0IcAizJsDGT.jpg',
    label: 'KGF: Chapter 2',
    fallbackBg: '#1a1000',
  },
  {
    url: 'https://image.tmdb.org/t/p/w1280/vB8o2p4ETnrfiWEgVxHmHWP9yRl.jpg',
    label: 'Kalki 2898 AD',
    fallbackBg: '#0e0e1a',
  },
  {
    url: 'https://image.tmdb.org/t/p/w1280/h9DIlghaiTxbQbt1FIwKNbQvEL.jpg',
    label: 'Pushpa: The Rise',
    fallbackBg: '#1a0800',
  },
];

const TAGLINE_CHARS = 'Your Story. Your Screen.'.split('');

const CinematicIntro = ({ onComplete }) => {
  const [phase, setPhase] = useState(0); // 0=logo, 1=showcase, 2=tagline, 3=exit
  const [currentHero, setCurrentHero] = useState(0);
  const [skipped, setSkipped] = useState(false);

  /* ── Phase machine ──────────────────────────────────────────────────── */
  useEffect(() => {
    if (skipped) return;
    const timers = [];
    // Phase 0 → 1: logo for 2.5s
    timers.push(setTimeout(() => setPhase(1), 2500));
    // Phase 1 → 2: showcase for ~6s (6 images × 1s)
    timers.push(setTimeout(() => setPhase(2), 8500));
    // Phase 2 → 3: tagline for 2s
    timers.push(setTimeout(() => setPhase(3), 11000));
    // Complete
    timers.push(setTimeout(() => {
      localStorage.setItem('mirai_intro_seen', 'true');
      onComplete?.();
    }, 12200));
    return () => timers.forEach(clearTimeout);
  }, [skipped, onComplete]);

  /* ── Hero image rotation ─────────────────────────────────────────────── */
  useEffect(() => {
    if (phase !== 1) return;
    const interval = setInterval(() => {
      setCurrentHero(prev => (prev + 1) % HEROES.length);
    }, 1000);
    return () => clearInterval(interval);
  }, [phase]);

  const handleSkip = useCallback(() => {
    setSkipped(true);
    localStorage.setItem('mirai_intro_seen', 'true');
    onComplete?.();
  }, [onComplete]);

  if (skipped) return null;

  return (
    <motion.div
      className="fixed inset-0 z-[200] bg-black flex items-center justify-center overflow-hidden"
      exit={{ opacity: 0 }}
      transition={{ duration: 0.8 }}
    >
      {/* Film grain overlay */}
      <div className="film-grain" />

      {/* Letterbox bars */}
      <div className="letterbox-top" />
      <div className="letterbox-bottom" />

      {/* Skip button */}
      <motion.button
        initial={{ opacity: 0 }}
        animate={{ opacity: 0.6 }}
        whileHover={{ opacity: 1, scale: 1.05 }}
        transition={{ delay: 1 }}
        onClick={handleSkip}
        className="absolute bottom-[14vh] right-6 z-[210] text-white/60 text-xs font-body tracking-widest uppercase border border-white/20 px-4 py-1.5 rounded-full hover:border-accent/50 hover:text-accent transition-all"
      >
        Skip Intro
      </motion.button>

      <AnimatePresence mode="wait">
        {/* ── Phase 0: Logo Reveal ─────────────────────────────────────── */}
        {phase === 0 && (
          <motion.div
            key="logo"
            className="flex flex-col items-center gap-6"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 1.1, filter: 'blur(10px)' }}
            transition={{ duration: 0.8, ease: 'easeOut' }}
          >
            <MiraiLogo size={100} animate />
            <motion.h1
              className="text-4xl sm:text-6xl font-display font-bold text-gradient tracking-tight"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 1.2, duration: 0.8 }}
            >
              MIRAI
            </motion.h1>
            <motion.p
              className="text-white/30 text-sm font-body tracking-[0.3em] uppercase"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 1.8, duration: 0.6 }}
            >
              Cinematic Intelligence
            </motion.p>
          </motion.div>
        )}

        {/* ── Phase 1: Hero Showcase ─────────────────────────────────── */}
        {phase === 1 && (
          <motion.div
            key="showcase"
            className="absolute inset-0"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.6 }}
          >
            <AnimatePresence>
              <motion.div
                key={currentHero}
                className="absolute inset-0 bg-black/40"
                initial={{ opacity: 0, scale: 1.15 }}
                animate={{ opacity: 1, scale: 1.05 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 1.2, ease: "easeOut" }}
              >
                {/* Ken Burns slow zoom via CSS */}
                <style>{`
                  @keyframes kenBurns { 0% { transform: scale(1); } 100% { transform: scale(1.1); } }
                  .kb-active { animation: kenBurns 4s ease-out forwards; }
                `}</style>
                <img
                  src={HEROES[currentHero].url}
                  alt={HEROES[currentHero].label}
                  className="w-full h-full object-cover kb-active"
                  loading="eager"
                  style={{ 
                    filter: 'brightness(0.6) contrast(1.1) saturate(1.2)',
                    backgroundColor: HEROES[currentHero].fallbackBg || '#111' 
                  }}
                  onError={(e) => {
                    console.error("Hero image failed to load:", e.target.src);
                    e.target.style.backgroundColor = HEROES[currentHero].fallbackBg || '#111';
                    e.target.style.display = 'none';
                  }}
                />
                {/* Gradient overlays */}
                <div className="absolute inset-0 bg-gradient-to-t from-black via-transparent to-black/60" />
                <div className="absolute inset-0 bg-gradient-to-r from-black/20 via-transparent to-black/20" />
                {/* Title */}
                <motion.div
                  className="absolute bottom-[16vh] left-8 sm:left-16"
                  initial={{ x: -30, opacity: 0 }}
                  animate={{ x: 0, opacity: 1 }}
                  transition={{ delay: 0.3, duration: 0.5 }}
                >
                  <p className="text-accent text-[10px] tracking-[0.4em] uppercase font-body mb-1">Now Streaming</p>
                  <h2 className="text-white text-3xl sm:text-5xl font-display font-bold">{HEROES[currentHero].label}</h2>
                </motion.div>
              </motion.div>
            </AnimatePresence>
          </motion.div>
        )}

        {/* ── Phase 2: Tagline Typewriter ──────────────────────────────── */}
        {phase === 2 && (
          <motion.div
            key="tagline"
            className="flex flex-col items-center gap-8"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.6 }}
          >
            <div className="flex overflow-hidden">
              {TAGLINE_CHARS.map((char, i) => (
                <motion.span
                  key={i}
                  className="text-3xl sm:text-5xl font-display font-bold text-white"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.05, duration: 0.3 }}
                >
                  {char === ' ' ? '\u00A0' : char}
                </motion.span>
              ))}
            </div>
            <motion.div
              className="w-24 h-0.5 bg-accent rounded-full"
              initial={{ scaleX: 0 }}
              animate={{ scaleX: 1 }}
              transition={{ delay: 1.2, duration: 0.6 }}
            />
          </motion.div>
        )}

        {/* ── Phase 3: Iris Wipe Exit ──────────────────────────────────── */}
        {phase === 3 && (
          <motion.div
            key="exit"
            className="absolute inset-0 bg-midnight-950"
            initial={{ clipPath: 'circle(100% at 50% 50%)' }}
            animate={{ clipPath: 'circle(0% at 50% 50%)' }}
            transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
          />
        )}
      </AnimatePresence>
    </motion.div>
  );
};

export default CinematicIntro;
