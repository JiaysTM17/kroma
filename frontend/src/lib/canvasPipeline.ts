import {
  AdjustmentValues,
  MarketplacePreset,
  PromoBadgeConfig,
  ShadowConfig,
  WatermarkConfig,
} from './types';

/**
 * Convert sRGB 8-bit to Linear Float [0..1]
 */
function srgbToLinear(val: number): number {
  const norm = val / 255.0;
  return norm <= 0.04045 ? norm / 12.92 : Math.pow((norm + 0.055) / 1.055, 2.4);
}

/**
 * Convert Linear Float [0..1] to sRGB 8-bit
 */
function linearToSrgb(val: number): number {
  const clamped = Math.max(0, Math.min(1, val));
  const srgb = clamped <= 0.0031308 ? clamped * 12.92 : 1.055 * Math.pow(clamped, 1 / 2.4) - 0.055;
  return Math.round(srgb * 255.0);
}

/**
 * Apply non-destructive Float32 color & tone adjustments on imageData
 */
export function applyFloat32Adjustments(
  imageData: ImageData,
  adj: AdjustmentValues
): ImageData {
  const data = imageData.data;
  const len = data.length;

  const expMult = Math.pow(2, adj.exposure / 50.0);
  const contrastFactor = (259 * (adj.contrast + 100)) / (100 * (259 - adj.contrast));
  const tempShift = adj.temperature / 200.0;
  const tintShift = adj.tint / 200.0;

  for (let i = 0; i < len; i += 4) {
    const alpha = data[i + 3];
    if (alpha === 0) continue;

    // Linear Float32
    let r = srgbToLinear(data[i]);
    let g = srgbToLinear(data[i + 1]);
    let b = srgbToLinear(data[i + 2]);

    // Exposure
    r *= expMult;
    g *= expMult;
    b *= expMult;

    // White Balance
    r += tempShift * 0.1;
    b -= tempShift * 0.1;
    g += tintShift * 0.1;

    // sRGB with Contrast
    let sr = linearToSrgb(r);
    let sg = linearToSrgb(g);
    let sb = linearToSrgb(b);

    if (adj.contrast !== 0) {
      sr = Math.max(0, Math.min(255, Math.round(contrastFactor * (sr - 128) + 128)));
      sg = Math.max(0, Math.min(255, Math.round(contrastFactor * (sg - 128) + 128)));
      sb = Math.max(0, Math.min(255, Math.round(contrastFactor * (sb - 128) + 128)));
    }

    data[i] = sr;
    data[i + 1] = sg;
    data[i + 2] = sb;
  }

  return imageData;
}

/**
 * Draw Physical Shadow: Contact, Directional Floor, or Reflection
 */
export function renderShadow(
  ctx: CanvasRenderingContext2D,
  img: HTMLImageElement | HTMLCanvasElement,
  x: number,
  y: number,
  width: number,
  height: number,
  config: ShadowConfig
) {
  if (!config.enabled || config.type === 'none') return;

  ctx.save();

  if (config.type === 'contact') {
    // Ambient occlusion contact shadow directly touching the floor
    const shadowWidth = width * 0.88;
    const shadowHeight = Math.max(8, height * 0.08);
    const shadowX = x + (width - shadowWidth) / 2;
    const shadowY = y + height - shadowHeight * 0.5 + config.distance * 0.3;

    ctx.save();
    ctx.translate(shadowX + shadowWidth / 2, shadowY + shadowHeight / 2);
    ctx.scale(shadowWidth / 2, shadowHeight / 2);
    ctx.beginPath();
    ctx.arc(0, 0, 1, 0, Math.PI * 2);

    const grad = ctx.createRadialGradient(0, 0, 0, 0, 0, 1);
    grad.addColorStop(0, `rgba(15, 23, 42, ${config.opacity})`);
    grad.addColorStop(0.4, `rgba(15, 23, 42, ${config.opacity * 0.5})`);
    grad.addColorStop(1, 'rgba(15, 23, 42, 0)');
    ctx.fillStyle = grad;
    ctx.fill();
    ctx.restore();

  } else if (config.type === 'floor') {
    // Directional projected floor shadow
    const rad = ((config.angle - 90) * Math.PI) / 180.0;
    const skewX = Math.cos(rad) * 0.65;
    const scaleY = Math.abs(Math.sin(rad)) * 0.35 + 0.12;

    ctx.save();
    ctx.globalAlpha = config.opacity;
    ctx.translate(x + width / 2, y + height);
    ctx.transform(1, 0, skewX, -scaleY, 0, config.distance);
    ctx.translate(-(x + width / 2), -(y + height));

    if (ctx.filter !== undefined) {
      ctx.filter = `blur(${Math.max(1, config.blur)}px)`;
    }

    const offCanvas = document.createElement('canvas');
    offCanvas.width = width;
    offCanvas.height = height;
    const offCtx = offCanvas.getContext('2d');
    if (offCtx) {
      offCtx.drawImage(img, 0, 0, width, height);
      offCtx.globalCompositeOperation = 'source-in';
      offCtx.fillStyle = config.color || '#0F172A';
      offCtx.fillRect(0, 0, width, height);
      ctx.drawImage(offCanvas, x, y, width, height);
    }
    ctx.restore();

  } else if (config.type === 'reflection') {
    // Premium glass/acrylic table reflection
    const reflectionHeight = height * 0.45;
    ctx.save();
    ctx.translate(0, y + height * 2 + config.distance);
    ctx.scale(1, -1);

    const offCanvas = document.createElement('canvas');
    offCanvas.width = width;
    offCanvas.height = height;
    const offCtx = offCanvas.getContext('2d');
    if (offCtx) {
      offCtx.drawImage(img, 0, 0, width, height);
      offCtx.globalCompositeOperation = 'destination-out';
      const fadeGrad = offCtx.createLinearGradient(0, height, 0, height - reflectionHeight);
      fadeGrad.addColorStop(0, 'rgba(0,0,0,0)');
      fadeGrad.addColorStop(1, 'rgba(0,0,0,1)');
      offCtx.fillStyle = fadeGrad;
      offCtx.fillRect(0, 0, width, height);

      ctx.globalAlpha = config.opacity * 0.55;
      ctx.drawImage(offCanvas, x, y, width, height);
    }
    ctx.restore();
  }

  ctx.restore();
}

/**
 * Draw Safe Zone Overlay Guides on Canvas
 */
export function drawSafeZone(
  ctx: CanvasRenderingContext2D,
  canvasWidth: number,
  canvasHeight: number,
  preset: MarketplacePreset
) {
  if (!preset.safe_zone) return;

  const { top, right, bottom, left } = preset.safe_zone;

  ctx.save();
  ctx.strokeStyle = '#06B6D4';
  ctx.lineWidth = 2;
  ctx.setLineDash([8, 6]);

  const x = left;
  const y = top;
  const w = canvasWidth - left - right;
  const h = canvasHeight - top - bottom;

  ctx.strokeRect(x, y, w, h);

  // Label Safe Area
  ctx.font = 'bold 11px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
  ctx.fillStyle = '#06B6D4';
  ctx.fillText(`Safe Zone: ${preset.marketplace}`, x + 8, y + 18);

  ctx.restore();
}

/**
 * Render Promotional Frames & E-Commerce Badges
 */
export function renderPromoBadge(
  ctx: CanvasRenderingContext2D,
  canvasWidth: number,
  canvasHeight: number,
  config: PromoBadgeConfig
) {
  if (!config.enabled || config.type === 'none') return;

  ctx.save();
  const pad = 24;

  let x = pad;
  let y = pad;

  if (config.position === 'top_right') {
    x = canvasWidth - pad - 140;
    y = pad;
  } else if (config.position === 'bottom_left') {
    x = pad;
    y = canvasHeight - pad - 45;
  } else if (config.position === 'bottom_right') {
    x = canvasWidth - pad - 140;
    y = canvasHeight - pad - 45;
  }

  if (config.type === 'flash_sale') {
    // Flash Sale Badge: Flame red/orange gradient pill
    const grad = ctx.createLinearGradient(x, y, x + 150, y + 40);
    grad.addColorStop(0, '#EF4444');
    grad.addColorStop(1, '#F97316');

    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.roundRect(x, y, 145, 42, 6);
    ctx.fill();

    ctx.fillStyle = '#FFFFFF';
    ctx.font = 'bold 13px -apple-system, BlinkMacSystemFont, sans-serif';
    ctx.fillText('⚡ FLASH SALE', x + 14, y + 26);

  } else if (config.type === 'freeship') {
    // Freeship Xtra: Emerald green badge
    ctx.fillStyle = '#059669';
    ctx.beginPath();
    ctx.roundRect(x, y, 150, 42, 6);
    ctx.fill();

    ctx.fillStyle = '#FFFFFF';
    ctx.font = 'bold 12px -apple-system, BlinkMacSystemFont, sans-serif';
    ctx.fillText('FREESHIP XTRA', x + 14, y + 26);

  } else if (config.type === 'mall') {
    // Mall Official: Deep red
    ctx.fillStyle = '#DC2626';
    ctx.beginPath();
    ctx.roundRect(x, y, 120, 36, 4);
    ctx.fill();

    ctx.fillStyle = '#FFFFFF';
    ctx.font = '900 12px -apple-system, BlinkMacSystemFont, sans-serif';
    ctx.fillText('MALL CHÍNH HÃNG', x + 8, y + 23);

  } else if (config.type === 'top_deal') {
    // Top Bán Chạy: Gold ribbon
    ctx.fillStyle = '#D97706';
    ctx.beginPath();
    ctx.roundRect(x, y, 135, 38, 6);
    ctx.fill();

    ctx.fillStyle = '#FFFFFF';
    ctx.font = 'bold 12px -apple-system, BlinkMacSystemFont, sans-serif';
    ctx.fillText('★ TOP BÁN CHẠY', x + 12, y + 24);

  } else if (config.type === 'discount_50') {
    // Discount Badge
    ctx.fillStyle = '#BE123C';
    ctx.beginPath();
    ctx.roundRect(x, y, 110, 40, 6);
    ctx.fill();

    ctx.fillStyle = '#FFFFFF';
    ctx.font = '900 15px -apple-system, BlinkMacSystemFont, sans-serif';
    ctx.fillText('GIẢM 50%', x + 12, y + 26);
  }

  ctx.restore();
}

/**
 * Render Smart Watermark Text
 */
export function renderWatermark(
  ctx: CanvasRenderingContext2D,
  canvasWidth: number,
  canvasHeight: number,
  config: WatermarkConfig
) {
  if (!config.enabled || !config.text.trim()) return;

  ctx.save();
  ctx.globalAlpha = config.opacity;
  ctx.fillStyle = config.color || '#0F172A';
  ctx.font = `bold ${config.fontSize}px -apple-system, BlinkMacSystemFont, sans-serif`;

  if (config.position === 'center') {
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(config.text, canvasWidth / 2, canvasHeight / 2);
  } else if (config.position === 'bottom_right') {
    ctx.textAlign = 'right';
    ctx.textBaseline = 'bottom';
    ctx.fillText(config.text, canvasWidth - 30, canvasHeight - 30);
  } else if (config.position === 'bottom_left') {
    ctx.textAlign = 'left';
    ctx.textBaseline = 'bottom';
    ctx.fillText(config.text, 30, canvasHeight - 30);
  } else if (config.position === 'diagonal_repeat') {
    // Diagonal security watermark pattern
    ctx.rotate(-0.35);
    for (let y = -canvasHeight; y < canvasHeight * 2; y += 140) {
      for (let x = -canvasWidth; x < canvasWidth * 2; x += 220) {
        ctx.fillText(config.text, x, y);
      }
    }
  }

  ctx.restore();
}

/**
 * Render Interactive Canva/Figma-style Transform Bounding Box with 8 handles
 */
export function renderBoundingBox(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number
) {
  ctx.save();

  // Bounding border
  ctx.strokeStyle = '#4F46E5'; // KROMA Indigo
  ctx.lineWidth = 1.5;
  ctx.strokeRect(x, y, width, height);

  // 8 Resize Handles
  const handleSize = 8;
  const half = handleSize / 2;
  const points = [
    { x: x, y: y },                       // Top-Left
    { x: x + width / 2, y: y },           // Top-Center
    { x: x + width, y: y },               // Top-Right
    { x: x + width, y: y + height / 2 },   // Middle-Right
    { x: x + width, y: y + height },       // Bottom-Right
    { x: x + width / 2, y: y + height },   // Bottom-Center
    { x: x, y: y + height },               // Bottom-Left
    { x: x, y: y + height / 2 },           // Middle-Left
  ];

  ctx.fillStyle = '#FFFFFF';
  ctx.strokeStyle = '#4F46E5';
  ctx.lineWidth = 1.5;

  points.forEach((pt) => {
    ctx.fillRect(pt.x - half, pt.y - half, handleSize, handleSize);
    ctx.strokeRect(pt.x - half, pt.y - half, handleSize, handleSize);
  });

  ctx.restore();
}

/**
 * Render Real-time Before/After Split Line & Handle
 */
export function renderSplitDivider(
  ctx: CanvasRenderingContext2D,
  canvasHeight: number,
  splitX: number
) {
  ctx.save();

  // Vertical line
  ctx.strokeStyle = '#FFFFFF';
  ctx.lineWidth = 2.5;
  ctx.beginPath();
  ctx.moveTo(splitX, 0);
  ctx.lineTo(splitX, canvasHeight);
  ctx.stroke();

  // Center grab pill
  const centerY = canvasHeight / 2;
  ctx.fillStyle = '#FFFFFF';
  ctx.shadowColor = 'rgba(0, 0, 0, 0.35)';
  ctx.shadowBlur = 8;
  ctx.beginPath();
  ctx.arc(splitX, centerY, 16, 0, Math.PI * 2);
  ctx.fill();

  // Inner arrows ◂ ▸
  ctx.fillStyle = '#0F172A';
  ctx.font = 'bold 12px sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText('◂▸', splitX, centerY);

  ctx.restore();
}
