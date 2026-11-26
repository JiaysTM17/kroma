'use client';

import React from 'react';
import Image from 'next/image';
import { Share2, Download, Globe, ShieldCheck } from 'lucide-react';
import { Language, translations } from '@/lib/i18n';

interface HeaderProps {
  lang: Language;
  onLanguageChange: (lang: Language) => void;
  onOpenExport: () => void;
  onOpenProofing: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  lang,
  onLanguageChange,
  onOpenExport,
  onOpenProofing,
}) => {
  const t = translations[lang];

  return (
    <header className="h-14 border-b border-surface-border bg-surface-light px-4 flex items-center justify-between select-none z-20">
      {/* Brand & Wordmark */}
      <div className="flex items-center gap-3">
        <div className="h-8 flex items-center">
          <img
            src="/assets/logo/kroma-logo-horizontal.svg"
            alt="KROMA Intelligent Image Studio"
            className="h-8 w-auto object-contain"
          />
        </div>
        <span className="hidden sm:inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
          <ShieldCheck className="w-3 h-3 text-emerald-600" />
          <span>Local Engine Active</span>
        </span>
      </div>

      {/* Action Controls */}
      <div className="flex items-center gap-2">
        {/* Language switcher */}
        <div className="flex items-center rounded border border-surface-border bg-surface-subtle p-0.5 text-xs">
          <button
            onClick={() => onLanguageChange('vi')}
            className={`px-2 py-1 rounded font-medium transition-colors ${
              lang === 'vi'
                ? 'bg-surface-light text-slate-900 shadow-sm'
                : 'text-slate-500 hover:text-slate-900'
            }`}
          >
            VI
          </button>
          <button
            onClick={() => onLanguageChange('en')}
            className={`px-2 py-1 rounded font-medium transition-colors ${
              lang === 'en'
                ? 'bg-surface-light text-slate-900 shadow-sm'
                : 'text-slate-500 hover:text-slate-900'
            }`}
          >
            EN
          </button>
        </div>

        {/* Share Proofing Link */}
        <button
          onClick={onOpenProofing}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-surface-subtle hover:bg-surface-muted border border-surface-border rounded transition-colors"
        >
          <Share2 className="w-3.5 h-3.5 text-slate-500" />
          <span className="hidden md:inline">{t.share_proofing}</span>
        </button>

        {/* Batch Export ZIP */}
        <button
          onClick={onOpenExport}
          className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold text-white bg-kroma-600 hover:bg-kroma-700 rounded shadow-sm transition-colors"
        >
          <Download className="w-3.5 h-3.5" />
          <span>{t.export_all}</span>
        </button>
      </div>
    </header>
  );
};
