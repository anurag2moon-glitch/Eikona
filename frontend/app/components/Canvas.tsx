"use client";

import React, { useRef, useEffect, useState, forwardRef, useImperativeHandle } from 'react';
import { RotateCcw, Maximize2, Minimize2 } from 'lucide-react';

interface CanvasProps {
  onDraw?: () => void;
}

export interface CanvasHandle {
  clear: () => void;
  undo: () => void;
  getBlob: () => Promise<Blob>;
}

const Canvas = forwardRef<CanvasHandle, CanvasProps>(({ onDraw }, ref) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const contextRef = useRef<CanvasRenderingContext2D | null>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [history, setHistory] = useState<ImageData[]>([]);
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    initCanvas();
    window.addEventListener('resize', initCanvas);
    return () => window.removeEventListener('resize', initCanvas);
  }, [isFullscreen]);

  const initCanvas = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.parentElement?.getBoundingClientRect();
    if (!rect) return;

    // Use current parent size
    canvas.width = rect.width * window.devicePixelRatio;
    canvas.height = rect.height * window.devicePixelRatio;
    
    const context = canvas.getContext('2d', { willReadFrequently: true });
    if (!context) return;

    context.scale(window.devicePixelRatio, window.devicePixelRatio);
    context.lineCap = 'round';
    context.strokeStyle = 'white';
    context.lineWidth = 3;
    contextRef.current = context;

    // Background
    context.fillStyle = 'black';
    context.fillRect(0, 0, canvas.width, canvas.height);

    // Restore history if exists
    if (history.length > 0) {
      context.putImageData(history[history.length - 1], 0, 0);
    }
  };

  const saveToHistory = () => {
    const canvas = canvasRef.current;
    const context = contextRef.current;
    if (canvas && context) {
      const state = context.getImageData(0, 0, canvas.width, canvas.height);
      setHistory(prev => [...prev.slice(-19), state]); // Keep last 20 states
    }
  };

  useImperativeHandle(ref, () => ({
    clear: () => {
      const context = contextRef.current;
      const canvas = canvasRef.current;
      if (context && canvas) {
        context.fillStyle = 'black';
        context.fillRect(0, 0, canvas.width, canvas.height);
        setHistory([]);
      }
    },
    undo: () => {
      const canvas = canvasRef.current;
      const context = contextRef.current;
      if (canvas && context && history.length > 0) {
        const newHistory = [...history];
        newHistory.pop(); // Remove current state
        setHistory(newHistory);
        
        if (newHistory.length > 0) {
          context.putImageData(newHistory[newHistory.length - 1], 0, 0);
        } else {
          context.fillStyle = 'black';
          context.fillRect(0, 0, canvas.width, canvas.height);
        }
      }
    },
    getBlob: async () => {
      return new Promise((resolve) => {
        canvasRef.current?.toBlob((blob) => {
          if (blob) resolve(blob);
        }, 'image/png');
      });
    }
  }));

  const startDrawing = (e: React.MouseEvent | React.TouchEvent) => {
    saveToHistory();
    const { offsetX, offsetY } = getCoordinates(e);
    contextRef.current?.beginPath();
    contextRef.current?.moveTo(offsetX, offsetY);
    setIsDrawing(true);
  };

  const draw = (e: React.MouseEvent | React.TouchEvent) => {
    if (!isDrawing) return;
    const { offsetX, offsetY } = getCoordinates(e);
    contextRef.current?.lineTo(offsetX, offsetY);
    contextRef.current?.stroke();
    onDraw?.();
  };

  const endDrawing = () => {
    contextRef.current?.closePath();
    setIsDrawing(false);
  };

  const getCoordinates = (e: React.MouseEvent | React.TouchEvent) => {
    if ('touches' in e) {
      const rect = canvasRef.current?.getBoundingClientRect();
      if (!rect) return { offsetX: 0, offsetY: 0 };
      return {
        offsetX: e.touches[0].clientX - rect.left,
        offsetY: e.touches[0].clientY - rect.top
      };
    } else {
      return { offsetX: e.nativeEvent.offsetX, offsetY: e.nativeEvent.offsetY };
    }
  };

  return (
    <div className={`relative w-full h-full ${isFullscreen ? 'fixed inset-0 z-50 bg-black p-4' : ''}`}>
      <canvas
        ref={canvasRef}
        className="w-full h-full touch-none cursor-crosshair rounded-[32px]"
        onMouseDown={startDrawing}
        onMouseMove={draw}
        onMouseUp={endDrawing}
        onMouseLeave={endDrawing}
        onTouchStart={startDrawing}
        onTouchMove={draw}
        onTouchEnd={endDrawing}
      />
      
      {/* Canvas Toolset */}
      <div className="absolute top-6 right-6 flex flex-col gap-3">
        <button 
           onClick={() => {
             const canvas = canvasRef.current;
             const context = contextRef.current;
             if (canvas && context && history.length > 0) {
                const newHistory = [...history];
                newHistory.pop();
                setHistory(newHistory);
                if (newHistory.length > 0) context.putImageData(newHistory[newHistory.length - 1], 0, 0);
                else {
                  context.fillStyle = 'black';
                  context.fillRect(0, 0, canvas.width, canvas.height);
                }
             }
           }}
           title="Undo"
           className="h-10 w-10 glass-pill flex items-center justify-center hover:bg-white/10 transition-colors"
        >
          <RotateCcw className="w-4 h-4 text-white/60" />
        </button>
        <button 
           onClick={() => setIsFullscreen(!isFullscreen)}
           title={isFullscreen ? "Minimize" : "Fullscreen"}
           className="h-10 w-10 glass-pill flex items-center justify-center hover:bg-white/10 transition-colors"
        >
          {isFullscreen ? <Minimize2 className="w-4 h-4 text-white/60" /> : <Maximize2 className="w-4 h-4 text-white/60" />}
        </button>
      </div>
    </div>
  );
});

Canvas.displayName = 'Canvas';

export default Canvas;
