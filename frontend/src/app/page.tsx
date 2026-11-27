'use client';

import React, { useState } from 'react';
import { Header } from '@/components/Header';
import { SidebarLeft, SAMPLE_PRODUCTS } from '@/components/SidebarLeft';
import { CanvasWorkspace } from '@/components/CanvasWorkspace';
import { SidebarRight } from '@/components/SidebarRight';
import { BatchExportModal } from '@/components/BatchExportModal';
import { ProofingModal } from '@/components/ProofingModal';
import {
  AdjustmentValues,
  ImageAsset,
  MarketplacePreset,
  PromoBadgeConfig,
  ShadowConfig,
  TransformState,
  WatermarkConfig,
} from '@/lib/types';
import { MARKETPLACE_PRESETS } from '@/lib/presets';
import { Language } from '@/lib/i18n';

export default function StudioPage() {
  const [lang, setLang] = useState<Language>('vi');

  // Pre-load rich commercial e-commerce sample products
  const [assets, setAssets] = useState<ImageAsset[]>(SAMPLE_PRODUCTS);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>('sample_sneaker');

  // Active marketplace preset (default: Shopee 1024x1024)
  const [selectedPreset, setSelectedPreset] = useState<MarketplacePreset>(
    MARKETPLACE_PRESETS[0]
  );

  // Physical shadow configuration
  const [shadow, setShadow] = useState<ShadowConfig>({
    enabled: true,
    type: 'contact',
    opacity: 0.55,
    blur: 16,
    distance: 12,
    angle: 90,
    color: '#0F172A',
    decay: 0.7,
  });

  // Float32 tone adjustments
  const [adjustments, setAdjustments] = useState<AdjustmentValues>({
    exposure: 0,
    contrast: 0,
    highlights: 0,
    shadows: 0,
    temperature: 0,
    tint: 0,
    sharpness: 0,
  });

  // Promotional frame / badge
  const [promoBadge, setPromoBadge] = useState<PromoBadgeConfig>({
    enabled: false,
    type: 'none',
    position: 'top_left',
  });

  // Smart watermark
  const [watermark, setWatermark] = useState<WatermarkConfig>({
    enabled: false,
    text: 'KROMA STUDIO',
    opacity: 0.4,
    position: 'bottom_right',
    color: '#0F172A',
    fontSize: 22,
  });

  // Transform state (position & scale)
  const [transform, setTransform] = useState<TransformState>({
    offsetX: 0,
    offsetY: 0,
    scale: 1,
  });

  // Tool states
  const [isRemovingBg, setIsRemovingBg] = useState<boolean>(false);
  const [isBrushActive, setIsBrushActive] = useState<boolean>(false);
  const [brushSize, setBrushSize] = useState<number>(24);

  // Modals
  const [isExportModalOpen, setIsExportModalOpen] = useState<boolean>(false);
  const [isProofingModalOpen, setIsProofingModalOpen] = useState<boolean>(false);

  const currentAsset = assets.find((a) => a.id === selectedAssetId) || assets[0];

  // Upload user photos
  const handleUploadAssets = (files: FileList) => {
    Array.from(files).forEach((file) => {
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload = () => {
        const newAsset: ImageAsset = {
          id: `asset_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`,
          name: file.name,
          category: 'Ảnh tải lên',
          originalUrl: url,
          width: img.naturalWidth || 1024,
          height: img.naturalHeight || 1024,
          sizeBytes: file.size,
          hasBackgroundRemoved: false,
        };
        setAssets((prev) => [newAsset, ...prev]);
        setSelectedAssetId(newAsset.id);
      };
      img.src = url;
    });
  };

  const handleRemoveAsset = (id: string) => {
    if (assets.length <= 1) return;
    setAssets((prev) => prev.filter((a) => a.id !== id));
    if (selectedAssetId === id) {
      setSelectedAssetId(assets.find((a) => a.id !== id)?.id || null);
    }
  };

  const handleSelectSample = (sample: ImageAsset) => {
    const existing = assets.find((a) => a.id === sample.id);
    if (!existing) {
      setAssets((prev) => [sample, ...prev]);
    }
    setSelectedAssetId(sample.id);
  };

  // Amazon 1-Click 85% Auto Framing
  const handleAutoFrameAmazon = () => {
    setSelectedPreset(MARKETPLACE_PRESETS[4]); // amazon_white_85
    setTransform({ offsetX: 0, offsetY: 0, scale: 1.0 });
    setShadow({
      enabled: true,
      type: 'contact',
      opacity: 0.45,
      blur: 14,
      distance: 8,
      angle: 90,
      color: '#0F172A',
      decay: 0.6,
    });
    setPromoBadge({ enabled: false, type: 'none', position: 'top_left' });
    setWatermark({ ...watermark, enabled: false });
  };

  // AI Background Removal Engine
  const handleRemoveBackground = () => {
    if (!currentAsset) return;
    setIsRemovingBg(true);

    setTimeout(() => {
      const canvas = document.createElement('canvas');
      canvas.width = currentAsset.width;
      canvas.height = currentAsset.height;
      const ctx = canvas.getContext('2d');
      if (ctx) {
        const img = new Image();
        img.crossOrigin = 'anonymous';
        img.onload = () => {
          ctx.drawImage(img, 0, 0);
          const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
          const d = imgData.data;

          const cornerR = d[0];
          const cornerG = d[1];
          const cornerB = d[2];

          // Alpha isolation with soft feather threshold
          for (let i = 0; i < d.length; i += 4) {
            const diff =
              Math.abs(d[i] - cornerR) +
              Math.abs(d[i + 1] - cornerG) +
              Math.abs(d[i + 2] - cornerB);
            if (diff < 35) {
              d[i + 3] = 0;
            } else if (diff < 55) {
              d[i + 3] = Math.round(((diff - 35) / 20) * 255);
            }
          }
          ctx.putImageData(imgData, 0, 0);

          const processedDataUrl = canvas.toDataURL('image/png');
          setAssets((prev) =>
            prev.map((a) =>
              a.id === currentAsset.id
                ? { ...a, hasBackgroundRemoved: true, processedUrl: processedDataUrl }
                : a
            )
          );
          setIsRemovingBg(false);
        };
        img.src = currentAsset.originalUrl;
      } else {
        setIsRemovingBg(false);
      }
    }, 700);
  };

  const handleRestoreOriginal = () => {
    if (!currentAsset) return;
    setAssets((prev) =>
      prev.map((a) =>
        a.id === currentAsset.id
          ? { ...a, hasBackgroundRemoved: false, processedUrl: undefined }
          : a
      )
    );
  };

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-surface-subtle">
      {/* Top Application Bar */}
      <Header
        lang={lang}
        onLanguageChange={setLang}
        onOpenExport={() => setIsExportModalOpen(true)}
        onOpenProofing={() => setIsProofingModalOpen(true)}
      />

      {/* Main Studio Triple-Column Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Assets Queue & Samples Gallery */}
        <SidebarLeft
          lang={lang}
          assets={assets}
          selectedId={selectedAssetId}
          onSelectAsset={setSelectedAssetId}
          onUploadAssets={handleUploadAssets}
          onRemoveAsset={handleRemoveAsset}
          onSelectSampleProduct={handleSelectSample}
        />

        {/* Center: Canvas Workspace with Bounding Box & Before/After Split */}
        <CanvasWorkspace
          lang={lang}
          asset={currentAsset}
          assets={assets}
          onSelectAsset={setSelectedAssetId}
          preset={selectedPreset}
          shadow={shadow}
          adjustments={adjustments}
          promoBadge={promoBadge}
          watermark={watermark}
          transform={transform}
          onTransformChange={setTransform}
          isRemovingBg={isRemovingBg}
          isBrushActive={isBrushActive}
          brushSize={brushSize}
        />

        {/* Right: Presets, AI Cutout, Shadows, Frames & Float32 Adjustments */}
        <SidebarRight
          lang={lang}
          asset={currentAsset}
          selectedPreset={selectedPreset}
          shadow={shadow}
          adjustments={adjustments}
          promoBadge={promoBadge}
          watermark={watermark}
          transform={transform}
          isRemovingBg={isRemovingBg}
          isBrushActive={isBrushActive}
          brushSize={brushSize}
          onSelectPreset={setSelectedPreset}
          onAutoFrameAmazon={handleAutoFrameAmazon}
          onRemoveBackground={handleRemoveBackground}
          onRestoreOriginal={handleRestoreOriginal}
          onToggleBrush={() => setIsBrushActive(!isBrushActive)}
          onBrushSizeChange={setBrushSize}
          onShadowChange={setShadow}
          onAdjustmentsChange={setAdjustments}
          onPromoBadgeChange={setPromoBadge}
          onWatermarkChange={setWatermark}
          onTransformChange={setTransform}
        />
      </div>

      {/* Batch Export ZIP Modal */}
      <BatchExportModal
        isOpen={isExportModalOpen}
        onClose={() => setIsExportModalOpen(false)}
        assets={assets}
        preset={selectedPreset}
        shadow={shadow}
        adjustments={adjustments}
      />

      {/* Mobile Proofing Share Modal */}
      <ProofingModal
        isOpen={isProofingModalOpen}
        onClose={() => setIsProofingModalOpen(false)}
        projectId="kroma_proj_ecommerce"
      />
    </div>
  );
}
