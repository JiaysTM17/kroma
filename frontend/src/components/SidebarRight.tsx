'use client';

import React, { useState } from 'react';
import {
  Wand2,
  Paintbrush,
  RotateCcw,
  CheckCircle2,
  Sliders,
  Maximize,
  Eye,
  EyeOff,
  X,
} from 'lucide-react';
import {
  AdjustmentValues,
  ImageAsset,
  MarketplacePreset,
  PromoBadgeConfig,
  PromoBadgeType,
  ShadowConfig,
  ShadowType,
  TransformState,
  WatermarkConfig,
} from '@/lib/types';
import { MARKETPLACE_PRESETS } from '@/lib/presets';
import { Language, translations } from '@/lib/i18n';

interface SidebarRightProps {
  lang: Language;
  asset: ImageAsset | null;
  selectedPreset: MarketplacePreset;
  shadow: ShadowConfig;
  adjustments: AdjustmentValues;
  promoBadge: PromoBadgeConfig;
  watermark: WatermarkConfig;
  transform: TransformState;
  isRemovingBg: boolean;
  isBrushActive: boolean;
  brushSize: number;
  onSelectPreset: (preset: MarketplacePreset) => void;
  onAutoFrameAmazon: () => void;
  onRemoveBackground: () => void;
  onRestoreOriginal: () => void;
  onToggleBrush: () => void;
  onBrushSizeChange: (size: number) => void;
  onShadowChange: (shadow: ShadowConfig) => void;
  onAdjustmentsChange: (adjustments: AdjustmentValues) => void;
  onPromoBadgeChange: (badge: PromoBadgeConfig) => void;
  onWatermarkChange: (watermark: WatermarkConfig) => void;
  onTransformChange: (transform: TransformState) => void;
  isOpenMobile?: boolean;
  onCloseMobile?: () => void;
}

export const SidebarRight: React.FC<SidebarRightProps> = ({
  lang,
  asset,
  selectedPreset,
  shadow,
  adjustments,
  promoBadge,
  watermark,
  transform,
  isRemovingBg,
  isBrushActive,
  brushSize,
  onSelectPreset,
  onAutoFrameAmazon,
  onRemoveBackground,
  onRestoreOriginal,
  onToggleBrush,
  onBrushSizeChange,
  onShadowChange,
  onAdjustmentsChange,
  onPromoBadgeChange,
  onWatermarkChange,
  onTransformChange,
  isOpenMobile = false,
  onCloseMobile,
}) => {
  const t = translations[lang];
  const [activeTab, setActiveTab] = useState<'presets' | 'cutout' | 'shadow' | 'badges' | 'adjust' | 'layers'>('presets');

  const tabs: Array<{ id: typeof activeTab; label: string }> = [
    { id: 'presets', label: lang === 'vi' ? 'Sàn TMĐT' : 'Presets' },
    { id: 'cutout', label: lang === 'vi' ? 'Tách nền' : 'Cutout' },
    { id: 'shadow', label: lang === 'vi' ? 'Đổ bóng' : 'Shadow' },
    { id: 'badges', label: lang === 'vi' ? 'Khung tem' : 'Badges' },
    { id: 'adjust', label: lang === 'vi' ? 'Chỉnh màu' : 'Adjust' },
    { id: 'layers', label: 'Layer' },
  ];

  return (
    <aside
      aria-label={t.toggle_inspector_panel}
      className={`fixed inset-y-14 right-0 z-30 w-80 lg:static lg:inset-auto lg:w-80 shrink-0 border-l border-surface-border bg-surface-light flex flex-col lg:h-[calc(100vh-3.5rem)] select-none transition-transform duration-200 ${
        isOpenMobile ? 'translate-x-0 shadow-lg lg:shadow-none' : 'translate-x-full lg:translate-x-0'
      }`}
    >
      {/* Mobile Close Header */}
      {onCloseMobile && (
        <div className="lg:hidden px-4 py-2 border-b border-surface-border flex items-center justify-between bg-surface-subtle">
          <span className="text-xs font-semibold text-zinc-800">{t.toggle_inspector_panel}</span>
          <button
            type="button"
            onClick={onCloseMobile}
            aria-label={t.close_panel}
            className="p-1 rounded text-zinc-500 hover:text-zinc-900 hover:bg-zinc-200/70 transition-colors"
          >
            <X className="w-4 h-4" strokeWidth={1.5} />
          </button>
        </div>
      )}

      {/* 6-Tab Navigation Bar */}
      <div className="flex items-center overflow-x-auto border-b border-surface-border bg-surface-subtle">
        {tabs.map((tab) => {
          const active = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 min-w-0 py-3 px-1 text-center text-xs whitespace-nowrap border-b-2 transition-colors ${
                active
                  ? 'border-kroma-600 text-zinc-900 bg-surface-light font-semibold'
                  : 'border-transparent text-zinc-500 hover:text-zinc-900 font-medium'
              }`}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab Panels */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {/* 1. MARKETPLACE PRESETS TAB */}
        {activeTab === 'presets' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-semibold text-zinc-800">
                {t.tab_presets}
              </span>
              <span className="text-xs text-emerald-700 font-medium flex items-center gap-1">
                <CheckCircle2 className="w-4 h-4" strokeWidth={1.5} />
                <span>{t.compliant}</span>
              </span>
            </div>

            {/* Amazon 1-Click Auto Framing Feature (Calm Neutral Card) */}
            {selectedPreset.id === 'amazon_white_85' && (
              <div className="p-3 bg-zinc-50 rounded-lg border border-zinc-200 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-zinc-900">
                    {lang === 'vi' ? 'Chuẩn Amazon 85% diện tích' : 'Amazon 85% subject fill'}
                  </span>
                  <span className="text-xs font-medium text-kroma-700 bg-kroma-50 border border-kroma-200 px-2 py-1 rounded">
                    {lang === 'vi' ? 'Khuyến nghị' : 'Recommended'}
                  </span>
                </div>
                <p className="text-xs text-zinc-500 leading-relaxed">
                  {lang === 'vi'
                    ? 'Tự động căn sản phẩm chiếm đúng 85% khung hình và áp dụng nền trắng tinh khiết RGB(255,255,255).'
                    : 'Automatically scales product to fill 85% of the frame on pure white RGB(255,255,255).'}
                </p>
                <button
                  type="button"
                  onClick={onAutoFrameAmazon}
                  className="w-full py-2 px-3 text-xs font-medium rounded-lg bg-kroma-600 hover:bg-kroma-700 text-white flex items-center justify-center gap-2 transition-colors shadow-sm"
                >
                  <Maximize className="w-4 h-4" strokeWidth={1.5} />
                  <span>
                    {lang === 'vi' ? 'Áp dụng căn khung 85% Amazon' : 'Apply Amazon 85% framing'}
                  </span>
                </button>
              </div>
            )}

            {/* Scale Slider */}
            <div className="space-y-1 pt-1">
              <div className="flex justify-between text-xs text-zinc-600">
                <span>{lang === 'vi' ? 'Tỷ lệ khung hình sản phẩm' : 'Subject scale'}</span>
                <span className="font-mono tabular-nums">{Math.round(transform.scale * 100)}%</span>
              </div>
              <input
                type="range"
                min="0.5"
                max="1.5"
                step="0.02"
                value={transform.scale}
                onChange={(e) => onTransformChange({ ...transform, scale: Number(e.target.value) })}
                className="w-full accent-kroma-600 cursor-pointer"
              />
            </div>

            <div className="space-y-2 pt-2">
              {MARKETPLACE_PRESETS.map((p) => {
                const isSelected = p.id === selectedPreset.id;
                const pName = lang === 'vi' ? p.name_vi : p.name_en;
                const pDesc = lang === 'vi' ? p.rule_description_vi : p.rule_description_en;
                return (
                  <div
                    key={p.id}
                    onClick={() => onSelectPreset(p)}
                    className={`p-3 rounded-lg border cursor-pointer transition-[border-color,background-color] ${
                      isSelected
                        ? 'border-kroma-600 bg-kroma-50/60 shadow-sm'
                        : 'border-surface-border hover:border-zinc-300 bg-surface-light'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <span className="text-xs font-semibold text-zinc-900">{p.marketplace}</span>
                      <span className="text-xs font-mono tabular-nums px-2 py-1 rounded bg-zinc-100 text-zinc-600 border border-zinc-200">
                        {p.width}×{p.height} ({p.aspect_ratio})
                      </span>
                    </div>
                    <p className="text-xs font-medium text-zinc-800">{pName}</p>
                    <p className="text-xs text-zinc-500 mt-1 leading-relaxed">{pDesc}</p>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* 2. AI CUTOUT TAB */}
        {activeTab === 'cutout' && (
          <div className="space-y-4">
            <span className="text-xs font-semibold text-zinc-800 block">
              {t.tab_cutout}
            </span>

            <div className="p-3 rounded-lg border border-zinc-200 bg-surface-subtle space-y-3">
              <p className="text-xs font-semibold text-zinc-800 flex items-center gap-2">
                <Wand2 className="w-4 h-4 text-kroma-600" strokeWidth={1.5} />
                <span>RMBG-1.4 Neural Engine (Offline)</span>
              </p>
              <p className="text-xs text-zinc-500 leading-relaxed">
                {lang === 'vi'
                  ? 'Tách chủ thể chính xác với viền mềm trong suốt mà không gửi dữ liệu ra ngoài.'
                  : 'Isolates subject edges locally with smooth alpha feathering without external uploads.'}
              </p>

              {asset?.hasBackgroundRemoved ? (
                <button
                  type="button"
                  onClick={onRestoreOriginal}
                  className="w-full py-2 px-3 text-xs font-medium rounded-lg border border-zinc-300 bg-surface-light hover:bg-zinc-50 text-zinc-700 flex items-center justify-center gap-2 transition-colors"
                >
                  <RotateCcw className="w-4 h-4 text-zinc-500" strokeWidth={1.5} />
                  <span>{t.restore_bg}</span>
                </button>
              ) : (
                <button
                  type="button"
                  onClick={onRemoveBackground}
                  disabled={!asset || isRemovingBg}
                  className="w-full py-2 px-3 text-xs font-medium rounded-lg bg-kroma-600 hover:bg-kroma-700 text-white flex items-center justify-center gap-2 shadow-sm transition-colors disabled:opacity-40"
                >
                  <Wand2 className="w-4 h-4" strokeWidth={1.5} />
                  <span>{isRemovingBg ? t.removing_bg : t.remove_bg}</span>
                </button>
              )}
            </div>

            {/* Refine Edge Tool */}
            <div className="space-y-3">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-medium text-zinc-800 flex items-center gap-2">
                  <Paintbrush className="w-4 h-4 text-zinc-600" strokeWidth={1.5} />
                  <span>{t.refine_edge}</span>
                </span>
                <button
                  type="button"
                  onClick={onToggleBrush}
                  className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                    isBrushActive
                      ? 'bg-kroma-600 text-white'
                      : 'bg-zinc-100 text-zinc-600 hover:bg-zinc-200'
                  }`}
                >
                  {isBrushActive
                    ? lang === 'vi'
                      ? 'Đang bật cọ'
                      : 'Active'
                    : lang === 'vi'
                    ? 'Bật cọ'
                    : 'Enable'}
                </button>
              </div>

              {isBrushActive && (
                <div className="space-y-2 pt-2 border-t border-zinc-200">
                  <div className="flex justify-between text-xs text-zinc-600">
                    <span>{t.brush_size}</span>
                    <span className="font-mono tabular-nums">{brushSize}px</span>
                  </div>
                  <input
                    type="range"
                    min="5"
                    max="80"
                    value={brushSize}
                    onChange={(e) => onBrushSizeChange(Number(e.target.value))}
                    className="w-full accent-kroma-600 cursor-pointer"
                  />
                </div>
              )}
            </div>
          </div>
        )}

        {/* 3. PHYSICAL SHADOW TAB */}
        {activeTab === 'shadow' && (
          <div className="space-y-4">
            <span className="text-xs font-semibold text-zinc-800 block">
              {t.tab_shadow}
            </span>

            <div className="grid grid-cols-2 gap-2">
              {[
                { type: 'none', label: t.shadow_none },
                { type: 'contact', label: t.shadow_contact },
                { type: 'floor', label: t.shadow_floor },
                { type: 'reflection', label: t.shadow_reflection },
              ].map((item) => (
                <button
                  key={item.type}
                  type="button"
                  onClick={() =>
                    onShadowChange({
                      ...shadow,
                      enabled: item.type !== 'none',
                      type: item.type as ShadowType,
                    })
                  }
                  className={`p-2 rounded-lg text-xs text-left border transition-[border-color,background-color] ${
                    shadow.type === item.type
                      ? 'border-kroma-600 bg-kroma-50 text-kroma-950 font-semibold shadow-sm'
                      : 'border-surface-border hover:border-zinc-300 text-zinc-700 bg-surface-light font-medium'
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>

            {shadow.enabled && shadow.type !== 'none' && (
              <div className="space-y-4 pt-2">
                <div className="space-y-1">
                  <div className="flex justify-between text-xs text-zinc-600">
                    <span>{t.opacity}</span>
                    <span className="font-mono tabular-nums">{Math.round(shadow.opacity * 100)}%</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={shadow.opacity}
                    onChange={(e) =>
                      onShadowChange({ ...shadow, opacity: Number(e.target.value) })
                    }
                    className="w-full accent-kroma-600 cursor-pointer"
                  />
                </div>

                {shadow.type !== 'contact' && (
                  <div className="space-y-1">
                    <div className="flex justify-between text-xs text-zinc-600">
                      <span>{t.blur}</span>
                      <span className="font-mono tabular-nums">{shadow.blur}px</span>
                    </div>
                    <input
                      type="range"
                      min="1"
                      max="40"
                      value={shadow.blur}
                      onChange={(e) =>
                        onShadowChange({ ...shadow, blur: Number(e.target.value) })
                      }
                      className="w-full accent-kroma-600 cursor-pointer"
                    />
                  </div>
                )}

                <div className="space-y-1">
                  <div className="flex justify-between text-xs text-zinc-600">
                    <span>{t.distance}</span>
                    <span className="font-mono tabular-nums">{shadow.distance}px</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="50"
                    value={shadow.distance}
                    onChange={(e) =>
                      onShadowChange({ ...shadow, distance: Number(e.target.value) })
                    }
                    className="w-full accent-kroma-600 cursor-pointer"
                  />
                </div>

                {shadow.type === 'floor' && (
                  <div className="space-y-1">
                    <div className="flex justify-between text-xs text-zinc-600">
                      <span>{t.angle}</span>
                      <span className="font-mono tabular-nums">{shadow.angle}°</span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="180"
                      value={shadow.angle}
                      onChange={(e) =>
                        onShadowChange({ ...shadow, angle: Number(e.target.value) })
                      }
                      className="w-full accent-kroma-600 cursor-pointer"
                    />
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* 4. PROMO BADGES & WATERMARK TAB */}
        {activeTab === 'badges' && (
          <div className="space-y-4">
            <span className="text-xs font-semibold text-zinc-800 block">
              {t.tab_badges}
            </span>

            <div className="space-y-3">
              <label className="text-xs font-medium text-zinc-700 block">
                {t.promo_badge}
              </label>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { type: 'none', label: t.badge_none },
                  { type: 'flash_sale', label: t.badge_flash_sale },
                  { type: 'freeship', label: t.badge_freeship },
                  { type: 'mall', label: t.badge_mall },
                  { type: 'top_deal', label: t.badge_top_deal },
                  { type: 'discount_50', label: t.badge_discount_50 },
                ].map((item) => (
                  <button
                    key={item.type}
                    type="button"
                    onClick={() =>
                      onPromoBadgeChange({
                        ...promoBadge,
                        enabled: item.type !== 'none',
                        type: item.type as PromoBadgeType,
                      })
                    }
                    className={`p-2 rounded-lg text-xs border text-left transition-[border-color,background-color] ${
                      promoBadge.type === item.type
                        ? 'border-kroma-600 bg-kroma-50 text-kroma-950 font-semibold shadow-sm'
                        : 'border-surface-border hover:border-zinc-300 text-zinc-700 bg-surface-light font-medium'
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-3 pt-3 border-t border-zinc-200">
              <div className="flex items-center justify-between">
                <label className="text-xs font-medium text-zinc-700">
                  {t.watermark_title}
                </label>
                <input
                  type="checkbox"
                  checked={watermark.enabled}
                  onChange={(e) => onWatermarkChange({ ...watermark, enabled: e.target.checked })}
                  className="rounded text-kroma-600 accent-kroma-600"
                />
              </div>

              {watermark.enabled && (
                <div className="space-y-3 pt-2">
                  <input
                    type="text"
                    value={watermark.text}
                    onChange={(e) => onWatermarkChange({ ...watermark, text: e.target.value })}
                    placeholder={t.watermark_placeholder}
                    className="w-full px-3 py-2 text-xs rounded-lg border border-zinc-300 focus:border-kroma-600 focus:outline-none"
                  />

                  <div className="space-y-1">
                    <span className="text-xs text-zinc-500">{t.watermark_position}</span>
                    <div className="grid grid-cols-2 gap-2">
                      {(
                        [
                          { pos: 'bottom_right', label: t.pos_bottom_right },
                          { pos: 'bottom_left', label: t.pos_bottom_left },
                          { pos: 'center', label: t.pos_center },
                          { pos: 'diagonal_repeat', label: t.pos_repeat },
                        ] as const
                      ).map((item) => (
                        <button
                          key={item.pos}
                          type="button"
                          onClick={() =>
                            onWatermarkChange({
                              ...watermark,
                              position: item.pos,
                            })
                          }
                          className={`p-2 text-xs rounded-md border text-center transition-colors ${
                            watermark.position === item.pos
                              ? 'border-kroma-600 bg-kroma-50 text-kroma-900 font-semibold'
                              : 'border-zinc-200 text-zinc-600 hover:border-zinc-300'
                          }`}
                        >
                          {item.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-1">
                    <div className="flex justify-between text-xs text-zinc-500">
                      <span>{lang === 'vi' ? 'Độ trong suốt' : 'Opacity'}</span>
                      <span className="font-mono tabular-nums">{Math.round(watermark.opacity * 100)}%</span>
                    </div>
                    <input
                      type="range"
                      min="0.1"
                      max="0.9"
                      step="0.05"
                      value={watermark.opacity}
                      onChange={(e) =>
                        onWatermarkChange({ ...watermark, opacity: Number(e.target.value) })
                      }
                      className="w-full accent-kroma-600 cursor-pointer"
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* 5. FLOAT32 LIGHT ADJUSTMENTS */}
        {activeTab === 'adjust' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-zinc-800">
                {t.tab_adjust}
              </span>
              <button
                type="button"
                onClick={() =>
                  onAdjustmentsChange({
                    exposure: 0,
                    contrast: 0,
                    highlights: 0,
                    shadows: 0,
                    temperature: 0,
                    tint: 0,
                    sharpness: 0,
                  })
                }
                className="text-xs text-zinc-500 hover:text-zinc-900 transition-colors"
              >
                {lang === 'vi' ? 'Đặt lại' : 'Reset'}
              </button>
            </div>

            <div className="space-y-1">
              <div className="flex justify-between text-xs text-zinc-600">
                <span>Exposure</span>
                <span className="font-mono tabular-nums">{adjustments.exposure}</span>
              </div>
              <input
                type="range"
                min="-50"
                max="50"
                value={adjustments.exposure}
                onChange={(e) =>
                  onAdjustmentsChange({ ...adjustments, exposure: Number(e.target.value) })
                }
                className="w-full accent-kroma-600 cursor-pointer"
              />
            </div>

            <div className="space-y-1">
              <div className="flex justify-between text-xs text-zinc-600">
                <span>Contrast</span>
                <span className="font-mono tabular-nums">{adjustments.contrast}</span>
              </div>
              <input
                type="range"
                min="-50"
                max="50"
                value={adjustments.contrast}
                onChange={(e) =>
                  onAdjustmentsChange({ ...adjustments, contrast: Number(e.target.value) })
                }
                className="w-full accent-kroma-600 cursor-pointer"
              />
            </div>

            <div className="space-y-1">
              <div className="flex justify-between text-xs text-zinc-600">
                <span>Temperature</span>
                <span className="font-mono tabular-nums">{adjustments.temperature}</span>
              </div>
              <input
                type="range"
                min="-50"
                max="50"
                value={adjustments.temperature}
                onChange={(e) =>
                  onAdjustmentsChange({ ...adjustments, temperature: Number(e.target.value) })
                }
                className="w-full accent-kroma-600 cursor-pointer"
              />
            </div>

            <div className="space-y-1">
              <div className="flex justify-between text-xs text-zinc-600">
                <span>Tint</span>
                <span className="font-mono tabular-nums">{adjustments.tint}</span>
              </div>
              <input
                type="range"
                min="-50"
                max="50"
                value={adjustments.tint}
                onChange={(e) =>
                  onAdjustmentsChange({ ...adjustments, tint: Number(e.target.value) })
                }
                className="w-full accent-kroma-600 cursor-pointer"
              />
            </div>
          </div>
        )}

        {/* 6. LAYERS TAB */}
        {activeTab === 'layers' && (
          <div className="space-y-4">
            <div>
              <h3 className="text-xs font-semibold text-zinc-800 mb-1">
                {lang === 'vi' ? 'Ngăn xếp lớp vẽ (Canvas Layers)' : 'Canvas layer stack'}
              </h3>
              <p className="text-xs text-zinc-500">
                {lang === 'vi'
                  ? 'Quản lý bật/tắt hiển thị và kiểm tra thuộc tính từng lớp trên khung vẽ.'
                  : 'Toggle visibility and inspect layer parameters on the active canvas.'}
              </p>
            </div>

            <div className="space-y-2">
              {/* Layer 1: Watermark */}
              <div className="p-3 rounded-lg border border-zinc-200 bg-white shadow-sm flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <button
                    type="button"
                    onClick={() => onWatermarkChange({ ...watermark, enabled: !watermark.enabled })}
                    className={`p-1 rounded transition-colors shrink-0 ${
                      watermark.enabled
                        ? 'text-kroma-600 bg-kroma-50 hover:bg-kroma-100'
                        : 'text-zinc-400 bg-zinc-100 hover:text-zinc-600'
                    }`}
                    title={watermark.enabled ? 'Hide watermark' : 'Show watermark'}
                  >
                    {watermark.enabled ? (
                      <Eye className="w-4 h-4" strokeWidth={1.5} />
                    ) : (
                      <EyeOff className="w-4 h-4" strokeWidth={1.5} />
                    )}
                  </button>
                  <div className="min-w-0">
                    <div className="text-xs font-medium text-zinc-800 flex items-center gap-2">
                      <span>Watermark</span>
                      {watermark.enabled && (
                        <span className="px-2 py-0 rounded text-xs bg-emerald-50 text-emerald-700 font-mono">
                          ON
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-zinc-500 truncate">
                      {watermark.text || '—'}
                    </div>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setActiveTab('badges')}
                  className="text-xs text-kroma-600 hover:text-kroma-800 font-medium shrink-0"
                >
                  {lang === 'vi' ? 'Sửa' : 'Edit'}
                </button>
              </div>

              {/* Layer 2: Promo Badge */}
              <div className="p-3 rounded-lg border border-zinc-200 bg-white shadow-sm flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <button
                    type="button"
                    onClick={() => onPromoBadgeChange({ ...promoBadge, enabled: !promoBadge.enabled })}
                    className={`p-1 rounded transition-colors shrink-0 ${
                      promoBadge.enabled
                        ? 'text-kroma-600 bg-kroma-50 hover:bg-kroma-100'
                        : 'text-zinc-400 bg-zinc-100 hover:text-zinc-600'
                    }`}
                    title={promoBadge.enabled ? 'Hide badge' : 'Show badge'}
                  >
                    {promoBadge.enabled ? (
                      <Eye className="w-4 h-4" strokeWidth={1.5} />
                    ) : (
                      <EyeOff className="w-4 h-4" strokeWidth={1.5} />
                    )}
                  </button>
                  <div className="min-w-0">
                    <div className="text-xs font-medium text-zinc-800 flex items-center gap-2">
                      <span>{lang === 'vi' ? 'Khung / Huy hiệu' : 'Promo badge'}</span>
                      {promoBadge.enabled && (
                        <span className="px-2 py-0 rounded text-xs bg-zinc-100 text-zinc-700 font-mono">
                          {promoBadge.type}
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-zinc-500">
                      {promoBadge.position.replace('_', ' ')}
                    </div>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setActiveTab('badges')}
                  className="text-xs text-kroma-600 hover:text-kroma-800 font-medium shrink-0"
                >
                  {lang === 'vi' ? 'Sửa' : 'Edit'}
                </button>
              </div>

              {/* Layer 3: Main Product Subject */}
              <div className="p-3 rounded-lg border border-zinc-200 bg-white shadow-sm flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="p-1 rounded text-kroma-600 bg-kroma-50 shrink-0">
                    <Maximize className="w-4 h-4" strokeWidth={1.5} />
                  </div>
                  <div className="min-w-0">
                    <div className="text-xs font-medium text-zinc-800">
                      {lang === 'vi' ? 'Chủ thể sản phẩm' : 'Product subject'}
                    </div>
                    <div className="text-xs text-zinc-500 font-mono tabular-nums">
                      {Math.round(transform.scale * 100)}% · X:{Math.round(transform.offsetX)} Y:{Math.round(transform.offsetY)}
                    </div>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => onTransformChange({ offsetX: 0, offsetY: 0, scale: 1 })}
                  className="text-xs text-zinc-500 hover:text-zinc-900 font-medium shrink-0"
                >
                  {lang === 'vi' ? 'Căn giữa' : 'Center'}
                </button>
              </div>

              {/* Layer 4: Physical Shadow */}
              <div className="p-3 rounded-lg border border-zinc-200 bg-white shadow-sm flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <button
                    type="button"
                    onClick={() => onShadowChange({ ...shadow, enabled: !shadow.enabled })}
                    className={`p-1 rounded transition-colors shrink-0 ${
                      shadow.enabled
                        ? 'text-kroma-600 bg-kroma-50 hover:bg-kroma-100'
                        : 'text-zinc-400 bg-zinc-100 hover:text-zinc-600'
                    }`}
                    title={shadow.enabled ? 'Hide shadow' : 'Show shadow'}
                  >
                    {shadow.enabled ? (
                      <Eye className="w-4 h-4" strokeWidth={1.5} />
                    ) : (
                      <EyeOff className="w-4 h-4" strokeWidth={1.5} />
                    )}
                  </button>
                  <div className="min-w-0">
                    <div className="text-xs font-medium text-zinc-800 flex items-center gap-2">
                      <span>{lang === 'vi' ? 'Bóng đổ quang học' : 'Optical shadow'}</span>
                      {shadow.enabled && (
                        <span className="px-2 py-0 rounded text-xs bg-zinc-100 text-zinc-700 font-mono">
                          {shadow.type}
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-zinc-500 font-mono tabular-nums">
                      {Math.round(shadow.opacity * 100)}% · {shadow.blur}px
                    </div>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setActiveTab('shadow')}
                  className="text-xs text-kroma-600 hover:text-kroma-800 font-medium shrink-0"
                >
                  {lang === 'vi' ? 'Sửa' : 'Edit'}
                </button>
              </div>

              {/* Layer 5: Studio Backdrop */}
              <div className="p-3 rounded-lg border border-zinc-200 bg-white shadow-sm flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="p-1 rounded text-zinc-500 bg-zinc-100 shrink-0">
                    <Sliders className="w-4 h-4" strokeWidth={1.5} />
                  </div>
                  <div className="min-w-0">
                    <div className="text-xs font-medium text-zinc-800">
                      {lang === 'vi' ? 'Phông nền sàn TMĐT' : 'Marketplace frame'}
                    </div>
                    <div className="text-xs text-zinc-500 font-mono tabular-nums truncate">
                      {selectedPreset.marketplace} ({selectedPreset.width}×{selectedPreset.height})
                    </div>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setActiveTab('presets')}
                  className="text-xs text-kroma-600 hover:text-kroma-800 font-medium shrink-0"
                >
                  {lang === 'vi' ? 'Đổi' : 'Change'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
};
