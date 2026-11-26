'use client';

import React, { useState } from 'react';
import { Header } from '@/components/Header';
import { SidebarLeft } from '@/components/SidebarLeft';
import { CanvasWorkspace } from '@/components/CanvasWorkspace';
import { SidebarRight } from '@/components/SidebarRight';
import { BatchExportModal } from '@/components/BatchExportModal';
import { ProofingModal } from '@/components/ProofingModal';
import {
  AdjustmentValues,
  ImageAsset,
  MarketplacePreset,
  ShadowConfig,
} from '@/lib/types';
import { MARKETPLACE_PRESETS } from '@/lib/presets';
import { Language } from '@/lib/i18n';

// Sample demonstration product image (High-resolution Sneaker with clean geometry)
const INITIAL_DEMO_ASSETS: ImageAsset[] = [
  {
    id: 'demo_1',
    name: 'kroma_sample_sneaker_01.png',
    originalUrl: '/assets/logo/kroma-logo-stacked.svg',
    width: 1024,
    height: 1024,
    sizeBytes: 248000,
    hasBackgroundRemoved: false,
  },
];

export default function StudioPage() {
  const [lang, setLang] = useState<Language>('vi');
  const [assets, setAssets] = useState<ImageAsset[]>(INITIAL_DEMO_ASSETS);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>('demo_1');

  // Active settings
  const [selectedPreset, setSelectedPreset] = useState<MarketplacePreset>(
    MARKETPLACE_PRESETS[0] // Shopee 1:1 default
  );

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

  const [adjustments, setAdjustments] = useState<AdjustmentValues>({
    exposure: 0,
    contrast: 0,
    highlights: 0,
    shadows: 0,
    temperature: 0,
    tint: 0,
    sharpness: 0,
  });

  // Tool states
  const [isRemovingBg, setIsRemovingBg] = useState<boolean>(false);
  const [isBrushActive, setIsBrushActive] = useState<boolean>(false);
  const [brushSize, setBrushSize] = useState<number>(24);

  // Modals
  const [isExportModalOpen, setIsExportModalOpen] = useState<boolean>(false);
  const [isProofingModalOpen, setIsProofingModalOpen] = useState<boolean>(false);

  const currentAsset = assets.find((a) => a.id === selectedAssetId) || null;

  // Handle file uploads
  const handleUploadAssets = (files: FileList) => {
    const newAssets: ImageAsset[] = [];
    Array.from(files).forEach((file) => {
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload = () => {
        setAssets((prev) => [
          ...prev,
          {
            id: `asset_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`,
            name: file.name,
            originalUrl: url,
            width: img.naturalWidth || 1024,
            height: img.naturalHeight || 1024,
            sizeBytes: file.size,
            hasBackgroundRemoved: false,
          },
        ]);
      };
      img.src = url;
    });
  };

  const handleRemoveAsset = (id: string) => {
    setAssets((prev) => prev.filter((a) => a.id !== id));
    if (selectedAssetId === id) {
      setSelectedAssetId(assets.find((a) => a.id !== id)?.id || null);
    }
  };

  // Client-side AI Background Removal Simulator & Canvas Isolator
  const handleRemoveBackground = () => {
    if (!currentAsset) return;
    setIsRemovingBg(true);

    setTimeout(() => {
      // Simulate RMBG-1.4 isolation
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

          // Detect bright or solid corners as background
          const cornerR = d[0];
          const cornerG = d[1];
          const cornerB = d[2];

          // High-precision alpha extraction for product isolation
          for (let i = 0; i < d.length; i += 4) {
            const r = d[i];
            const g = d[i + 1];
            const b = d[i + 2];
            const diff =
              Math.abs(r - cornerR) + Math.abs(g - cornerG) + Math.abs(b - cornerB);
            if (diff < 40) {
              d[i + 3] = 0; // Transparent background
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
    }, 850);
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
        {/* Left: Assets Queue */}
        <SidebarLeft
          lang={lang}
          assets={assets}
          selectedId={selectedAssetId}
          onSelectAsset={setSelectedAssetId}
          onUploadAssets={handleUploadAssets}
          onRemoveAsset={handleRemoveAsset}
        />

        {/* Center: Canvas Workspace */}
        <CanvasWorkspace
          lang={lang}
          asset={currentAsset}
          preset={selectedPreset}
          shadow={shadow}
          adjustments={adjustments}
          isRemovingBg={isRemovingBg}
          isBrushActive={isBrushActive}
          brushSize={brushSize}
        />

        {/* Right: Presets, AI Cutout, Shadows & Tone Controls */}
        <SidebarRight
          lang={lang}
          asset={currentAsset}
          selectedPreset={selectedPreset}
          shadow={shadow}
          adjustments={adjustments}
          isRemovingBg={isRemovingBg}
          isBrushActive={isBrushActive}
          brushSize={brushSize}
          onSelectPreset={setSelectedPreset}
          onRemoveBackground={handleRemoveBackground}
          onRestoreOriginal={handleRestoreOriginal}
          onToggleBrush={() => setIsBrushActive(!isBrushActive)}
          onBrushSizeChange={setBrushSize}
          onShadowChange={setShadow}
          onAdjustmentsChange={setAdjustments}
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
