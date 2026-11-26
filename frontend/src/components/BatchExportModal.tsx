'use client';

import React, { useState } from 'react';
import JSZip from 'jszip';
import { X, Download, Check, FileArchive } from 'lucide-react';
import { ImageAsset, MarketplacePreset, ShadowConfig, AdjustmentValues } from '@/lib/types';
import { applyFloat32Adjustments, renderShadow } from '@/lib/canvasPipeline';

interface BatchExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  assets: ImageAsset[];
  preset: MarketplacePreset;
  shadow: ShadowConfig;
  adjustments: AdjustmentValues;
}

export const BatchExportModal: React.FC<BatchExportModalProps> = ({
  isOpen,
  onClose,
  assets,
  preset,
  shadow,
  adjustments,
}) => {
  const [format, setFormat] = useState<'webp' | 'png' | 'jpeg'>('webp');
  const [quality, setQuality] = useState<number>(0.92);
  const [isExporting, setIsExporting] = useState<boolean>(false);
  const [progress, setProgress] = useState<number>(0);

  if (!isOpen) return null;

  const handleExportZip = async () => {
    setIsExporting(true);
    setProgress(0);

    const zip = new JSZip();
    const folder = zip.folder(`kroma_${preset.marketplace.toLowerCase()}_export`);

    const canvas = document.createElement('canvas');
    canvas.width = preset.width;
    canvas.height = preset.height;
    const ctx = canvas.getContext('2d');

    if (!ctx || !folder) {
      setIsExporting(false);
      return;
    }

    for (let i = 0; i < assets.length; i++) {
      const asset = assets[i];

      // Draw composite
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Background
      if (format === 'jpeg' || preset.background_rgb) {
        ctx.fillStyle = '#FFFFFF';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
      }

      // Load image
      await new Promise<void>((resolve) => {
        const img = new Image();
        img.crossOrigin = 'anonymous';
        img.onload = () => {
          const scaleRatio = preset.subject_area_ratio || 0.82;
          const maxSubjectW = canvas.width * scaleRatio;
          const maxSubjectH = canvas.height * scaleRatio;
          const imgAspect = img.width / img.height;
          let drawW = maxSubjectW;
          let drawH = drawW / imgAspect;

          if (drawH > maxSubjectH) {
            drawH = maxSubjectH;
            drawW = drawH * imgAspect;
          }

          const drawX = (canvas.width - drawW) / 2;
          const drawY = (canvas.height - drawH) / 2 + (canvas.height * 0.02);

          // Shadow
          if (asset.hasBackgroundRemoved) {
            renderShadow(ctx, img, drawX, drawY, drawW, drawH, shadow);
          }

          // Offscreen adjustments
          const off = document.createElement('canvas');
          off.width = Math.round(drawW);
          off.height = Math.round(drawH);
          const offCtx = off.getContext('2d');
          if (offCtx) {
            offCtx.drawImage(img, 0, 0, drawW, drawH);
            const imgData = offCtx.getImageData(0, 0, off.width, off.height);
            applyFloat32Adjustments(imgData, adjustments);
            offCtx.putImageData(imgData, 0, 0);
            ctx.drawImage(off, drawX, drawY, drawW, drawH);
          }
          resolve();
        };
        img.src = asset.processedUrl || asset.originalUrl;
      });

      // Export canvas to blob
      const mime = format === 'webp' ? 'image/webp' : format === 'png' ? 'image/png' : 'image/jpeg';
      const blob = await new Promise<Blob | null>((resolve) => {
        canvas.toBlob((b) => resolve(b), mime, quality);
      });

      if (blob) {
        const ext = format === 'jpeg' ? 'jpg' : format;
        const cleanName = asset.name.replace(/\.[^/.]+$/, '');
        folder.file(`${cleanName}_${preset.id}.${ext}`, blob);
      }

      setProgress(Math.round(((i + 1) / assets.length) * 100));
    }

    // Generate ZIP file and trigger browser download
    const content = await zip.generateAsync({ type: 'blob' });
    const url = URL.createObjectURL(content);
    const link = document.createElement('a');
    link.href = url;
    link.download = `kroma_export_${preset.id}_${Date.now()}.zip`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    setIsExporting(false);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4">
      <div className="w-full max-w-md rounded-lg bg-surface-light border border-surface-border shadow-2xl overflow-hidden select-none">
        {/* Header */}
        <div className="p-4 border-b border-surface-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FileArchive className="w-5 h-5 text-kroma-600" />
            <h3 className="text-sm font-bold text-slate-900">Xuất ảnh hàng loạt (Batch Export)</h3>
          </div>
          <button onClick={onClose} className="p-1 text-slate-400 hover:text-slate-600 rounded">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="p-4 space-y-4 text-xs">
          <div>
            <label className="font-semibold text-slate-700 block mb-1">Quy chuẩn xuất theo sàn:</label>
            <div className="p-2.5 rounded bg-slate-50 border border-slate-200">
              <p className="font-bold text-slate-800">{preset.name_vi}</p>
              <p className="text-slate-500 font-mono text-[11px] mt-0.5">
                {preset.width} × {preset.height} px ({preset.aspect_ratio})
              </p>
            </div>
          </div>

          <div>
            <label className="font-semibold text-slate-700 block mb-1">Định dạng file xuất:</label>
            <div className="grid grid-cols-3 gap-2">
              {(['webp', 'png', 'jpeg'] as const).map((fmt) => (
                <button
                  key={fmt}
                  onClick={() => setFormat(fmt)}
                  className={`p-2 rounded border font-medium uppercase text-center transition-all ${
                    format === fmt
                      ? 'border-kroma-600 bg-kroma-50 text-kroma-900 font-bold'
                      : 'border-slate-200 hover:border-slate-300 text-slate-600'
                  }`}
                >
                  {fmt}
                </button>
              ))}
            </div>
          </div>

          {format !== 'png' && (
            <div>
              <div className="flex justify-between font-semibold text-slate-700 mb-1">
                <span>Chất lượng nén:</span>
                <span className="font-mono">{Math.round(quality * 100)}%</span>
              </div>
              <input
                type="range"
                min="0.7"
                max="1"
                step="0.05"
                value={quality}
                onChange={(e) => setQuality(Number(e.target.value))}
                className="w-full accent-kroma-600 cursor-pointer"
              />
            </div>
          )}

          {isExporting && (
            <div className="space-y-1 pt-2">
              <div className="flex justify-between text-slate-600">
                <span>Đang render nén ảnh...</span>
                <span className="font-mono">{progress}%</span>
              </div>
              <div className="w-full h-2 bg-slate-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-kroma-600 transition-all duration-150"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-surface-border bg-surface-subtle flex justify-end gap-2">
          <button
            onClick={onClose}
            disabled={isExporting}
            className="px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-200 rounded border border-slate-300 transition-colors"
          >
            Hủy
          </button>
          <button
            onClick={handleExportZip}
            disabled={isExporting || assets.length === 0}
            className="px-4 py-1.5 text-xs font-semibold text-white bg-kroma-600 hover:bg-kroma-700 rounded shadow-xs transition-colors flex items-center gap-1.5 disabled:opacity-50"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Tải file ZIP ({assets.length} ảnh)</span>
          </button>
        </div>
      </div>
    </div>
  );
};
