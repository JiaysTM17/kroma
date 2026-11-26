'use client';

import React, { useEffect, useRef, useState } from 'react';
import {
  ZoomIn,
  ZoomOut,
  Maximize2,
  Eye,
  Grid3X3,
  Paintbrush,
  Sun,
  Moon,
  Sparkles,
} from 'lucide-react';
import { AdjustmentValues, ImageAsset, MarketplacePreset, ShadowConfig } from '@/lib/types';
import { applyFloat32Adjustments, drawSafeZone, renderShadow } from '@/lib/canvasPipeline';
import { Language, translations } from '@/lib/i18n';

interface CanvasWorkspaceProps {
  lang: Language;
  asset: ImageAsset | null;
  preset: MarketplacePreset;
  shadow: ShadowConfig;
  adjustments: AdjustmentValues;
  isRemovingBg: boolean;
  isBrushActive: boolean;
  brushSize: number;
  onUpdateAssetMask?: (maskDataUrl: string) => void;
}

export const CanvasWorkspace: React.FC<CanvasWorkspaceProps> = ({
  lang,
  asset,
  preset,
  shadow,
  adjustments,
  isRemovingBg,
  isBrushActive,
  brushSize,
  onUpdateAssetMask,
}) => {
  const t = translations[lang];
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const [zoom, setZoom] = useState(1);
  const [bgMode, setBgMode] = useState<'white' | 'dark' | 'checker'>('white');
  const [showSafeZone, setShowSafeZone] = useState(true);
  const [showGrid, setShowGrid] = useState(false);
  const [isComparing, setIsComparing] = useState(false);

  // Loaded image cache
  const [loadedImg, setLoadedImg] = useState<HTMLImageElement | null>(null);

  useEffect(() => {
    if (!asset) {
      setLoadedImg(null);
      return;
    }
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.src = asset.processedUrl || asset.originalUrl;
    img.onload = () => setLoadedImg(img);
  }, [asset, asset?.processedUrl]);

  // Main Render Cycle
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    if (!ctx) return;

    // Canvas resolution matches the active Marketplace Preset
    canvas.width = preset.width;
    canvas.height = preset.height;

    // 1. Clear & Render Background
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (bgMode === 'white') {
      ctx.fillStyle = '#FFFFFF';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    } else if (bgMode === 'dark') {
      ctx.fillStyle = '#0F172A';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    } else {
      // Checkerboard transparency pattern
      const size = 16;
      for (let y = 0; y < canvas.height; y += size) {
        for (let x = 0; x < canvas.width; x += size) {
          ctx.fillStyle = (x / size + y / size) % 2 === 0 ? '#FFFFFF' : '#E2E8F0';
          ctx.fillRect(x, y, size, size);
        }
      }
    }

    if (!loadedImg) return;

    // 2. Compute Subject Framing
    // Amazon rule: subject must occupy >= 85% area if specified
    const scaleRatio = preset.subject_area_ratio || 0.82;
    const maxSubjectW = canvas.width * scaleRatio;
    const maxSubjectH = canvas.height * scaleRatio;

    const imgAspect = loadedImg.width / loadedImg.height;
    let drawW = maxSubjectW;
    let drawH = drawW / imgAspect;

    if (drawH > maxSubjectH) {
      drawH = maxSubjectH;
      drawW = drawH * imgAspect;
    }

    const drawX = (canvas.width - drawW) / 2;
    // Align subject slightly grounded towards the bottom for physical shadow realism
    const drawY = (canvas.height - drawH) / 2 + (canvas.height * 0.02);

    // 3. Render Physical Shadow Layer (Beneath Subject)
    if (asset?.hasBackgroundRemoved && !isComparing) {
      renderShadow(ctx, loadedImg, drawX, drawY, drawW, drawH, shadow);
    }

    // 4. Render Subject with Float32 Linear Light Adjustments
    if (isComparing && asset) {
      // Draw original unmodified photo for comparison
      const origImg = new Image();
      origImg.src = asset.originalUrl;
      ctx.drawImage(origImg, drawX, drawY, drawW, drawH);
    } else {
      // Draw subject offscreen to apply adjustments without degrading main canvas
      const offscreen = document.createElement('canvas');
      offscreen.width = Math.round(drawW);
      offscreen.height = Math.round(drawH);
      const offCtx = offscreen.getContext('2d');

      if (offCtx) {
        offCtx.drawImage(loadedImg, 0, 0, drawW, drawH);
        const hasAdjustments =
          adjustments.exposure !== 0 ||
          adjustments.contrast !== 0 ||
          adjustments.temperature !== 0 ||
          adjustments.tint !== 0;

        if (hasAdjustments) {
          const imgData = offCtx.getImageData(0, 0, offscreen.width, offscreen.height);
          applyFloat32Adjustments(imgData, adjustments);
          offCtx.putImageData(imgData, 0, 0);
        }

        ctx.drawImage(offscreen, drawX, drawY, drawW, drawH);
      }
    }

    // 5. Draw Overlays (Rule of thirds & Safe Zone)
    if (showGrid) {
      ctx.save();
      ctx.strokeStyle = 'rgba(148, 163, 184, 0.35)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(canvas.width / 3, 0);
      ctx.lineTo(canvas.width / 3, canvas.height);
      ctx.moveTo((canvas.width * 2) / 3, 0);
      ctx.lineTo((canvas.width * 2) / 3, canvas.height);
      ctx.moveTo(0, canvas.height / 3);
      ctx.lineTo(canvas.width, canvas.height / 3);
      ctx.moveTo(0, (canvas.height * 2) / 3);
      ctx.lineTo(canvas.width, (canvas.height * 2) / 3);
      ctx.stroke();
      ctx.restore();
    }

    if (showSafeZone) {
      drawSafeZone(ctx, canvas.width, canvas.height, preset);
    }
  }, [
    loadedImg,
    preset,
    shadow,
    adjustments,
    bgMode,
    showSafeZone,
    showGrid,
    isComparing,
    asset?.hasBackgroundRemoved,
  ]);

  return (
    <div className="flex-1 flex flex-col bg-slate-100 overflow-hidden relative select-none">
      {/* Top Floating Viewport Toolbar */}
      <div className="h-10 border-b border-surface-border bg-surface-light px-4 flex items-center justify-between z-10">
        {/* Preset Info */}
        <div className="flex items-center gap-2 text-xs">
          <span className="font-semibold text-slate-800">{preset.name_vi}</span>
          <span className="text-slate-400">|</span>
          <span className="text-slate-500 font-mono">
            {preset.width} × {preset.height} px ({preset.aspect_ratio})
          </span>
        </div>

        {/* View Controls */}
        <div className="flex items-center gap-1.5">
          {/* Safe-zone toggle */}
          <button
            onClick={() => setShowSafeZone(!showSafeZone)}
            className={`p-1.5 rounded text-xs flex items-center gap-1 transition-colors ${
              showSafeZone
                ? 'bg-cyan-50 text-cyan-700 border border-cyan-200'
                : 'text-slate-500 hover:text-slate-800'
            }`}
            title={t.safe_zone_toggle}
          >
            <span className="text-[11px] font-medium">Safe Zone</span>
          </button>

          {/* Grid 3x3 toggle */}
          <button
            onClick={() => setShowGrid(!showGrid)}
            className={`p-1.5 rounded transition-colors ${
              showGrid
                ? 'bg-slate-200 text-slate-900'
                : 'text-slate-500 hover:text-slate-800'
            }`}
            title="Lưới bố cục 1/3"
          >
            <Grid3X3 className="w-3.5 h-3.5" />
          </button>

          {/* Background Modes */}
          <div className="flex items-center bg-slate-100 p-0.5 rounded border border-slate-200 text-xs">
            <button
              onClick={() => setBgMode('white')}
              className={`p-1 rounded transition-colors ${
                bgMode === 'white' ? 'bg-white shadow-xs text-slate-900' : 'text-slate-500'
              }`}
              title={t.view_white}
            >
              <Sun className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setBgMode('dark')}
              className={`p-1 rounded transition-colors ${
                bgMode === 'dark' ? 'bg-white shadow-xs text-slate-900' : 'text-slate-500'
              }`}
              title={t.view_dark}
            >
              <Moon className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setBgMode('checker')}
              className={`px-1.5 py-0.5 text-[10px] font-mono rounded transition-colors ${
                bgMode === 'checker' ? 'bg-white shadow-xs text-slate-900' : 'text-slate-500'
              }`}
              title={t.view_checkerboard}
            >
              PNG
            </button>
          </div>

          {/* Compare Button */}
          {asset?.hasBackgroundRemoved && (
            <button
              onMouseDown={() => setIsComparing(true)}
              onMouseUp={() => setIsComparing(false)}
              onMouseLeave={() => setIsComparing(false)}
              className="px-2 py-1 text-[11px] font-medium rounded border border-slate-200 bg-surface-subtle hover:bg-surface-muted text-slate-700 flex items-center gap-1 active:bg-slate-200"
            >
              <Eye className="w-3 h-3 text-slate-500" />
              <span>Giữ xem ảnh gốc</span>
            </button>
          )}

          {/* Zoom controls */}
          <div className="flex items-center gap-1 pl-2 border-l border-slate-200">
            <button
              onClick={() => setZoom((z) => Math.max(0.25, z - 0.15))}
              className="p-1 text-slate-500 hover:text-slate-900"
              title="Thu nhỏ"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <span className="text-[11px] font-mono text-slate-600 min-w-[36px] text-center">
              {Math.round(zoom * 100)}%
            </span>
            <button
              onClick={() => setZoom((z) => Math.min(3, z + 0.15))}
              className="p-1 text-slate-500 hover:text-slate-900"
              title="Phóng to"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setZoom(1)}
              className="p-1 text-slate-500 hover:text-slate-900"
              title="Về 100%"
            >
              <Maximize2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Interactive Canvas Canvas Center */}
      <div className="flex-1 flex items-center justify-center p-8 overflow-auto relative">
        {isRemovingBg && (
          <div className="absolute inset-0 bg-white/70 backdrop-blur-xs flex flex-col items-center justify-center z-30 gap-2">
            <div className="w-8 h-8 rounded-full border-2 border-kroma-600 border-t-transparent animate-spin" />
            <p className="text-xs font-semibold text-slate-800">{t.removing_bg}</p>
          </div>
        )}

        {!asset ? (
          <div className="text-center py-24 text-slate-400 text-xs">
            Vui lòng chọn hoặc tải ảnh từ cột bên trái để bắt đầu xử lý
          </div>
        ) : (
          <div
            style={{
              transform: `scale(${zoom})`,
              transformOrigin: 'center center',
              transition: 'transform 0.1s ease-out',
            }}
            className="shadow-xl rounded overflow-hidden border border-slate-300 relative bg-white"
          >
            <canvas ref={canvasRef} className="block max-w-none" />
          </div>
        )}
      </div>
    </div>
  );
};
