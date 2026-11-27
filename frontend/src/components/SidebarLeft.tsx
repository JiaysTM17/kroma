'use client';

import React, { useRef, useState } from 'react';
import { UploadCloud, Trash2, X } from 'lucide-react';
import { ImageAsset } from '@/lib/types';
import { Language, translations } from '@/lib/i18n';

interface SidebarLeftProps {
  lang: Language;
  assets: ImageAsset[];
  selectedId: string | null;
  onSelectAsset: (id: string) => void;
  onUploadAssets: (files: FileList) => void;
  onRemoveAsset: (id: string) => void;
  isOpenMobile?: boolean;
  onCloseMobile?: () => void;
}

export const SidebarLeft: React.FC<SidebarLeftProps> = ({
  lang,
  assets,
  selectedId,
  onSelectAsset,
  onUploadAssets,
  onRemoveAsset,
  isOpenMobile = false,
  onCloseMobile,
}) => {
  const t = translations[lang];
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (!isDragOver) setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (!e.currentTarget.contains(e.relatedTarget as Node)) {
      setIsDragOver(false);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      onUploadAssets(e.dataTransfer.files);
    }
  };

  return (
    <aside
      aria-label={t.batch_queue}
      className={`fixed inset-y-14 left-0 z-30 w-72 lg:static lg:inset-auto lg:w-64 xl:w-72 shrink-0 border-r border-surface-border bg-surface-subtle flex flex-col lg:h-[calc(100vh-3.5rem)] select-none transition-transform duration-200 ${
        isOpenMobile ? 'translate-x-0 shadow-lg lg:shadow-none' : '-translate-x-full lg:translate-x-0'
      }`}
    >
      {/* Header */}
      <div className="px-4 py-3 border-b border-surface-border flex items-center justify-between gap-2">
        <span className="text-xs font-semibold text-zinc-800 tabular-nums">
          {t.batch_queue} ({assets.length})
        </span>
        {onCloseMobile && (
          <button
            type="button"
            onClick={onCloseMobile}
            aria-label={t.close_panel}
            className="lg:hidden p-1 rounded text-zinc-500 hover:text-zinc-900 hover:bg-zinc-200/70 transition-colors"
          >
            <X className="w-4 h-4" strokeWidth={1.5} />
          </button>
        )}
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
            if (e.target.files && e.target.files.length > 0) {
              onUploadAssets(e.target.files);
            }
            e.target.value = '';
          }}
        />
        <div
          role="button"
          tabIndex={0}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              fileInputRef.current?.click();
            }
          }}
          className={`cursor-pointer border border-dashed rounded-lg p-3 text-center transition-[border-color,background-color] flex flex-col items-center gap-1 focus:outline-none focus:ring-2 focus:ring-kroma-600/30 ${
            isDragOver
              ? 'border-kroma-600 bg-kroma-50/40'
              : 'border-zinc-300 bg-surface-light hover:border-zinc-400'
          }`}
        >
          <UploadCloud className="w-4 h-4 text-kroma-600" strokeWidth={1.5} />
          <span className="text-xs font-medium text-zinc-800">{t.new_upload}</span>
          <span className="text-xs font-mono text-zinc-400">PNG, JPG, WebP</span>
        </div>
      </div>

      {/* Asset List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {assets.length === 0 ? (
          <div className="rounded-lg border border-dashed border-zinc-200 bg-white/70 p-4 text-center">
            <p className="text-xs text-zinc-500 leading-relaxed">{t.empty_queue}</p>
          </div>
        ) : (
          assets.map((asset) => {
            const isSelected = asset.id === selectedId;
            return (
              <div
                key={asset.id}
                onClick={() => {
                  onSelectAsset(asset.id);
                  if (onCloseMobile) onCloseMobile();
                }}
                className={`group relative flex items-center gap-3 p-2 rounded-lg cursor-pointer border transition-[border-color,background-color] ${
                  isSelected
                    ? 'bg-kroma-50/70 border-kroma-500 text-kroma-950 shadow-sm'
                    : 'bg-surface-light border-surface-border hover:border-zinc-300 text-zinc-700'
                }`}
              >
                {/* Thumbnail */}
                <div className="w-12 h-12 rounded-md overflow-hidden bg-zinc-100 border border-zinc-200 shrink-0 flex items-center justify-center relative">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={asset.processedUrl || asset.originalUrl}
                    alt={asset.name}
                    className="w-full h-full object-contain"
                  />
                  {asset.hasBackgroundRemoved && (
                    <span
                      className="absolute bottom-1 right-1 w-2 h-2 rounded-full bg-emerald-500 ring-1 ring-white"
                      title={t.tab_cutout}
                    />
                  )}
                </div>

                {/* Metadata */}
                <div className="flex-1 min-w-0 pr-1">
                  <p className="text-xs font-medium truncate text-zinc-900">{asset.name}</p>
                  {asset.category && (
                    <p className="text-xs text-kroma-700 truncate">{asset.category}</p>
                  )}
                  <p className="text-xs text-zinc-400 font-mono tabular-nums">
                    {asset.width} × {asset.height} px
                  </p>
                </div>

                {/* Remove button (always allowed even for single remaining item) */}
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onRemoveAsset(asset.id);
                  }}
                  className="opacity-70 group-hover:opacity-100 focus:opacity-100 p-1 text-zinc-400 hover:text-rose-600 rounded transition-colors shrink-0"
                  title={t.remove_asset}
                  aria-label={`${t.remove_asset}: ${asset.name}`}
                >
                  <Trash2 className="w-4 h-4" strokeWidth={1.5} />
                </button>
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
};
