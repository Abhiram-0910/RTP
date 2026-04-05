import React, { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Camera, Upload, Sparkles, X, Loader2, Image as ImageIcon, Film } from 'lucide-react';
import toast from 'react-hot-toast';

const VisualMoodSearch = ({ onResultsFound }) => {
  const [isDragging, setIsDragging] = useState(false);
  const [preview, setPreview] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [extractedMood, setExtractedMood] = useState('');

  const handleFile = useCallback(async (file) => {
    if (!file || !file.type.startsWith('image/')) {
      toast.error('Please upload a valid image file.');
      return;
    }

    // Show preview
    const reader = new FileReader();
    reader.onload = (e) => setPreview(e.target.result);
    reader.readAsDataURL(file);

    setIsAnalyzing(true);
    setExtractedMood('');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('/api/mood-from-image', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) throw new Error('Analysis failed');

      const data = await response.json();
      setExtractedMood(data.extracted_query);
      
      if (onResultsFound && data.recommendations) {
        onResultsFound(data.recommendations, data.extracted_query);
      }
      
      toast.success('Visual mood analyzed successfully!');
    } catch (error) {
      console.error('Visual search error:', error);
      toast.error('Could not analyze the image. Please try again.');
    } finally {
      setIsAnalyzing(false);
    }
  }, [onResultsFound]);

  const onDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    handleFile(file);
  };

  const onFileSelect = (e) => {
    const file = e.target.files[0];
    handleFile(file);
  };

  const reset = () => {
    setPreview(null);
    setIsAnalyzing(false);
    setExtractedMood('');
  };

  return (
    <div className="w-full max-w-3xl mx-auto mb-10">
      <div className="relative group">
        {/* Glow effect */}
        <div className="absolute -inset-1 bg-gradient-to-r from-accent/20 via-cinema-violet/20 to-cinema-neon/20 rounded-2xl blur-xl opacity-50 group-hover:opacity-100 transition duration-1000 group-hover:duration-200"></div>
        
        <div 
          className={`relative glass-card rounded-2xl border-2 border-dashed transition-all duration-300 overflow-hidden ${
            isDragging ? 'border-accent bg-accent/5' : 'border-white/10 hover:border-white/20'
          }`}
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={onDrop}
        >
          <AnimatePresence mode="wait">
            {!preview ? (
              <motion.div 
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="py-12 flex flex-col items-center justify-center text-center px-4 cursor-pointer"
                onClick={() => document.getElementById('visual-upload').click()}
              >
                <div className="w-16 h-16 bg-midnight-900 rounded-full flex items-center justify-center mb-4 border border-white/5 shadow-inner">
                  <Camera className="text-accent" size={28} />
                </div>
                <h3 className="text-white font-display font-semibold text-lg mb-1">Search by Visual Mood</h3>
                <p className="text-slate-400 text-sm max-w-xs font-body">
                  Upload an image (movie poster, scene, or vibe) and our AI will find films that match its aesthetic.
                </p>
                <div className="mt-6 flex items-center gap-2 text-xs text-slate-500 font-medium font-body bg-white/5 px-4 py-2 rounded-full border border-white/5 transition-colors hover:bg-white/10">
                  <Upload size={14} />
                  Click to browse or drag & drop
                </div>
                <input 
                  id="visual-upload" 
                  type="file" 
                  accept="image/*" 
                  className="hidden" 
                  onChange={onFileSelect} 
                />
              </motion.div>
            ) : (
              <motion.div 
                key="preview"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="relative min-h-[300px] flex flex-col items-center justify-center p-6"
              >
                <div className="absolute inset-0 bg-midnight-950/60 backdrop-blur-sm z-10" />
                <img 
                  src={preview} 
                  alt="Preview" 
                  className="absolute inset-0 w-full h-full object-cover opacity-30 grayscale-[50%]"
                />
                
                {/* Content over preview */}
                <div className="relative z-20 flex flex-col items-center text-center w-full max-w-sm">
                  {isAnalyzing ? (
                    <div className="space-y-6 w-full">
                      <div className="relative w-24 h-24 mx-auto">
                        <motion.div 
                          className="absolute inset-0 border-4 border-accent/20 rounded-full"
                          animate={{ rotate: 360 }}
                          transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                        />
                        <motion.div 
                          className="absolute inset-0 border-4 border-t-accent rounded-full"
                          animate={{ rotate: 360 }}
                          transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
                        />
                        <div className="absolute inset-0 flex items-center justify-center">
                          <Sparkles className="text-accent animate-pulse" size={32} />
                        </div>
                      </div>
                      
                      <div className="space-y-2">
                        <h3 className="text-white font-display font-bold text-xl tracking-wide">Analyzing Visual Vibe</h3>
                        <p className="text-slate-300 text-sm animate-pulse font-body">Consulting Gemini Vision API...</p>
                      </div>

                      {/* Scanning Line Animation */}
                      <div className="w-full h-1 bg-white/10 rounded-full relative overflow-hidden">
                        <motion.div 
                          className="absolute h-full w-1/3 bg-gradient-to-r from-transparent via-accent to-transparent"
                          animate={{ left: ['-100%', '100%'] }}
                          transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
                        />
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-6">
                      <div className="w-16 h-16 bg-accent/20 rounded-full flex items-center justify-center mx-auto border border-accent/30 shadow-glow-sm">
                        <Sparkles className="text-accent" size={28} />
                      </div>
                      
                      <div>
                        <h3 className="text-white font-display font-bold text-2xl mb-2">Analysis Complete</h3>
                        <div className="flex flex-wrap justify-center gap-2 mt-4">
                          {extractedMood.split(',').map((tag, i) => (
                            <span 
                              key={i} 
                              className="px-3 py-1 bg-accent/10 border border-accent/20 rounded-full text-accent text-xs font-semibold font-body"
                            >
                              {tag.trim()}
                            </span>
                          ))}
                        </div>
                      </div>

                      <div className="flex gap-3 justify-center pt-2">
                        <button 
                          onClick={reset}
                          className="px-6 py-2 rounded-xl bg-white/5 border border-white/10 text-white text-sm font-semibold hover:bg-white/10 transition-colors"
                        >
                          Try Another Image
                        </button>
                      </div>
                    </div>
                  )}
                  
                  {!isAnalyzing && (
                    <button 
                      onClick={reset}
                      className="absolute top-2 right-2 p-2 bg-midnight-900/80 hover:bg-midnight-900 rounded-full text-slate-400 hover:text-white transition-colors"
                    >
                      <X size={20} />
                    </button>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
};

export default VisualMoodSearch;
