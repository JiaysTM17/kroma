'use client';

import React from 'react';
import { Share2, Download, PanelLeft, SlidersHorizontal } from 'lucide-react';
import { Language, translations } from '@/lib/i18n';

interface HeaderProps {
  lang: Language;
  onLanguageChange: (lang: Language) => void;
  onOpenExport: () => void;
  onOpenProofing: () => void;
  activeMobilePanel?: 'none' | 'left' | 'right';
  onToggleLeftPanel?: () => void;
  onToggleRightPanel?: () => void;
  assetCount?: number;
}

export const Header: React.FC<HeaderProps> = ({
  lang,
  onLanguageChange,
  onOpenExport,
  onOpenProofing,
  activeMobilePanel = 'none',
  onToggleLeftPanel,
  onToggleRightPanel,
  assetCount = 0,
}) => {
  const t = translations[lang];

  return (
    <header className="h-14 border-b border-surface-border bg-surface-light px-3 sm:px-4 flex items-center justify-between gap-2 select-none z-30 shrink-0">
      {/* Left: Drawer Toggle (<lg) + Brand Wordmark + Quiet Status */}
      <div className="flex items-center gap-2 sm:gap-3 min-w-0">
        {onToggleLeftPanel && (
          <button
            type="button"
            onClick={onToggleLeftPanel}
            aria-label={t.toggle_assets_panel}
            aria-expanded={activeMobilePanel === 'left'}
            className={`lg:hidden h-8 px-2 rounded-md border flex items-center gap-1 text-xs font-medium transition-colors shrink-0 ${
              activeMobilePanel === 'left'
                ? 'bg-zinc-900 text-white border-zinc-900'
                : 'bg-surface-subtle text-zinc-700 border-surface-border hover:bg-surface-muted'
            }`}
          >
            <PanelLeft className="w-4 h-4" strokeWidth={1.5} />
            <span className="font-mono tabular-nums text-xs">{assetCount}</span>
          </button>
        )}

        <div className="h-7 sm:h-8 flex items-center shrink-0">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/assets/logo/kroma-logo-horizontal.svg"
            alt="KROMA Intelligent Image Studio"
            className="h-7 sm:h-8 w-auto object-contain"
          />
        </div>

        <span className="hidden md:inline-flex items-center gap-2 px-2 py-1 rounded-md text-xs text-zinc-500 whitespace-nowrap">
          <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
          <span>Local Engine Active</span>
        </span>
      </div>

      {/* Right: Language + Actions + Inspector Toggle (<lg) */}
      <div className="flex items-center gap-2 shrink-0">
        {/* Language Switcher */}
        <div className="flex items-center rounded-md border border-surface-border bg-surface-subtle p-1 text-xs">
          <button
            type="button"
            onClick={() => onLanguageChange('vi')}
            className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
              lang === 'vi'
                ? 'bg-surface-light text-zinc-900 shadow-sm'
                : 'text-zinc-500 hover:text-zinc-900'
            }`}
          >
            VI
          </button>
          <button
            type="button"
            onClick={() => onLanguageChange('en')}
            className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
              lang === 'en'
                ? 'bg-surface-light text-zinc-900 shadow-sm'
                : 'text-zinc-500 hover:text-zinc-900'
            }`}
          >
            EN
          </button>
        </div>

        {/* Share Proofing Link */}
        <button
          type="button"
          onClick={onOpenProofing}
          title={t.share_proofing}
          className="h-8 flex items-center gap-2 px-2 sm:px-3 text-xs font-medium text-zinc-700 bg-surface-subtle hover:bg-surface-muted border border-surface-border rounded-md transition-colors whitespace-nowrap"
        >
          <Share2 className="w-4 h-4 text-zinc-500" strokeWidth={1.5} />
          <span className="hidden md:inline">{t.share_proofing}</span>
        </button>

        {/* Batch Export ZIP */}
        <button
          type="button"
          onClick={onOpenExport}
          className="h-8 flex items-center gap-2 px-3 text-xs font-medium text-white bg-kroma-600 hover:bg-kroma-700 rounded-md shadow-sm transition-colors whitespace-nowrap"
        >
          <Download className="w-4 h-4" strokeWidth={1.5} />
          <span className="hidden sm:inline">{t.export_all}</span>
          <span className="sm:hidden">{t.export_short}</span>
        </button>

        {onToggleRightPanel && (
          <button
            type="button"
            onClick={onToggleRightPanel}
            aria-label={t.toggle_inspector_panel}
            aria-expanded={activeMobilePanel === 'right'}
            className={`lg:hidden h-8 w-8 rounded-md border flex items-center justify-center transition-colors shrink-0 ${
              activeMobilePanel === 'right'
                ? 'bg-zinc-900 text-white border-zinc-900'
                : 'bg-surface-subtle text-zinc-700 border-surface-border hover:bg-surface-muted'
            }`}
          >
            <SlidersHorizontal className="w-4 h-4" strokeWidth={1.5} />
          </button>
        )}
      </div>
    </header>
  );
};
