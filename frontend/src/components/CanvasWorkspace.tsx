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
  LayoutGrid,
  Image as ImageIcon,
  Check,
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
  renderCenterSnapGuides,
  renderPromoBadge,
  renderShadow,
  renderSplitDivider,
  renderWatermark,
} from '@/lib/canvasPipeline';
import { Language, translations } from '@/lib/i18n';
import { EmptyCanvasState } from '@/components/EmptyCanvasState';

interface CanvasWorkspaceProps {
  lang: Language;
  asset: ImageAsset | null;
  assets?: ImageAsset[];
  onSelectAsset?: (id: string) => void;
  onUploadAssets: (files: FileList) => void;
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
  assets = [],
  onSelectAsset,
  onUploadAssets,
  preset,
  shadow,
  adjustments,
  promoBadge,
  watermark,
  transform,
  onTransformChange,
  isRemovingBg,
}) => {
  const t = translations[lang];
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const safeTransform = {
    offsetX: transform?.offsetX ?? 0,
    offsetY: transform?.offsetY ?? 0,
    scale: transform?.scale ?? 1,
  };

  const [viewMode, setViewMode] = useState<'editor' | 'gallery'>('editor');
  const [zoom, setZoom] = useState(1);
  const [bgMode, setBgMode] = useState<'white' | 'dark' | 'checker' | 'warm'>('white');
  const [showSafeZone, setShowSafeZone] = useState(true);
  const [showGrid, setShowGrid] = useState(false);
  const [showHandles, setShowHandles] = useState(true);
  const [splitSliderEnabled, setSplitSliderEnabled] = useState(false);
  const [splitPos, setSplitPos] = useState(0.5);

  const [isDraggingProduct, setIsDraggingProduct] = useState(false);
  const [isDraggingSlider, setIsDraggingSlider] = useState(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

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
    if (!canvas || !asset) return;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    if (!ctx) return;

    canvas.width = preset.width;
    canvas.height = preset.height;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (bgMode === 'white') {
      ctx.fillStyle = '#FFFFFF';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    } else if (bgMode === 'dark') {
      ctx.fillStyle = '#0F172A';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    } else if (bgMode === 'warm') {
      const grad = ctx.createLinearGradient(0, 0, 0, canvas.height);
      grad.addColorStop(0, '#FAFAFA');
      grad.addColorStop(0.7, '#F4F4F5');
      grad.addColorStop(1, '#E4E4E7');
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      ctx.save();
      ctx.fillStyle = '#E4E4E7';
      ctx.beginPath();
      ctx.ellipse(
        canvas.width / 2,
        canvas.height * 0.88,
        canvas.width * 0.38,
        canvas.height * 0.08,
        0,
        0,
        Math.PI * 2
      );
      ctx.fill();
      ctx.restore();
    } else {
      const size = 20;
      for (let y = 0; y < canvas.height; y += size) {
        for (let x = 0; x < canvas.width; x += size) {
          ctx.fillStyle = (x / size + y / size) % 2 === 0 ? '#FFFFFF' : '#E4E4E7';
          ctx.fillRect(x, y, size, size);
        }
      }
    }

    if (!loadedImg) return;

    const scaleRatio = (preset.subject_area_ratio || 0.82) * safeTransform.scale;
    const maxSubjectW = canvas.width * scaleRatio;
    const maxSubjectH = canvas.height * scaleRatio;

    const imgAspect = loadedImg.width / loadedImg.height;
    let drawW = maxSubjectW;
    let drawH = drawW / imgAspect;

    if (drawH > maxSubjectH) {
      drawH = maxSubjectH;
      drawW = drawH * imgAspect;
    }

    const drawX = (canvas.width - drawW) / 2 + safeTransform.offsetX;
    const drawY = (canvas.height - drawH) / 2 + canvas.height * 0.02 + safeTransform.offsetY;

    const splitX = canvas.width * splitPos;

    if (splitSliderEnabled && origImg) {
      ctx.save();
      ctx.beginPath();
      ctx.rect(0, 0, splitX, canvas.height);
      ctx.clip();
      ctx.drawImage(origImg, drawX, drawY, drawW, drawH);
      ctx.restore();

      ctx.save();
      ctx.beginPath();
      ctx.rect(splitX, 0, canvas.width - splitX, canvas.height);
      ctx.clip();

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
      ctx.restore();

      renderSplitDivider(ctx, canvas.height, splitX);
    } else {
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

    renderPromoBadge(ctx, canvas.width, canvas.height, promoBadge);
    renderWatermark(ctx, canvas.width, canvas.height, watermark);

    if (showGrid) {
      ctx.save();
      ctx.strokeStyle = 'rgba(113, 113, 122, 0.45)';
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

    // Magnetic Snapping Guidelines when subject aligns with center
    const isSnapX = Math.abs(safeTransform.offsetX) < 4;
    const isSnapY = Math.abs(safeTransform.offsetY) < 4;
    if (isDraggingProduct && (isSnapX || isSnapY)) {
      renderCenterSnapGuides(ctx, canvas.width, canvas.height, isSnapX, isSnapY);
    }
  }, [
    asset,
    loadedImg,
    origImg,
    preset,
    shadow,
    adjustments,
    promoBadge,
    watermark,
    safeTransform.offsetX,
    safeTransform.offsetY,
    safeTransform.scale,
    bgMode,
    showSafeZone,
    showGrid,
    showHandles,
    splitSliderEnabled,
    splitPos,
  ]);

  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mouseX = (e.clientX - rect.left) * (canvas.width / rect.width);

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
      let nextX = safeTransform.offsetX + dx;
      let nextY = safeTransform.offsetY + dy;

      // Magnetic snap to center within 4px
      if (Math.abs(nextX) < 4) nextX = 0;
      if (Math.abs(nextY) < 4) nextY = 0;

      onTransformChange({
        offsetX: nextX,
        offsetY: nextY,
        scale: safeTransform.scale,
      });
      setDragStart({ x: e.clientX, y: e.clientY });
    }
  };

  const handleMouseUp = () => {
    setIsDraggingSlider(false);
    setIsDraggingProduct(false);
  };

  const isTransformed =
    safeTransform.offsetX !== 0 || safeTransform.offsetY !== 0 || safeTransform.scale !== 1;
  const hasAssets = assets.length > 0 && Boolean(asset);
  const presetName = lang === 'vi' ? preset.name_vi : preset.name_en;

  return (
    <main className="flex-1 min-w-0 flex flex-col bg-zinc-50 overflow-hidden relative select-none">
      {/* Adaptive Non-Overlapping Top Canvas Toolbar */}
      <div
        data-testid="canvas-top-toolbar"
        className="min-h-12 px-4 py-2 border-b border-surface-border bg-surface-light flex flex-wrap items-center justify-between gap-x-4 gap-y-2 z-10"
      >
        {/* Left Group: Mode Switcher + Active Preset Readout */}
        <div className="flex flex-wrap items-center gap-2 min-w-0 max-w-full">
          <div className="flex items-center rounded-lg border border-zinc-200 bg-zinc-100 p-1 gap-1 shrink-0 max-w-full">
            <button
              type="button"
              onClick={() => setViewMode('editor')}
              className={`flex items-center gap-2 px-3 py-1 rounded-md text-xs font-medium whitespace-nowrap transition-colors ${
                viewMode === 'editor'
                  ? 'bg-white text-zinc-900 shadow-sm'
                  : 'text-zinc-600 hover:text-zinc-900'
              }`}
            >
              <ImageIcon className="w-4 h-4 shrink-0" strokeWidth={1.5} />
              <span>{t.toolbar_canvas_studio}</span>
            </button>
            <button
              type="button"
              onClick={() => setViewMode('gallery')}
              className={`flex items-center gap-2 px-3 py-1 rounded-md text-xs font-medium whitespace-nowrap tabular-nums transition-colors ${
                viewMode === 'gallery'
                  ? 'bg-white text-zinc-900 shadow-sm'
                  : 'text-zinc-600 hover:text-zinc-900'
              }`}
            >
              <LayoutGrid className="w-4 h-4 shrink-0" strokeWidth={1.5} />
              <span>
                {t.toolbar_batch_grid} ({assets.length})
              </span>
            </button>
          </div>

          <div
            data-testid="toolbar-preset-info"
            className="flex items-center gap-2 min-w-0 max-w-full px-2 py-1 rounded-md bg-zinc-50 border border-zinc-200"
            title={presetName}
          >
            <span className="text-xs font-medium text-zinc-800 truncate">
              {preset.marketplace}
            </span>
            <span className="text-xs font-mono tabular-nums text-zinc-500 whitespace-nowrap shrink-0">
              {preset.width}×{preset.height} ({preset.aspect_ratio})
            </span>
          </div>
        </div>

        {/* Right Group: Editor Tools or Gallery Hint */}
        {viewMode === 'editor' ? (
          <div className="flex flex-wrap items-center gap-2 min-w-0 max-w-full">
            <button
              type="button"
              disabled={!hasAssets}
              onClick={() => setSplitSliderEnabled(!splitSliderEnabled)}
              className={`h-8 px-3 rounded-md text-xs font-medium border flex items-center gap-2 whitespace-nowrap transition-colors disabled:opacity-40 disabled:pointer-events-none ${
                splitSliderEnabled
                  ? 'bg-zinc-900 text-white border-zinc-900'
                  : 'bg-white text-zinc-700 border-zinc-200 hover:bg-zinc-100 hover:text-zinc-900'
              }`}
              title={t.split_slider}
            >
              <SplitSquareVertical className="w-4 h-4 shrink-0" strokeWidth={1.5} />
              <span>{t.toolbar_before_after}</span>
            </button>

            <button
              type="button"
              disabled={!hasAssets}
              onClick={() => setShowHandles(!showHandles)}
              className={`h-8 w-8 rounded-md border flex items-center justify-center transition-colors disabled:opacity-40 disabled:pointer-events-none ${
                showHandles
                  ? 'bg-zinc-900 text-white border-zinc-900'
                  : 'bg-white text-zinc-600 border-zinc-200 hover:bg-zinc-100 hover:text-zinc-900'
              }`}
              title={t.show_handles}
              aria-label={t.show_handles}
            >
              <Move className="w-4 h-4" strokeWidth={1.5} />
            </button>

            {hasAssets && isTransformed && (
              <button
                type="button"
                onClick={() => onTransformChange({ offsetX: 0, offsetY: 0, scale: 1 })}
                className="h-8 w-8 rounded-md border border-zinc-200 bg-white text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 flex items-center justify-center transition-colors"
                title={t.reset_transform}
                aria-label={t.reset_transform}
              >
                <RotateCcw className="w-4 h-4" strokeWidth={1.5} />
              </button>
            )}

            <button
              type="button"
              disabled={!hasAssets}
              onClick={() => setShowSafeZone(!showSafeZone)}
              className={`h-8 px-3 rounded-md text-xs font-medium border flex items-center whitespace-nowrap transition-colors disabled:opacity-40 disabled:pointer-events-none ${
                showSafeZone
                  ? 'bg-zinc-900 text-white border-zinc-900'
                  : 'bg-white text-zinc-700 border-zinc-200 hover:bg-zinc-100 hover:text-zinc-900'
              }`}
              title={t.safe_zone_toggle}
            >
              <span>{t.toolbar_safe_zone}</span>
            </button>

            <button
              type="button"
              disabled={!hasAssets}
              onClick={() => setShowGrid(!showGrid)}
              className={`h-8 w-8 rounded-md border flex items-center justify-center transition-colors disabled:opacity-40 disabled:pointer-events-none ${
                showGrid
                  ? 'bg-zinc-900 text-white border-zinc-900'
                  : 'bg-white text-zinc-600 border-zinc-200 hover:bg-zinc-100 hover:text-zinc-900'
              }`}
              title={t.grid_toggle}
              aria-label={t.grid_toggle}
            >
              <Grid3X3 className="w-4 h-4" strokeWidth={1.5} />
            </button>
          </div>
        ) : (
          <div className="text-xs text-zinc-500">
            {hasAssets ? t.toolbar_gallery_hint : t.empty_drop_title}
          </div>
        )}
      </div>

      {/* Main Content Area: Empty State, Gallery Grid, or Canvas Studio Stage */}
      {!hasAssets ? (
        <div
          data-testid="empty-canvas-scroll"
          className="flex-1 flex flex-col items-center p-4 sm:p-8 overflow-y-auto"
        >
          <EmptyCanvasState lang={lang} preset={preset} onUploadAssets={onUploadAssets} />
        </div>
      ) : viewMode === 'gallery' ? (
        <div className="flex-1 p-4 sm:p-6 overflow-y-auto bg-zinc-50">
          <div className="max-w-6xl mx-auto space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-zinc-200">
              <div>
                <h2 className="text-sm font-semibold text-zinc-900 tabular-nums">
                  {t.gallery_title} ({assets.length} {t.gallery_unit})
                </h2>
                <p className="text-xs text-zinc-500 mt-1 tabular-nums">
                  {t.gallery_preset_note}:{' '}
                  <span className="font-medium text-zinc-800">
                    {presetName} ({preset.width}×{preset.height})
                  </span>
                </p>
              </div>
              <span className="px-2 py-1 rounded-md text-xs font-medium bg-kroma-50 text-kroma-700 border border-kroma-200">
                {t.gallery_client_note}
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
              {assets.map((item) => {
                const isSelected = item.id === asset?.id;
                return (
                  <div
                    key={item.id}
                    onClick={() => {
                      if (onSelectAsset) onSelectAsset(item.id);
                      setViewMode('editor');
                    }}
                    className={`group rounded-xl border p-3 bg-white shadow-sm transition-[border-color,box-shadow] cursor-pointer flex flex-col justify-between ${
                      isSelected
                        ? 'border-kroma-600 ring-2 ring-kroma-600/20'
                        : 'border-zinc-200 hover:border-zinc-400'
                    }`}
                  >
                    <div>
                      <div className="w-full aspect-square bg-zinc-100 rounded-lg overflow-hidden flex items-center justify-center p-3 relative mb-3">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={item.processedUrl || item.originalUrl}
                          alt={item.name}
                          className="max-h-full max-w-full object-contain"
                        />
                        <div className="absolute top-2 right-2">
                          {item.hasBackgroundRemoved ? (
                            <span className="flex items-center gap-1 px-2 py-1 rounded text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                              <Check className="w-3 h-3" strokeWidth={1.5} />
                              <span>{t.gallery_cutout}</span>
                            </span>
                          ) : (
                            <span className="px-2 py-1 rounded text-xs font-medium bg-zinc-200 text-zinc-700">
                              {t.gallery_original}
                            </span>
                          )}
                        </div>
                      </div>

                      <h3 className="text-xs font-medium text-zinc-900 truncate mb-1">
                        {item.name}
                      </h3>
                      <p className="text-xs text-zinc-500 font-mono tabular-nums">
                        {item.width} × {item.height} px
                      </p>
                    </div>

                    <div className="mt-3 pt-2 border-t border-zinc-100 flex items-center justify-between">
                      <span className="text-xs font-medium text-kroma-600 group-hover:text-kroma-700">
                        {t.gallery_edit_action}
                      </span>
                      {isSelected && (
                        <span className="text-xs font-medium text-zinc-500">
                          {t.gallery_selected}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      ) : (
        /* Interactive Single Canvas Stage */
        <div
          className="flex-1 flex items-center justify-center p-4 sm:p-8 pb-20 overflow-auto relative"
          onMouseUp={handleMouseUp}
        >
          {isRemovingBg && (
            <div className="absolute inset-0 bg-white/80 backdrop-blur-sm flex flex-col items-center justify-center z-30 gap-3">
              <div className="w-8 h-8 rounded-full border-2 border-kroma-600 border-t-transparent animate-spin" />
              <p className="text-xs font-medium text-zinc-800">{t.removing_bg}</p>
            </div>
          )}

          <div
            style={{
              transform: `scale(${zoom})`,
              transformOrigin: 'center center',
              transition:
                isDraggingProduct || isDraggingSlider ? 'none' : 'transform 150ms cubic-bezier(0.22, 1, 0.36, 1)',
            }}
            className="max-w-full rounded-lg overflow-hidden border border-zinc-200 shadow-sm relative bg-white"
          >
            <canvas
              ref={canvasRef}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              style={{ aspectRatio: `${preset.width} / ${preset.height}` }}
              className={`block max-w-full max-h-[calc(100vh-14rem)] w-auto h-auto ${
                splitSliderEnabled
                  ? 'cursor-ew-resize'
                  : isDraggingProduct
                  ? 'cursor-grabbing'
                  : 'cursor-grab'
              }`}
            />
          </div>

          {/* Floating Bottom Canvas Dock (Studio Backdrops + Zoom) */}
          <div
            data-testid="canvas-bottom-dock"
            className="absolute bottom-4 left-1/2 -translate-x-1/2 max-w-[calc(100%-2rem)] overflow-x-auto z-20 flex items-center gap-1 sm:gap-2 px-2 py-1 rounded-xl bg-white/95 backdrop-blur-sm border border-zinc-200 shadow-sm"
          >
            {/* Studio Backdrops */}
            <div className="flex items-center bg-zinc-100 p-1 rounded-lg border border-zinc-200 gap-1 shrink-0">
              <button
                type="button"
                onClick={() => setBgMode('white')}
                className={`h-7 w-7 rounded-md flex items-center justify-center transition-colors ${
                  bgMode === 'white'
                    ? 'bg-white shadow-sm text-zinc-900'
                    : 'text-zinc-500 hover:text-zinc-900'
                }`}
                title={t.view_white}
                aria-label={t.view_white}
              >
                <Sun className="w-4 h-4" strokeWidth={1.5} />
              </button>
              <button
                type="button"
                onClick={() => setBgMode('dark')}
                className={`h-7 w-7 rounded-md flex items-center justify-center transition-colors ${
                  bgMode === 'dark'
                    ? 'bg-white shadow-sm text-zinc-900'
                    : 'text-zinc-500 hover:text-zinc-900'
                }`}
                title={t.view_dark}
                aria-label={t.view_dark}
              >
                <Moon className="w-4 h-4" strokeWidth={1.5} />
              </button>
              <button
                type="button"
                onClick={() => setBgMode('warm')}
                className={`h-7 px-2 rounded-md text-xs font-medium whitespace-nowrap transition-colors ${
                  bgMode === 'warm'
                    ? 'bg-white shadow-sm text-zinc-900'
                    : 'text-zinc-500 hover:text-zinc-900'
                }`}
                title={t.view_warm}
              >
                Podium
              </button>
              <button
                type="button"
                onClick={() => setBgMode('checker')}
                className={`h-7 px-2 rounded-md text-xs font-mono whitespace-nowrap transition-colors ${
                  bgMode === 'checker'
                    ? 'bg-white shadow-sm text-zinc-900'
                    : 'text-zinc-500 hover:text-zinc-900'
                }`}
                title={t.view_checkerboard}
              >
                PNG
              </button>
            </div>

            <div className="h-4 w-px bg-zinc-200 shrink-0" />

            {/* Zoom Controls */}
            <div className="flex items-center gap-1 shrink-0">
              <button
                type="button"
                onClick={() => setZoom((z) => Math.max(0.25, z - 0.15))}
                className="h-7 w-7 rounded-md text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100 flex items-center justify-center transition-colors"
                title={t.zoom_out}
                aria-label={t.zoom_out}
              >
                <ZoomOut className="w-4 h-4" strokeWidth={1.5} />
              </button>
              <span className="text-xs font-mono tabular-nums text-zinc-700 min-w-10 sm:min-w-12 text-center">
                {Math.round(zoom * 100)}%
              </span>
              <button
                type="button"
                onClick={() => setZoom((z) => Math.min(3, z + 0.15))}
                className="h-7 w-7 rounded-md text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100 flex items-center justify-center transition-colors"
                title={t.zoom_in}
                aria-label={t.zoom_in}
              >
                <ZoomIn className="w-4 h-4" strokeWidth={1.5} />
              </button>
              <button
                type="button"
                onClick={() => setZoom(1)}
                className="h-7 w-7 rounded-md text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100 flex items-center justify-center transition-colors"
                title={t.zoom_reset}
                aria-label={t.zoom_reset}
              >
                <Maximize2 className="w-4 h-4" strokeWidth={1.5} />
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
};
