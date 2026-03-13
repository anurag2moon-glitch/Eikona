"use client";

import React, { useState, useRef } from 'react';
import {
  Download,
  X,
  ChevronRight,
  RefreshCw,
  Database,
  ShieldCheck,
  ZapIcon,
  CircleDashed,
  Layers,
  Sparkles,
  Cpu
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import Canvas, { CanvasHandle } from './components/Canvas';
import { submitJob, pollJob, getResultUrl } from './lib/api';

export default function Home() {
  const [activeTab, setActiveTab] = useState<'upload' | 'sketch'>('sketch');
  const [image, setImage] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<'idle' | 'uploading' | 'processing' | 'done' | 'error'>('idle');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);

  const canvasRef = useRef<CanvasHandle>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) {
      setFile(f);
      const reader = new FileReader();
      reader.onload = (e) => setImage(e.target?.result as string);
      reader.readAsDataURL(f);
      setActiveTab('upload');
      setErrorMsg(null);
    }
  };

  const handleGenerate = async () => {
    try {
      setErrorMsg(null);
      setStatus('uploading');
      let blob: Blob;

      if (activeTab === 'sketch' && canvasRef.current) {
        blob = await canvasRef.current.getBlob();
      } else if (file) {
        blob = file;
      } else {
        setStatus('idle');
        return;
      }

      const id = await submitJob(blob);
      setJobId(id);
      setStatus('processing');

      await pollJob(id);
      setStatus('done');
    } catch (err) {
      console.error(err);
      setErrorMsg(err instanceof Error ? err.message : 'An unexpected error occurred.');
      setStatus('error');
    }
  };

  const reset = () => {
    setImage(null);
    setFile(null);
    setJobId(null);
    setStatus('idle');
    setErrorMsg(null);
    if (canvasRef.current) canvasRef.current.clear();
  };

  return (
    <main className="min-h-screen max-w-lg mx-auto bg-canvas text-white p-6 relative flex flex-col font-sans">
      {/* Header - Unified Brand Row */}
      <header className="flex justify-between items-center py-4 mb-2">
        <h1 className="text-3xl font-bold tracking-tight text-white/90" style={{ fontFamily: 'Caveat, cursive' }}>
          Eikona
        </h1>

        <div className="flex bg-white/[0.03] p-1 rounded-full border border-white/5 shadow-inner">
          <button
            onClick={() => setActiveTab('sketch')}
            className={`text-[9px] uppercase tracking-[0.2em] font-black px-5 py-2 rounded-full transition-all duration-300 ${activeTab === 'sketch' ? 'bg-white text-black shadow-lg shadow-white/5' : 'text-white/20 hover:text-white/40'}`}
          >
            Sketch
          </button>
          <button
            onClick={() => setActiveTab('upload')}
            className={`text-[9px] uppercase tracking-[0.2em] font-black px-5 py-2 rounded-full transition-all duration-300 ${activeTab === 'upload' ? 'bg-white text-black shadow-lg shadow-white/5' : 'text-white/20 hover:text-white/40'}`}
          >
            Upload
          </button>
        </div>
      </header>

      <AnimatePresence mode="wait">
        {status === 'error' ? (
          <motion.div 
            key="error"
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            className="flex-1 flex flex-col items-center justify-center text-center p-6"
          >
            <div className="w-20 h-20 rounded-full bg-red-500/10 flex items-center justify-center mb-6">
              <X className="w-10 h-10 text-red-500" />
            </div>
            <h2 className="text-2xl font-bold mb-4">Synthesis Failed</h2>
            <p className="text-white/40 leading-relaxed mb-10 max-w-xs mx-auto">
              {errorMsg || 'The neural engine encountered an unexpected interruption.'}
            </p>
            <button 
              onClick={reset}
              className="btn-secondary w-full py-4 rounded-3xl font-bold flex items-center justify-center gap-3 border-white/10"
            >
              <RefreshCw className="w-5 h-5" /> Return & Reset
            </button>
          </motion.div>
        ) : status === 'done' && jobId ? (
          <motion.div 
            key="result"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex-1 flex flex-col gap-6"
          >
            <div className="glass-card flex-1 overflow-y-auto custom-scrollbar flex flex-col gap-6 p-4 border-white/[0.03]">
              {/* Top: 3-Image Comparison */}
              <div className="flex flex-col gap-3">
                <span className="text-[10px] font-black uppercase tracking-[0.2em] text-white/20 italic ml-1">Synthesis Breakdown</span>
                <div className="aspect-[3/1] bg-black/40 rounded-2xl overflow-hidden p-1 border border-white/5">
                  <img 
                    src={getResultUrl(jobId)} 
                    className="w-full h-full object-contain" 
                    alt="Synthesis Breakdown" 
                  />
                </div>
              </div>

              {/* Bottom: Solo Output */}
              <div className="flex flex-col gap-3">
                <span className="text-[10px] font-black uppercase tracking-[0.2em] text-white/20 italic ml-1">Generated Artifact</span>
                <div className="aspect-square bg-black/40 rounded-2xl overflow-hidden border border-white/5 relative">
                  <div style={{
                    width: '100%',
                    height: '100%',
                    overflow: 'hidden',
                    position: 'relative'
                  }}>
                    <img 
                      src={getResultUrl(jobId)} 
                      className="absolute object-cover"
                      style={{
                        width: '300%',
                        height: 'calc(100% - 40px)', // adjusted for backend label height
                        maxWidth: 'none',
                        right: 0,
                        top: 0
                      }}
                      alt="Solo Result" 
                    />
                  </div>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-4 gap-4 mt-auto mb-4">
              <button 
                onClick={reset}
                className="btn-secondary h-16 rounded-3xl font-medium flex items-center justify-center border-white/5 group"
              >
                <RefreshCw className="w-5 h-5 text-white/20 group-hover:rotate-180 transition-transform duration-500" />
              </button>
              <button 
                onClick={async () => {
                   const url = getResultUrl(jobId);
                   const response = await fetch(url);
                   const blob = await response.blob();
                   const blobUrl = window.URL.createObjectURL(blob);
                   const link = document.createElement('a');
                   link.href = blobUrl;
                   link.download = `eikona-${jobId.slice(0,8)}.png`;
                   document.body.appendChild(link);
                   link.click();
                   document.body.removeChild(link);
                }}
                className="btn-primary col-span-3 h-16 rounded-3xl flex items-center justify-center gap-2 shadow-xl shadow-green-500/10 active:scale-98 transition-all"
              >
                <Download className="w-6 h-6" /> 
                <span className="font-bold tracking-tight">Save Artifact</span>
              </button>
            </div>
          </motion.div>
        ) : (
          <motion.div
            key="input"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex-1 flex flex-col"
          >
            {/* Hero Section */}
            <div className="mb-4 mt-4 px-1">
              <h2 className="text-3xl font-bold tracking-tight mb-3">
                Visual <span className="text-gradient">Optimization.</span>
              </h2>
              <p className="text-white/30 leading-snug text-[13px] font-medium pr-10">
                Unified RAG pipeline for photorealistic artifact generation from latent conceptual traces.
              </p>
            </div>

            {/* Interaction Layer */}
            <div className="glass-card h-[400px] relative overflow-hidden mb-6 border-white/[0.04]">
              {activeTab === 'sketch' ? (
                <Canvas ref={canvasRef} onDraw={() => status !== 'idle' && setStatus('idle')} />
              ) : (
                <div
                  className="w-full h-full flex flex-col items-center justify-center cursor-pointer transition-all hover:bg-white/[0.01]"
                  onClick={() => fileRef.current?.click()}
                >
                  {image ? (
                    <div className="w-full h-full p-6 animate-fade-in">
                      <img src={image} className="w-full h-full object-contain rounded-2xl" alt="Preview" />
                    </div>
                  ) : (
                    <div className="text-center p-8 space-y-6">
                      <div className="w-20 h-20 rounded-[32px] bg-white/[0.02] border border-white/5 flex items-center justify-center mx-auto shadow-2xl">
                        <Layers className="w-8 h-8 text-white/10" />
                      </div>
                      <div className="space-y-1.5">
                        <p className="text-[11px] font-black tracking-[0.3em] uppercase text-white/20">Initialize Context</p>
                        <p className="text-[9px] text-white/10 italic">Drop conceptual source or click to browse</p>
                      </div>
                    </div>
                  )}
                  <input type="file" ref={fileRef} className="hidden" onChange={handleFileChange} accept="image/*" />
                </div>
              )}

              {/* Floating Trigger */}
              <div className="absolute bottom-6 right-6 left-6 flex justify-between items-center">
                <button
                  onClick={reset}
                  className="h-14 w-14 rounded-[24px] btn-secondary flex items-center justify-center border-white/[0.05] group"
                >
                  <X className="w-5 h-5 text-white/20 group-hover:text-white transition-colors" />
                </button>
                <button
                  onClick={handleGenerate}
                  disabled={status === 'processing' || status === 'uploading'}
                  className="h-16 w-16 rounded-full btn-primary flex items-center justify-center shadow-2xl shadow-green-400/30 disabled:opacity-20 transition-all active:scale-95"
                >
                  {status === 'processing' ? (
                    <CircleDashed className="w-7 h-7 animate-spin" />
                  ) : (
                    <ChevronRight className="w-9 h-9" />
                  )}
                </button>
              </div>
            </div>

            {/* Professional Tech Specs Section */}
            <div className="space-y-6 mt-2 mb-10 overflow-y-auto custom-scrollbar pr-2 max-h-[300px]">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-black uppercase tracking-[0.3em] text-white/10 italic">Core Intelligence Briefing</span>
                <div className="h-[1px] flex-1 bg-white/[0.05] ml-6" />
              </div>

              {/* Technical FAQ / Intel Section */}
              <div className="grid grid-cols-1 gap-2 pt-2">
                {[
                  { q: "RAG Augmented Fusion", a: "Semantic reference features (CLIP ViT-L/14) are injected via 6-channel concatenation directly into the U-Net skip connections, providing non-local prior guidance.", icon: Database },
                  { q: "Latent Conditioning", a: "The generator utilizes a hybrid input state where the user sketch provides structural topology, while the RAG-retrieved features modulate the latent style distribution.", icon: Layers },
                  { q: "Dolphin Inference Layer", a: "A specialized detached worker process orchestrating job state via a file-based FIFO queue, ensuring 1:1 GPU memory allocation and preventing VRAM thrashing.", icon: ZapIcon },
                  { q: "Optimization & Compute", a: "Optimized for Apple Silicon (MPS) and NVIDIA (CUDA) with FP16 precision, leveraging FAISS's FlatIP index for sub-millisecond similarity lookups.", icon: Cpu },
                  { q: "Loss Objectives", a: "The model is trained on a weighted sum of L1 reconstruction loss, Perceptual (VGG) loss, and Adversarial (GAN) loss to ensure both structural accuracy and photorealistic fidelity.", icon: Sparkles },
                  { q: "Data Sovereignty", a: "Zero-persistence architecture. All task-specific weights and temporary job artifacts reside in a localized sandbox, pruned automatically upon worker cycle.", icon: ShieldCheck }
                ].map((faq, i) => (
                  <div key={i} className="p-4 rounded-3xl bg-white/[0.01] border border-white/[0.03] space-y-2 group hover:bg-white/[0.02] transition-colors">
                    <div className="flex items-center gap-3">
                      <div className="p-1.5 rounded-lg bg-green-500/5 group-hover:bg-green-500/10 transition-colors">
                        <faq.icon className="w-3.5 h-3.5 text-green-500/40 group-hover:text-green-400 transition-colors" />
                      </div>
                      <span className="text-[10px] font-black text-white/50 uppercase tracking-tighter">{faq.q}</span>
                    </div>
                    <p className="text-[10px] leading-relaxed text-white/20 font-medium pl-9">
                      {faq.a}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            {/* Synthesis HUD Overlay */}
            {status === 'processing' && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex items-center gap-6 px-1 mb-8"
              >
                <div className="flex-1 h-[1px] bg-white/5 relative">
                  <motion.div
                    initial={{ left: 0, width: 0 }}
                    animate={{ left: "0%", width: "100%" }}
                    transition={{ duration: 15, repeat: Infinity, ease: "linear" }}
                    className="absolute h-full bg-gradient-to-r from-transparent via-green-400 to-transparent opacity-50"
                  />
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-[9px] font-black tracking-[0.3em] uppercase text-green-400 animate-pulse">Synthesis_Active</span>
                </div>
              </motion.div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  );
}
