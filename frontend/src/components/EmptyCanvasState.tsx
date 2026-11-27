'use client';

import React, { useRef, useState } from 'react';
import { UploadCloud, ImagePlus, ScanLine, SlidersHorizontal } from 'lucide-react';
import { MarketplacePreset } from '@/lib/types';
import { Language, translations } from '@/lib/i18n';

interface EmptyCanvasStateProps {
  lang: Language;
  preset: MarketplacePreset;
  onUploadAssets: (files: FileList) => void;
}

export const EmptyCanvasState: React.FC<EmptyCanvasStateProps> = ({
  lang,
  preset,
  onUploadAssets,
}) => {
  const t = translations[lang];
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  const presetLabel = lang === 'vi' ? preset.name_vi : preset.name_en;
  const dimsLabel = `${preset.width}×${preset.height} px`;
  const tip2Text = t.empty_tip_2
    .replace('{preset}', presetLabel)
    .replace('{dims}', dimsLabel);

  const handleDragEnter = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (!isDragging) setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (!e.currentTarget.contains(e.relatedTarget as Node)) {
      setIsDragging(false);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      onUploadAssets(e.dataTransfer.files);
    }
  };

  const steps = [
    { num: '01', title: t.empty_step1_title, desc: t.empty_step1_desc },
    { num: '02', title: t.empty_step2_title, desc: t.empty_step2_desc },
    { num: '03', title: t.empty_step3_title, desc: t.empty_step3_desc },
  ];

  return (
    <div
      data-testid="empty-canvas-state"
      className="w-full max-w-2xl mx-auto my-auto"
    >
      <div className="bg-white border border-zinc-200 rounded-xl p-6 space-y-6 shadow-sm">
        {/* Top Metadata Bar */}
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-sm font-semibold text-zinc-900">
              {t.empty_title}
            </h2>
            <p className="text-xs text-zinc-500 mt-1 leading-relaxed">
              {t.empty_subtitle}
            </p>
          </div>
          <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-mono tabular-nums text-zinc-600 bg-zinc-100 border border-zinc-200 whitespace-nowrap shrink-0">
            {preset.marketplace} · {dimsLabel}
          </span>
        </div>

        {/* Optical Calibration Dropzone */}
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
          data-testid="empty-dropzone"
          onDragEnter={handleDragEnter}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`relative rounded-lg border border-dashed p-8 text-center cursor-pointer transition-[border-color,background-color] ${
            isDragging
              ? 'border-kroma-600 bg-kroma-50/40'
              : 'border-zinc-300 bg-zinc-50/70 hover:border-zinc-400 hover:bg-zinc-50'
          }`}
        >
          {/* Optical Viewfinder Corner Registration Ticks */}
          <span
            aria-hidden="true"
            className="pointer-events-none absolute top-2 left-2 w-3 h-3 border-t border-l border-zinc-400"
          />
          <span
            aria-hidden="true"
            className="pointer-events-none absolute top-2 right-2 w-3 h-3 border-t border-r border-zinc-400"
          />
          <span
            aria-hidden="true"
            className="pointer-events-none absolute bottom-2 left-2 w-3 h-3 border-b border-l border-zinc-400"
          />
          <span
            aria-hidden="true"
            className="pointer-events-none absolute bottom-2 right-2 w-3 h-3 border-b border-r border-zinc-400"
          />

          <div className="w-12 h-12 mx-auto rounded-lg bg-white border border-zinc-200 flex items-center justify-center mb-3">
            <UploadCloud className="w-5 h-5 text-zinc-700" strokeWidth={1.5} />
          </div>

          <p className="text-sm font-medium text-zinc-900">
            {isDragging ? t.empty_drop_active : t.empty_drop_title}
          </p>
          <p className="text-xs font-mono text-zinc-500 mt-1">
            {t.empty_formats}
          </p>

          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              fileInputRef.current?.click();
            }}
            className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-kroma-600 hover:bg-kroma-700 active:scale-[0.98] text-white text-xs font-medium transition-[background-color,transform] focus:outline-none focus:ring-2 focus:ring-kroma-600/30 shadow-sm"
          >
            <ImagePlus className="w-4 h-4" strokeWidth={1.5} />
            <span>{t.empty_cta}</span>
          </button>

          {/* Quick Paste Hint */}
          <div className="mt-3 flex items-center justify-center gap-1 text-xs text-zinc-500">
            <kbd className="px-2 py-0.5 rounded bg-zinc-100 border border-zinc-200 text-zinc-600 font-mono text-xs">
              Ctrl
            </kbd>
            <span>+</span>
            <kbd className="px-2 py-0.5 rounded bg-zinc-100 border border-zinc-200 text-zinc-600 font-mono text-xs">
              V
            </kbd>
            <span>{lang === 'vi' ? 'để dán nhanh ảnh chụp màn hình' : 'to paste screenshot directly'}</span>
          </div>
        </div>

        {/* 3-Step Usage Guide */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {steps.map((step) => (
            <div
              key={step.num}
              className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 space-y-1"
            >
              <span className="block text-xs font-mono font-medium text-kroma-600 tabular-nums">
                {step.num}
              </span>
              <h3 className="text-xs font-semibold text-zinc-900">
                {step.title}
              </h3>
              <p className="text-xs text-zinc-500 leading-relaxed">
                {step.desc}
              </p>
            </div>
          ))}
        </div>

        {/* Studio Notes */}
        <div className="border-t border-zinc-200 pt-4 space-y-2">
          <p className="text-xs font-medium text-zinc-700">
            {t.empty_tips_label}
          </p>
          <div className="flex items-start gap-2 text-xs text-zinc-500 leading-relaxed">
            <ScanLine className="w-4 h-4 text-zinc-400 shrink-0 mt-0.5" strokeWidth={1.5} />
            <span>{t.empty_tip_1}</span>
          </div>
          <div className="flex items-start gap-2 text-xs text-zinc-500 leading-relaxed">
            <SlidersHorizontal className="w-4 h-4 text-zinc-400 shrink-0 mt-0.5" strokeWidth={1.5} />
            <span className="tabular-nums">{tip2Text}</span>
          </div>
        </div>
      </div>
    </div>
  );
};
