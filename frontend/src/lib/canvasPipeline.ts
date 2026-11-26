import { AdjustmentValues, MarketplacePreset, ShadowConfig } from './types';

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
  const tempShift = adj.temperature / 200.0; // Red/Blue shift
  const tintShift = adj.tint / 200.0;       // Green/Magenta shift

  for (let i = 0; i < len; i += 4) {
    const alpha = data[i + 3];
    if (alpha === 0) continue;

    // To Linear Float32
    let r = srgbToLinear(data[i]);
    let g = srgbToLinear(data[i + 1]);
    let b = srgbToLinear(data[i + 2]);

    // Exposure
    r *= expMult;
    g *= expMult;
    b *= expMult;

    // White Balance / Temperature & Tint
    r += tempShift * 0.1;
    b -= tempShift * 0.1;
    g += tintShift * 0.1;

    // Back to sRGB with contrast
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
    const shadowWidth = width * 0.85;
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
    grad.addColorStop(0.5, `rgba(15, 23, 42, ${config.opacity * 0.4})`);
    grad.addColorStop(1, 'rgba(15, 23, 42, 0)');
    ctx.fillStyle = grad;
    ctx.fill();
    ctx.restore();

  } else if (config.type === 'floor') {
    // Directional projected floor shadow
    const rad = ((config.angle - 90) * Math.PI) / 180.0;
    const skewX = Math.cos(rad) * 0.6;
    const scaleY = Math.abs(Math.sin(rad)) * 0.4 + 0.1;

    ctx.save();
    ctx.globalAlpha = config.opacity;
    ctx.translate(x + width / 2, y + height);
    ctx.transform(1, 0, skewX, -scaleY, 0, config.distance);
    ctx.translate(-(x + width / 2), -(y + height));

    // Blur simulation using context filter
    if (ctx.filter !== undefined) {
      ctx.filter = `blur(${Math.max(1, config.blur)}px)`;
    }

    // Draw darkened silhouette
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
      // Linear gradient alpha fade
      offCtx.globalCompositeOperation = 'destination-out';
      const fadeGrad = offCtx.createLinearGradient(0, height, 0, height - reflectionHeight);
      fadeGrad.addColorStop(0, 'rgba(0,0,0,0)');
      fadeGrad.addColorStop(1, 'rgba(0,0,0,1)');
      offCtx.fillStyle = fadeGrad;
      offCtx.fillRect(0, 0, width, height);

      ctx.globalAlpha = config.opacity * 0.6;
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
  ctx.strokeStyle = '#06B6D4'; // Electric Cyan guide lines
  ctx.lineWidth = 1.5;
  ctx.setLineDash([6, 6]);

  const x = left;
  const y = top;
  const w = canvasWidth - left - right;
  const h = canvasHeight - top - bottom;

  ctx.strokeRect(x, y, w, h);

  // Label Safe Area
  ctx.font = '10px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
  ctx.fillStyle = '#06B6D4';
  ctx.fillText(`Safe Zone: ${preset.marketplace}`, x + 6, y + 14);

  ctx.restore();
}
