'use client';

import React, { useState } from 'react';
import {
  Sparkles,
  Wand2,
  Paintbrush,
  RotateCcw,
  CheckCircle2,
  Tag,
  Sliders,
  Type,
  Maximize,
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
}) => {
  const t = translations[lang];
  const [activeTab, setActiveTab] = useState<'presets' | 'cutout' | 'shadow' | 'badges' | 'adjust'>('presets');

  return (
    <aside className="w-84 border-l border-surface-border bg-surface-light flex flex-col h-[calc(100vh-3.5rem)] select-none">
      {/* 5-Tab Navigation Bar */}
      <div className="grid grid-cols-5 border-b border-surface-border bg-surface-subtle text-[11px]">
        <button
          onClick={() => setActiveTab('presets')}
          className={`py-3 px-1 text-center font-medium border-b-2 transition-colors ${
            activeTab === 'presets'
              ? 'border-kroma-600 text-kroma-900 bg-surface-light font-bold'
              : 'border-transparent text-slate-500 hover:text-slate-900'
          }`}
        >
          Sàn TMĐT
        </button>
        <button
          onClick={() => setActiveTab('cutout')}
          className={`py-3 px-1 text-center font-medium border-b-2 transition-colors ${
            activeTab === 'cutout'
              ? 'border-kroma-600 text-kroma-900 bg-surface-light font-bold'
              : 'border-transparent text-slate-500 hover:text-slate-900'
          }`}
        >
          Tách nền
        </button>
        <button
          onClick={() => setActiveTab('shadow')}
          className={`py-3 px-1 text-center font-medium border-b-2 transition-colors ${
            activeTab === 'shadow'
              ? 'border-kroma-600 text-kroma-900 bg-surface-light font-bold'
              : 'border-transparent text-slate-500 hover:text-slate-900'
          }`}
        >
          Đổ bóng
        </button>
        <button
          onClick={() => setActiveTab('badges')}
          className={`py-3 px-1 text-center font-medium border-b-2 transition-colors ${
            activeTab === 'badges'
              ? 'border-kroma-600 text-kroma-900 bg-surface-light font-bold'
              : 'border-transparent text-slate-500 hover:text-slate-900'
          }`}
        >
          Khung tem
        </button>
        <button
          onClick={() => setActiveTab('adjust')}
          className={`py-3 px-1 text-center font-medium border-b-2 transition-colors ${
            activeTab === 'adjust'
              ? 'border-kroma-600 text-kroma-900 bg-surface-light font-bold'
              : 'border-transparent text-slate-500 hover:text-slate-900'
          }`}
        >
          Ánh sáng
        </button>
      </div>

      {/* Tab Panels */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {/* 1. MARKETPLACE PRESETS TAB */}
        {activeTab === 'presets' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                {t.tab_presets}
              </span>
              <span className="text-[11px] text-emerald-600 font-semibold flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5" />
                {t.compliant}
              </span>
            </div>

            {/* Amazon 1-Click Auto Framing Feature */}
            {selectedPreset.id === 'amazon_white_85' && (
              <div className="p-3 bg-amber-50 rounded-lg border border-amber-200 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-amber-900">Chuẩn Amazon 85% Diện Tích</span>
                  <span className="text-[10px] font-bold text-emerald-700 bg-emerald-100 px-1.5 py-0.5 rounded">
                    Khuyến nghị
                  </span>
                </div>
                <p className="text-[11px] text-amber-800 leading-relaxed">
                  Tự động co dãn sản phẩm chiếm đúng 85% khung hình và áp dụng nền trắng tinh khiết RGB(255,255,255).
                </p>
                <button
                  onClick={onAutoFrameAmazon}
                  className="w-full py-1.5 px-3 text-xs font-semibold rounded bg-amber-600 hover:bg-amber-700 text-white flex items-center justify-center gap-1.5 transition-colors shadow-2xs"
                >
                  <Maximize className="w-3.5 h-3.5" />
                  <span>Áp dụng căn khung 85% chuẩn Amazon</span>
                </button>
              </div>
            )}

            {/* Scale Slider */}
            <div className="space-y-1 pt-1">
              <div className="flex justify-between text-xs text-slate-600">
                <span>Tỷ lệ khung hình sản phẩm (Scale)</span>
                <span className="font-mono">{Math.round(transform.scale * 100)}%</span>
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
                return (
                  <div
                    key={p.id}
                    onClick={() => onSelectPreset(p)}
                    className={`p-3 rounded-lg border cursor-pointer transition-all ${
                      isSelected
                        ? 'border-kroma-600 bg-kroma-50/60 shadow-xs'
                        : 'border-surface-border hover:border-slate-300 bg-surface-light'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-bold text-slate-900">{p.marketplace}</span>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
                        {p.width} × {p.height} ({p.aspect_ratio})
                      </span>
                    </div>
                    <p className="text-xs font-semibold text-slate-800">{p.name_vi}</p>
                    <p className="text-[11px] text-slate-500 mt-1 leading-relaxed">
                      {p.rule_description_vi}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* 2. AI CUTOUT TAB */}
        {activeTab === 'cutout' && (
          <div className="space-y-5">
            <span className="text-xs font-bold text-slate-800 uppercase tracking-wider block">
              {t.tab_cutout}
            </span>

            <div className="p-3.5 rounded-lg border border-slate-200 bg-surface-subtle space-y-2.5">
              <p className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                <Wand2 className="w-3.5 h-3.5 text-kroma-600" />
                <span>RMBG-1.4 Neural Engine (Offline)</span>
              </p>
              <p className="text-[11px] text-slate-500 leading-relaxed">
                Tách chủ thể chính xác từng sợi tóc, viền mềm trong suốt mà không gửi dữ liệu ra ngoài.
              </p>

              {asset?.hasBackgroundRemoved ? (
                <button
                  onClick={onRestoreOriginal}
                  className="w-full py-2 px-3 text-xs font-semibold rounded border border-slate-300 bg-surface-light hover:bg-slate-50 text-slate-700 flex items-center justify-center gap-1.5 transition-colors"
                >
                  <RotateCcw className="w-3.5 h-3.5 text-slate-500" />
                  <span>{t.restore_bg}</span>
                </button>
              ) : (
                <button
                  onClick={onRemoveBackground}
                  disabled={!asset || isRemovingBg}
                  className="w-full py-2 px-3 text-xs font-bold rounded bg-kroma-600 hover:bg-kroma-700 text-white flex items-center justify-center gap-1.5 shadow-sm transition-colors disabled:opacity-50"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>{isRemovingBg ? t.removing_bg : t.remove_bg}</span>
                </button>
              )}
            </div>

            {/* Refine Edge Tool */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                  <Paintbrush className="w-3.5 h-3.5 text-slate-600" />
                  <span>{t.refine_edge}</span>
                </span>
                <button
                  onClick={onToggleBrush}
                  className={`px-2 py-0.5 rounded text-[11px] font-semibold transition-colors ${
                    isBrushActive
                      ? 'bg-kroma-600 text-white'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  {isBrushActive ? 'Đang bật cọ' : 'Bật cọ'}
                </button>
              </div>

              {isBrushActive && (
                <div className="space-y-2 pt-2 border-t border-slate-200">
                  <div className="flex justify-between text-xs text-slate-600">
                    <span>{t.brush_size}</span>
                    <span className="font-mono">{brushSize}px</span>
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
          <div className="space-y-5">
            <span className="text-xs font-bold text-slate-800 uppercase tracking-wider block">
              {t.tab_shadow}
            </span>

            {/* Shadow Types */}
            <div className="grid grid-cols-2 gap-2">
              {[
                { type: 'none', label: t.shadow_none },
                { type: 'contact', label: t.shadow_contact },
                { type: 'floor', label: t.shadow_floor },
                { type: 'reflection', label: t.shadow_reflection },
              ].map((item) => (
                <button
                  key={item.type}
                  onClick={() =>
                    onShadowChange({
                      ...shadow,
                      enabled: item.type !== 'none',
                      type: item.type as ShadowType,
                    })
                  }
                  className={`p-2.5 rounded-lg text-xs text-left border font-medium transition-all ${
                    shadow.type === item.type
                      ? 'border-kroma-600 bg-kroma-50 text-kroma-950 font-bold shadow-xs'
                      : 'border-surface-border hover:border-slate-300 text-slate-700 bg-surface-light'
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>

            {shadow.enabled && shadow.type !== 'none' && (
              <div className="space-y-4 pt-2">
                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs text-slate-600">
                    <span>{t.opacity}</span>
                    <span className="font-mono">{Math.round(shadow.opacity * 100)}%</span>
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
                  <div className="space-y-1.5">
                    <div className="flex justify-between text-xs text-slate-600">
                      <span>{t.blur}</span>
                      <span className="font-mono">{shadow.blur}px</span>
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

                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs text-slate-600">
                    <span>{t.distance}</span>
                    <span className="font-mono">{shadow.distance}px</span>
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
                  <div className="space-y-1.5">
                    <div className="flex justify-between text-xs text-slate-600">
                      <span>{t.angle}</span>
                      <span className="font-mono">{shadow.angle}°</span>
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
          <div className="space-y-5">
            <span className="text-xs font-bold text-slate-800 uppercase tracking-wider block">
              {t.tab_badges}
            </span>

            {/* Promo Badges Section */}
            <div className="space-y-3">
              <label className="text-xs font-semibold text-slate-700 block">
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
                    onClick={() =>
                      onPromoBadgeChange({
                        ...promoBadge,
                        enabled: item.type !== 'none',
                        type: item.type as PromoBadgeType,
                      })
                    }
                    className={`p-2 rounded-lg text-xs font-medium border text-left transition-all ${
                      promoBadge.type === item.type
                        ? 'border-kroma-600 bg-kroma-50 text-kroma-950 font-bold shadow-2xs'
                        : 'border-surface-border hover:border-slate-300 text-slate-700 bg-surface-light'
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Smart Watermark Section */}
            <div className="space-y-3 pt-3 border-t border-slate-200">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-slate-700">
                  {t.watermark_title}
                </label>
                <input
                  type="checkbox"
                  checked={watermark.enabled}
                  onChange={(e) => onWatermarkChange({ ...watermark, enabled: e.target.checked })}
                  className="rounded text-kroma-600"
                />
              </div>

              {watermark.enabled && (
                <div className="space-y-3 pt-2">
                  <input
                    type="text"
                    value={watermark.text}
                    onChange={(e) => onWatermarkChange({ ...watermark, text: e.target.value })}
                    placeholder={t.watermark_placeholder}
                    className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 focus:border-kroma-600 focus:outline-none"
                  />

                  {/* Watermark Positions */}
                  <div className="space-y-1">
                    <span className="text-[11px] text-slate-500">{t.watermark_position}</span>
                    <div className="grid grid-cols-2 gap-1.5">
                      {[
                        { pos: 'bottom_right', label: t.pos_bottom_right },
                        { pos: 'bottom_left', label: t.pos_bottom_left },
                        { pos: 'center', label: t.pos_center },
                        { pos: 'diagonal_repeat', label: t.pos_repeat },
                      ].map((item) => (
                        <button
                          key={item.pos}
                          onClick={() =>
                            onWatermarkChange({
                              ...watermark,
                              position: item.pos as any,
                            })
                          }
                          className={`p-1.5 text-[11px] rounded border text-center ${
                            watermark.position === item.pos
                              ? 'border-kroma-600 bg-kroma-50 text-kroma-900 font-bold'
                              : 'border-slate-200 text-slate-600'
                          }`}
                        >
                          {item.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Watermark Opacity */}
                  <div className="space-y-1">
                    <div className="flex justify-between text-[11px] text-slate-500">
                      <span>Độ trong suốt</span>
                      <span className="font-mono">{Math.round(watermark.opacity * 100)}%</span>
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
              <span className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                {t.tab_adjust}
              </span>
              <button
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
                className="text-[11px] text-slate-500 hover:text-slate-800"
              >
                Đặt lại mặc định
              </button>
            </div>

            <div className="space-y-1.5">
              <div className="flex justify-between text-xs text-slate-600">
                <span>Độ phơi sáng (Exposure)</span>
                <span className="font-mono">{adjustments.exposure}</span>
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

            <div className="space-y-1.5">
              <div className="flex justify-between text-xs text-slate-600">
                <span>Độ tương phản (Contrast)</span>
                <span className="font-mono">{adjustments.contrast}</span>
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

            <div className="space-y-1.5">
              <div className="flex justify-between text-xs text-slate-600">
                <span>Cân bằng trắng (Temperature)</span>
                <span className="font-mono">{adjustments.temperature}</span>
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

            <div className="space-y-1.5">
              <div className="flex justify-between text-xs text-slate-600">
                <span>Sắc độ màu (Tint)</span>
                <span className="font-mono">{adjustments.tint}</span>
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
      </div>
    </aside>
  );
};
