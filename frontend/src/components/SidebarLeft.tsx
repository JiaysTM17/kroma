'use client';

import React, { useRef } from 'react';
import { UploadCloud, Image as ImageIcon, Trash2, CheckCircle2 } from 'lucide-react';
import { ImageAsset } from '@/lib/types';
import { Language, translations } from '@/lib/i18n';

interface SidebarLeftProps {
  lang: Language;
  assets: ImageAsset[];
  selectedId: string | null;
  onSelectAsset: (id: string) => void;
  onUploadAssets: (files: FileList) => void;
  onRemoveAsset: (id: string) => void;
}

export const SidebarLeft: React.FC<SidebarLeftProps> = ({
  lang,
  assets,
  selectedId,
  onSelectAsset,
  onUploadAssets,
  onRemoveAsset,
}) => {
  const t = translations[lang];
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      onUploadAssets(e.dataTransfer.files);
    }
  };

  return (
    <aside className="w-64 border-r border-surface-border bg-surface-subtle flex flex-col h-[calc(100vh-3.5rem)] select-none">
      {/* Header */}
      <div className="p-3 border-b border-surface-border flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
          {t.batch_queue} ({assets.length})
        </span>
      </div>

      {/* Upload Dropzone */}
      <div className="p-3 border-b border-surface-border">
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept="image/png,image/jpeg,image/webp"
          className="hidden"
          onChange={(e) => {
            if (e.target.files) onUploadAssets(e.target.files);
          }}
        />
        <div
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className="cursor-pointer border border-dashed border-slate-300 hover:border-kroma-500 rounded p-4 text-center bg-surface-light hover:bg-kroma-50/30 transition-all flex flex-col items-center gap-1.5"
        >
          <UploadCloud className="w-5 h-5 text-kroma-600" />
          <span className="text-xs font-medium text-slate-700">{t.new_upload}</span>
          <span className="text-[10px] text-slate-400">PNG, JPG, WebP</span>
        </div>
      </div>

      {/* Asset Thumbnails List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
        {assets.length === 0 ? (
          <div className="py-12 text-center text-xs text-slate-400">
            Chưa có ảnh nào được tải lên
          </div>
        ) : (
          assets.map((asset) => {
            const isSelected = asset.id === selectedId;
            return (
              <div
                key={asset.id}
                onClick={() => onSelectAsset(asset.id)}
                className={`group relative flex items-center gap-2.5 p-2 rounded cursor-pointer border transition-all ${
                  isSelected
                    ? 'bg-kroma-50/60 border-kroma-400 text-kroma-900 shadow-xs'
                    : 'bg-surface-light border-surface-border hover:border-slate-300 text-slate-700'
                }`}
              >
                {/* Thumbnail */}
                <div className="w-12 h-12 rounded overflow-hidden bg-slate-100 border border-slate-200 shrink-0 flex items-center justify-center relative">
                  <img
                    src={asset.originalUrl}
                    alt={asset.name}
                    className="w-full h-full object-contain"
                  />
                  {asset.hasBackgroundRemoved && (
                    <span className="absolute bottom-0.5 right-0.5 w-2 h-2 rounded-full bg-emerald-500 ring-1 ring-white" />
                  )}
                </div>

                {/* Metadata */}
                <div className="flex-1 min-w-0 pr-4">
                  <p className="text-xs font-medium truncate text-slate-800">{asset.name}</p>
                  <p className="text-[10px] text-slate-400">
                    {asset.width} × {asset.height} px
                  </p>
                  <p className="text-[10px] text-slate-400">
                    {(asset.sizeBytes / 1024).toFixed(1)} KB
                  </p>
                </div>

                {/* Delete button */}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onRemoveAsset(asset.id);
                  }}
                  className="opacity-0 group-hover:opacity-100 p-1 text-slate-400 hover:text-rose-500 rounded transition-opacity"
                  title="Xoá ảnh"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
};
