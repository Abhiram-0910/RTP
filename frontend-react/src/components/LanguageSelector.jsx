import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Globe, ChevronDown, Check } from 'lucide-react';
import { useAppContext } from '../context/AppContext';

/**
 * Languages supported by the MIRAI RAG backend.
 */
const LANGUAGES = [
  { label: 'English', value: 'en' },
  { label: 'Hindi',   value: 'hi' },
  { label: 'Telugu',  value: 'te' },
  { label: 'Spanish', value: 'es' },
  { label: 'French',  value: 'fr' },
  { label: 'German',  value: 'de' },
];

const LanguageSelector = () => {
  const { language, setLanguage } = useAppContext();
  const [isOpen, setIsOpen] = React.useState(false);

  const selectedTarget = LANGUAGES.find(l => l.value === language) || LANGUAGES[0];

  return (
    <div className="relative">
      <motion.button
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white/5 border border-white/10 hover:border-accent/30 hover:bg-white/10 transition-all duration-300 group"
      >
        <Globe size={14} className="text-slate-400 group-hover:text-accent transition-colors" />
        <span className="text-sm text-slate-300 font-medium font-body">{selectedTarget.label}</span>
        <ChevronDown 
          size={12} 
          className={`text-slate-500 transition-transform duration-300 ${isOpen ? 'rotate-180' : ''}`} 
        />
      </motion.button>

      <AnimatePresence>
        {isOpen && (
          <>
            {/* Backdrop for closing */}
            <div 
              className="fixed inset-0 z-40" 
              onClick={() => setIsOpen(false)} 
            />
            
            <motion.div
              initial={{ opacity: 0, y: 10, scale: 0.95 }}
              animate={{ opacity: 1, y: 5, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.95 }}
              className="absolute right-0 top-full mt-2 w-48 z-50 glass-card rounded-2xl border border-white/10 shadow-xl overflow-hidden py-1"
            >
              <div className="px-3 py-2 border-b border-white/5 mb-1">
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest font-body">
                  Select Language
                </span>
              </div>
              
              {LANGUAGES.map((item) => (
                <button
                  key={item.value}
                  onClick={() => {
                    setLanguage(item.value);
                    setIsOpen(false);
                  }}
                  className={`w-full flex items-center justify-between px-4 py-2.5 text-sm transition-colors font-body ${
                    language === item.value 
                      ? 'text-accent bg-accent/10' 
                      : 'text-slate-400 hover:text-white hover:bg-white/5'
                  }`}
                >
                  {item.label}
                  {language === item.value && <Check size={14} className="text-accent" />}
                </button>
              ))}
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
};

export default LanguageSelector;
