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
  PromoBadgeConfig,
  ShadowConfig,
  TransformState,
  WatermarkConfig,
} from '@/lib/types';
import { MARKETPLACE_PRESETS } from '@/lib/presets';
import { Language } from '@/lib/i18n';

const ACCEPTED_MIME_TYPES = new Set(['image/png', 'image/jpeg', 'image/webp']);
const ACCEPTED_EXT_REGEX = /\.(png|jpe?g|webp)$/i;

export default function StudioPage() {
  const [lang, setLang] = useState<Language>('vi');
  const [mobilePanel, setMobilePanel] = useState<'none' | 'left' | 'right'>('none');

  // Empty initial state (zero preloaded sample products)
  const [assets, setAssets] = useState<ImageAsset[]>([]);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);

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

  const currentAsset: ImageAsset | null =
    assets.find((a) => a.id === selectedAssetId) ?? assets[0] ?? null;

  // Upload user photos with MIME/extension guard and error cleanup
  const handleUploadAssets = (files: FileList) => {
    Array.from(files).forEach((file) => {
      const isValidMime = ACCEPTED_MIME_TYPES.has(file.type.toLowerCase());
      const isValidExt = ACCEPTED_EXT_REGEX.test(file.name);
      if (!isValidMime && !isValidExt) return;

      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload = () => {
        const newAsset: ImageAsset = {
          id: `asset_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`,
          name: file.name,
          category: lang === 'vi' ? 'Ảnh tải lên' : 'Uploaded image',
          originalUrl: url,
          width: img.naturalWidth || 1024,
          height: img.naturalHeight || 1024,
          sizeBytes: file.size,
          hasBackgroundRemoved: false,
        };
        setAssets((prev) => [newAsset, ...prev]);
        setSelectedAssetId(newAsset.id);
      };
      img.onerror = () => {
        URL.revokeObjectURL(url);
      };
      img.src = url;
    });
  };

  const handleRemoveAsset = (id: string) => {
    setAssets((prev) => {
      const target = prev.find((a) => a.id === id);
      if (target) {
        if (target.originalUrl.startsWith('blob:')) {
          URL.revokeObjectURL(target.originalUrl);
        }
        if (target.processedUrl && target.processedUrl.startsWith('blob:')) {
          URL.revokeObjectURL(target.processedUrl);
        }
      }
      const remaining = prev.filter((a) => a.id !== id);
      if (selectedAssetId === id) {
        setSelectedAssetId(remaining[0]?.id ?? null);
      }
      return remaining;
    });
  };

  // Amazon 1-Click 85% Auto Framing
  const handleAutoFrameAmazon = () => {
    setSelectedPreset(MARKETPLACE_PRESETS[4]);
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
        img.onerror = () => {
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
        activeMobilePanel={mobilePanel}
        onToggleLeftPanel={() => setMobilePanel((p) => (p === 'left' ? 'none' : 'left'))}
        onToggleRightPanel={() => setMobilePanel((p) => (p === 'right' ? 'none' : 'right'))}
        assetCount={assets.length}
      />

      {/* Main Studio Responsive Workspace Shell */}
      <div className="flex-1 flex min-h-0 min-w-0 relative overflow-hidden">
        {/* Mobile/Tablet Drawer Backdrop */}
        {mobilePanel !== 'none' && (
          <div
            aria-hidden="true"
            onClick={() => setMobilePanel('none')}
            className="fixed inset-0 top-14 bg-zinc-900/30 z-20 lg:hidden"
          />
        )}

        {/* Left: Product Queue & Upload */}
        <SidebarLeft
          lang={lang}
          assets={assets}
          selectedId={selectedAssetId}
          onSelectAsset={setSelectedAssetId}
          onUploadAssets={handleUploadAssets}
          onRemoveAsset={handleRemoveAsset}
          isOpenMobile={mobilePanel === 'left'}
          onCloseMobile={() => setMobilePanel('none')}
        />

        {/* Center: Canvas Workspace */}
        <CanvasWorkspace
          lang={lang}
          asset={currentAsset}
          assets={assets}
          onSelectAsset={setSelectedAssetId}
          onUploadAssets={handleUploadAssets}
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

        {/* Right: Inspector & Tools */}
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
          isOpenMobile={mobilePanel === 'right'}
          onCloseMobile={() => setMobilePanel('none')}
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
