'use client';

import React, { useRef } from 'react';
import { UploadCloud, Sparkles, Trash2, CheckCircle2, ShoppingBag } from 'lucide-react';
import { ImageAsset } from '@/lib/types';
import { Language, translations } from '@/lib/i18n';

interface SidebarLeftProps {
  lang: Language;
  assets: ImageAsset[];
  selectedId: string | null;
  onSelectAsset: (id: string) => void;
  onUploadAssets: (files: FileList) => void;
  onRemoveAsset: (id: string) => void;
  onSelectSampleProduct: (sample: ImageAsset) => void;
}

export const SAMPLE_PRODUCTS: ImageAsset[] = [
  {
    id: 'sample_sneaker',
    name: 'Giày Thể Thao Pro Air',
    category: 'Thời trang & Giày dép',
    originalUrl: '/assets/samples/sneaker_air_pro.svg',
    width: 1024,
    height: 1024,
    sizeBytes: 185000,
    hasBackgroundRemoved: true,
    isSample: true,
  },
  {
    id: 'sample_perfume',
    name: 'Nước Hoa Cao Cấp Kroma',
    category: 'Nước hoa & Mỹ phẩm',
    originalUrl: '/assets/samples/perfume_nocturne.svg',
    width: 1024,
    height: 1024,
    sizeBytes: 210000,
    hasBackgroundRemoved: true,
    isSample: true,
  },
  {
    id: 'sample_watch',
    name: 'Đồng Hồ Chronograph Nam',
    category: 'Phụ kiện cao cấp',
    originalUrl: '/assets/samples/chronograph_watch.svg',
    width: 1024,
    height: 1024,
    sizeBytes: 195000,
    hasBackgroundRemoved: true,
    isSample: true,
  },
  {
    id: 'sample_skincare',
    name: 'Serum Dưỡng Trắng B5',
    category: 'Chăm sóc da',
    originalUrl: '/assets/samples/skincare_serum.svg',
    width: 1024,
    height: 1024,
    sizeBytes: 160000,
    hasBackgroundRemoved: true,
    isSample: true,
  },
  {
    id: 'sample_bag',
    name: 'Túi Xách Da Công Sở',
    category: 'Túi xách & Ví',
    originalUrl: '/assets/samples/leather_handbag.svg',
    width: 1024,
    height: 1024,
    sizeBytes: 240000,
    hasBackgroundRemoved: true,
    isSample: true,
  },
];

export const SidebarLeft: React.FC<SidebarLeftProps> = ({
  lang,
  assets,
  selectedId,
  onSelectAsset,
  onUploadAssets,
  onRemoveAsset,
  onSelectSampleProduct,
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
    <aside className="w-72 border-r border-surface-border bg-surface-subtle flex flex-col h-[calc(100vh-3.5rem)] select-none">
      {/* Header */}
      <div className="p-3 border-b border-surface-border flex items-center justify-between">
        <span className="text-xs font-bold text-slate-800 uppercase tracking-wider">
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
          className="cursor-pointer border-2 border-dashed border-slate-300 hover:border-kroma-500 rounded-lg p-3 text-center bg-surface-light hover:bg-kroma-50/40 transition-all flex flex-col items-center gap-1"
        >
          <UploadCloud className="w-5 h-5 text-kroma-600" />
          <span className="text-xs font-semibold text-slate-800">{t.new_upload}</span>
          <span className="text-[10px] text-slate-400">PNG, JPG, WebP</span>
        </div>
      </div>

      {/* Pre-loaded Sample Products for Instant Testing */}
      <div className="p-3 border-b border-surface-border bg-surface-light">
        <div className="flex items-center gap-1.5 mb-2">
          <ShoppingBag className="w-3.5 h-3.5 text-kroma-600" />
          <span className="text-[11px] font-bold text-slate-700 uppercase tracking-wide">
            {t.sample_products}
          </span>
        </div>
        <div className="grid grid-cols-5 gap-1.5">
          {SAMPLE_PRODUCTS.map((prod) => (
            <button
              key={prod.id}
              onClick={() => onSelectSampleProduct(prod)}
              className="w-11 h-11 rounded-md border border-slate-200 hover:border-kroma-600 bg-slate-50 p-1 flex items-center justify-center transition-all hover:scale-105 shadow-2xs"
              title={`${prod.name} (${prod.category})`}
            >
              <img
                src={prod.originalUrl}
                alt={prod.name}
                className="w-full h-full object-contain"
              />
            </button>
          ))}
        </div>
      </div>

      {/* Asset List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
        {assets.map((asset) => {
          const isSelected = asset.id === selectedId;
          return (
            <div
              key={asset.id}
              onClick={() => onSelectAsset(asset.id)}
              className={`group relative flex items-center gap-2.5 p-2 rounded-lg cursor-pointer border transition-all ${
                isSelected
                  ? 'bg-kroma-50/80 border-kroma-500 text-kroma-950 shadow-xs'
                  : 'bg-surface-light border-surface-border hover:border-slate-300 text-slate-700'
              }`}
            >
              {/* Thumbnail */}
              <div className="w-12 h-12 rounded overflow-hidden bg-slate-100 border border-slate-200 shrink-0 flex items-center justify-center relative">
                <img
                  src={asset.processedUrl || asset.originalUrl}
                  alt={asset.name}
                  className="w-full h-full object-contain"
                />
                {asset.hasBackgroundRemoved && (
                  <span
                    className="absolute bottom-0.5 right-0.5 w-2.5 h-2.5 rounded-full bg-emerald-500 ring-1 ring-white"
                    title="Đã tách nền sạch"
                  />
                )}
              </div>

              {/* Metadata */}
              <div className="flex-1 min-w-0 pr-2">
                <p className="text-xs font-semibold truncate text-slate-800">{asset.name}</p>
                {asset.category && (
                  <p className="text-[10px] text-kroma-700 font-medium truncate">{asset.category}</p>
                )}
                <p className="text-[10px] text-slate-400 font-mono">
                  {asset.width} × {asset.height} px
                </p>
              </div>

              {/* Remove button */}
              {assets.length > 1 && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onRemoveAsset(asset.id);
                  }}
                  className="opacity-0 group-hover:opacity-100 p-1 text-slate-400 hover:text-rose-600 rounded transition-opacity"
                  title="Xóa"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          );
        })}
      </div>
    </aside>
  );
};
