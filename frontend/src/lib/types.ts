export type MarketplaceId =
  | 'shopee_1_1'
  | 'tiktok_3_4'
  | 'tiktok_1_1'
  | 'lazada_1_1'
  | 'amazon_white_85';

export interface SafeZone {
  top: number;
  right: number;
  bottom: number;
  left: number;
}

export interface MarketplacePreset {
  id: MarketplaceId;
  marketplace: string;
  name_en: string;
  name_vi: string;
  aspect_ratio: string;
  width: number;
  height: number;
  formats: string[];
  background_rgb: [number, number, number] | null;
  subject_area_ratio: number | null;
  safe_zone: SafeZone | null;
  rule_description_vi: string;
  rule_description_en: string;
}

export type ShadowType = 'none' | 'contact' | 'floor' | 'reflection';

export interface ShadowConfig {
  enabled: boolean;
  type: ShadowType;
  opacity: number;      // 0.0 to 1.0
  blur: number;         // 0 to 50px
  distance: number;     // 0 to 60px
  angle: number;        // 0 to 360 deg
  color: string;        // Hex e.g. #0F172A
  decay: number;        // 0.0 to 1.0 (for floor & reflection fade)
}

export interface AdjustmentValues {
  exposure: number;     // -100 to 100
  contrast: number;     // -100 to 100
  highlights: number;   // -100 to 100
  shadows: number;      // -100 to 100
  temperature: number;  // -100 to 100
  tint: number;         // -100 to 100
  sharpness: number;    // 0 to 100
}

export type PromoBadgeType =
  | 'none'
  | 'flash_sale'
  | 'freeship'
  | 'mall'
  | 'top_deal'
  | 'discount_50';

export interface PromoBadgeConfig {
  enabled: boolean;
  type: PromoBadgeType;
  position: 'top_left' | 'top_right' | 'bottom_left' | 'bottom_right';
  customText?: string;
}

export interface WatermarkConfig {
  enabled: boolean;
  text: string;
  opacity: number;      // 0.0 to 1.0
  position: 'bottom_right' | 'bottom_left' | 'center' | 'diagonal_repeat';
  color: string;
  fontSize: number;
}

export interface TransformState {
  offsetX: number;      // px offset from centered
  offsetY: number;
  scale: number;        // 0.5 to 2.0
}

export interface ImageAsset {
  id: string;
  name: string;
  category?: string;
  originalUrl: string;
  maskUrl?: string;
  processedUrl?: string;
  width: number;
  height: number;
  sizeBytes: number;
  hasBackgroundRemoved: boolean;
  isSample?: boolean;
}

export interface ProofingComment {
  id: string;
  author: string;
  content: string;
  x?: number;
  y?: number;
  createdAt: string;
}

export interface ProofingSession {
  id: string;
  projectId: string;
  title: string;
  clientName: string;
  status: 'pending' | 'approved' | 'changes_requested';
  createdAt: string;
  allowComments: boolean;
  comments: ProofingComment[];
}
