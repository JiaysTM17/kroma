'use client';

import React, { useEffect, useRef, useState } from 'react';
import {
  ZoomIn,
  ZoomOut,
  Maximize2,
  Grid3X3,
  Sun,
  Moon,
  SplitSquareVertical,
  Move,
  RotateCcw,
} from 'lucide-react';
import {
  AdjustmentValues,
  ImageAsset,
  MarketplacePreset,
  PromoBadgeConfig,
  ShadowConfig,
  TransformState,
  WatermarkConfig,
} from '@/lib/types';
import {
  applyFloat32Adjustments,
  drawSafeZone,
  renderBoundingBox,
  renderPromoBadge,
  renderShadow,
  renderSplitDivider,
  renderWatermark,
} from '@/lib/canvasPipeline';
import { Language, translations } from '@/lib/i18n';

interface CanvasWorkspaceProps {
  lang: Language;
  asset: ImageAsset | null;
  preset: MarketplacePreset;
  shadow: ShadowConfig;
  adjustments: AdjustmentValues;
  promoBadge: PromoBadgeConfig;
  watermark: WatermarkConfig;
  transform: TransformState;
  onTransformChange: (t: TransformState) => void;
  isRemovingBg: boolean;
  isBrushActive: boolean;
  brushSize: number;
}

export const CanvasWorkspace: React.FC<CanvasWorkspaceProps> = ({
  lang,
  asset,
  preset,
  shadow,
  adjustments,
  promoBadge,
  watermark,
  transform,
  onTransformChange,
  isRemovingBg,
  isBrushActive,
  brushSize,
}) => {
  const t = translations[lang];
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const [zoom, setZoom] = useState(1);
  const [bgMode, setBgMode] = useState<'white' | 'dark' | 'checker' | 'warm'>('white');
  const [showSafeZone, setShowSafeZone] = useState(true);
  const [showGrid, setShowGrid] = useState(false);
  const [showHandles, setShowHandles] = useState(true);
  const [splitSliderEnabled, setSplitSliderEnabled] = useState(false);
  const [splitPos, setSplitPos] = useState(0.5); // 0.0 to 1.0

  // Dragging states
  const [isDraggingProduct, setIsDraggingProduct] = useState(false);
  const [isDraggingSlider, setIsDraggingSlider] = useState(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // Loaded image cache
  const [loadedImg, setLoadedImg] = useState<HTMLImageElement | null>(null);
  const [origImg, setOrigImg] = useState<HTMLImageElement | null>(null);

  useEffect(() => {
    if (!asset) {
      setLoadedImg(null);
      setOrigImg(null);
      return;
    }
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.src = asset.processedUrl || asset.originalUrl;
    img.onload = () => setLoadedImg(img);

    const oImg = new Image();
    oImg.crossOrigin = 'anonymous';
    oImg.src = asset.originalUrl;
    oImg.onload = () => setOrigImg(oImg);
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
    } else if (bgMode === 'warm') {
      // Warm studio pedestal gradient
      const grad = ctx.createLinearGradient(0, 0, 0, canvas.height);
      grad.addColorStop(0, '#F8FAFC');
      grad.addColorStop(0.7, '#F1F5F9');
      grad.addColorStop(1, '#E2E8F0');
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Studio pedestal circle
      ctx.save();
      ctx.fillStyle = '#E2E8F0';
      ctx.beginPath();
      ctx.ellipse(canvas.width / 2, canvas.height * 0.88, canvas.width * 0.38, canvas.height * 0.08, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    } else {
      // Checkerboard transparency pattern
      const size = 20;
      for (let y = 0; y < canvas.height; y += size) {
        for (let x = 0; x < canvas.width; x += size) {
          ctx.fillStyle = (x / size + y / size) % 2 === 0 ? '#FFFFFF' : '#E2E8F0';
          ctx.fillRect(x, y, size, size);
        }
      }
    }

    if (!loadedImg) return;

    // 2. Compute Subject Framing
    const scaleRatio = (preset.subject_area_ratio || 0.82) * transform.scale;
    const maxSubjectW = canvas.width * scaleRatio;
    const maxSubjectH = canvas.height * scaleRatio;

    const imgAspect = loadedImg.width / loadedImg.height;
    let drawW = maxSubjectW;
    let drawH = drawW / imgAspect;

    if (drawH > maxSubjectH) {
      drawH = maxSubjectH;
      drawW = drawH * imgAspect;
    }

    const drawX = (canvas.width - drawW) / 2 + transform.offsetX;
    const drawY = (canvas.height - drawH) / 2 + (canvas.height * 0.02) + transform.offsetY;

    // 3. Render Processed Scene (or Split Scene)
    const splitX = canvas.width * splitPos;

    if (splitSliderEnabled && origImg) {
      // LEFT SIDE: Draw original unmodified scene clipped to splitX
      ctx.save();
      ctx.beginPath();
      ctx.rect(0, 0, splitX, canvas.height);
      ctx.clip();
      ctx.drawImage(origImg, drawX, drawY, drawW, drawH);
      ctx.restore();

      // RIGHT SIDE: Draw processed scene with shadows & adjustments clipped to remaining area
      ctx.save();
      ctx.beginPath();
      ctx.rect(splitX, 0, canvas.width - splitX, canvas.height);
      ctx.clip();

      if (asset?.hasBackgroundRemoved) {
        renderShadow(ctx, loadedImg, drawX, drawY, drawW, drawH, shadow);
      }

      // Draw adjusted subject
      const offscreen = document.createElement('canvas');
      offscreen.width = Math.max(1, Math.round(drawW));
      offscreen.height = Math.max(1, Math.round(drawH));
      const offCtx = offscreen.getContext('2d');
      if (offCtx) {
        offCtx.drawImage(loadedImg, 0, 0, drawW, drawH);
        const hasAdj =
          adjustments.exposure !== 0 ||
          adjustments.contrast !== 0 ||
          adjustments.temperature !== 0 ||
          adjustments.tint !== 0;

        if (hasAdj) {
          const imgData = offCtx.getImageData(0, 0, offscreen.width, offscreen.height);
          applyFloat32Adjustments(imgData, adjustments);
          offCtx.putImageData(imgData, 0, 0);
        }
        ctx.drawImage(offscreen, drawX, drawY, drawW, drawH);
      }
      ctx.restore();

      // Draw split divider line & handle
      renderSplitDivider(ctx, canvas.height, splitX);

    } else {
      // Normal full-processed render
      if (asset?.hasBackgroundRemoved) {
        renderShadow(ctx, loadedImg, drawX, drawY, drawW, drawH, shadow);
      }

      const offscreen = document.createElement('canvas');
      offscreen.width = Math.max(1, Math.round(drawW));
      offscreen.height = Math.max(1, Math.round(drawH));
      const offCtx = offscreen.getContext('2d');
      if (offCtx) {
        offCtx.drawImage(loadedImg, 0, 0, drawW, drawH);
        const hasAdj =
          adjustments.exposure !== 0 ||
          adjustments.contrast !== 0 ||
          adjustments.temperature !== 0 ||
          adjustments.tint !== 0;

        if (hasAdj) {
          const imgData = offCtx.getImageData(0, 0, offscreen.width, offscreen.height);
          applyFloat32Adjustments(imgData, adjustments);
          offCtx.putImageData(imgData, 0, 0);
        }
        ctx.drawImage(offscreen, drawX, drawY, drawW, drawH);
      }
    }

    // 4. Overlays: Promo Badges & Watermarks
    renderPromoBadge(ctx, canvas.width, canvas.height, promoBadge);
    renderWatermark(ctx, canvas.width, canvas.height, watermark);

    // 5. Guides & Transform Handles
    if (showGrid) {
      ctx.save();
      ctx.strokeStyle = 'rgba(148, 163, 184, 0.4)';
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

    if (showHandles && !splitSliderEnabled) {
      renderBoundingBox(ctx, drawX, drawY, drawW, drawH);
    }
  }, [
    loadedImg,
    origImg,
    preset,
    shadow,
    adjustments,
    promoBadge,
    watermark,
    transform,
    bgMode,
    showSafeZone,
    showGrid,
    showHandles,
    splitSliderEnabled,
    splitPos,
    asset?.hasBackgroundRemoved,
  ]);

  // Handle Mouse Events for Dragging Product & Split Slider
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mouseX = (e.clientX - rect.left) * (canvas.width / rect.width);
    const mouseY = (e.clientY - rect.top) * (canvas.height / rect.height);

    if (splitSliderEnabled) {
      const splitX = canvas.width * splitPos;
      if (Math.abs(mouseX - splitX) < 40) {
        setIsDraggingSlider(true);
        return;
      }
    }

    setIsDraggingProduct(true);
    setDragStart({ x: e.clientX, y: e.clientY });
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    if (isDraggingSlider) {
      const rect = canvas.getBoundingClientRect();
      const rawX = e.clientX - rect.left;
      const newPos = Math.max(0.05, Math.min(0.95, rawX / rect.width));
      setSplitPos(newPos);
      return;
    }

    if (isDraggingProduct) {
      const dx = (e.clientX - dragStart.x) / zoom;
      const dy = (e.clientY - dragStart.y) / zoom;
      onTransformChange({
        ...transform,
        offsetX: transform.offsetX + dx,
        offsetY: transform.offsetY + dy,
      });
      setDragStart({ x: e.clientX, y: e.clientY });
    }
  };

  const handleMouseUp = () => {
    setIsDraggingSlider(false);
    setIsDraggingProduct(false);
  };

  return (
    <div className="flex-1 flex flex-col bg-slate-100 overflow-hidden relative select-none">
      {/* Top Floating Viewport Toolbar */}
      <div className="h-11 border-b border-surface-border bg-surface-light px-4 flex items-center justify-between z-10 shadow-2xs">
        {/* Preset Info */}
        <div className="flex items-center gap-2 text-xs">
          <span className="font-bold text-slate-800">{preset.name_vi}</span>
          <span className="text-slate-300">|</span>
          <span className="text-slate-500 font-mono text-[11px]">
            {preset.width} × {preset.height} px ({preset.aspect_ratio})
          </span>
        </div>

        {/* View Controls */}
        <div className="flex items-center gap-2">
          {/* Before/After Split Slider Toggle */}
          <button
            onClick={() => setSplitSliderEnabled(!splitSliderEnabled)}
            className={`px-2.5 py-1 rounded text-xs flex items-center gap-1.5 font-medium transition-all ${
              splitSliderEnabled
                ? 'bg-kroma-600 text-white shadow-2xs'
                : 'text-slate-600 hover:text-slate-900 bg-surface-subtle border border-surface-border'
            }`}
            title={t.split_slider}
          >
            <SplitSquareVertical className="w-3.5 h-3.5" />
            <span className="text-[11px]">So sánh Before/After</span>
          </button>

          {/* Transform handles toggle */}
          <button
            onClick={() => setShowHandles(!showHandles)}
            className={`p-1.5 rounded transition-colors ${
              showHandles
                ? 'bg-slate-200 text-slate-900'
                : 'text-slate-500 hover:text-slate-800'
            }`}
            title={t.show_handles}
          >
            <Move className="w-3.5 h-3.5" />
          </button>

          {/* Reset position button */}
          {(transform.offsetX !== 0 || transform.offsetY !== 0 || transform.scale !== 1) && (
            <button
              onClick={() => onTransformChange({ offsetX: 0, offsetY: 0, scale: 1 })}
              className="p-1.5 text-slate-500 hover:text-slate-900 rounded"
              title="Đặt lại vị trí căn giữa"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          )}

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

          {/* Studio Backdrops */}
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
              onClick={() => setBgMode('warm')}
              className={`px-1.5 py-0.5 text-[10px] font-medium rounded transition-colors ${
                bgMode === 'warm' ? 'bg-white shadow-xs text-slate-900' : 'text-slate-500'
              }`}
              title="Studio Podium"
            >
              Podium
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

      {/* Interactive Center Stage */}
      <div
        className="flex-1 flex items-center justify-center p-8 overflow-auto relative"
        onMouseUp={handleMouseUp}
      >
        {isRemovingBg && (
          <div className="absolute inset-0 bg-white/75 backdrop-blur-xs flex flex-col items-center justify-center z-30 gap-2.5">
            <div className="w-9 h-9 rounded-full border-3 border-kroma-600 border-t-transparent animate-spin" />
            <p className="text-xs font-bold text-slate-800">{t.removing_bg}</p>
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
              transition: isDraggingProduct || isDraggingSlider ? 'none' : 'transform 0.1s ease-out',
            }}
            className="shadow-2xl rounded-lg overflow-hidden border border-slate-300 relative bg-white"
          >
            <canvas
              ref={canvasRef}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              className={`block max-w-none ${
                splitSliderEnabled
                  ? 'cursor-ew-resize'
                  : isDraggingProduct
                  ? 'cursor-grabbing'
                  : 'cursor-grab'
              }`}
            />
          </div>
        )}
      </div>
    </div>
  );
};
