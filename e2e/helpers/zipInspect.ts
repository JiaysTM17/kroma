import { execFileSync } from 'node:child_process';
import JSZip from 'jszip';
import { PYTHON_EXE } from '../fixtures/imageFixtures';

export interface ParsedImageHeader {
  format: 'png' | 'jpeg' | 'webp';
  width: number;
  height: number;
}

export function parseImageDimensions(buf: Buffer): ParsedImageHeader {
  // PNG: 8-byte sig + IHDR
  if (
    buf.length >= 24 &&
    buf[0] === 0x89 &&
    buf[1] === 0x50 &&
    buf[2] === 0x4e &&
    buf[3] === 0x47
  ) {
    return {
      format: 'png',
      width: buf.readUInt32BE(16),
      height: buf.readUInt32BE(20),
    };
  }

  // JPEG: 0xFF 0xD8 0xFF + SOF0/SOF2
  if (buf.length >= 4 && buf[0] === 0xff && buf[1] === 0xd8 && buf[2] === 0xff) {
    let offset = 2;
    while (offset + 4 < buf.length) {
      if (buf[offset] !== 0xff) {
        offset++;
        continue;
      }
      const marker = buf[offset + 1];
      offset += 2;
      if (marker === 0xd8 || marker === 0xd9 || marker === 0x00) continue;
      if (offset + 2 > buf.length) break;
      const segLen = buf.readUInt16BE(offset);
      if (
        marker === 0xc0 ||
        marker === 0xc1 ||
        marker === 0xc2 ||
        marker === 0xc3 ||
        marker === 0xc5 ||
        marker === 0xc6 ||
        marker === 0xc7 ||
        marker === 0xc9 ||
        marker === 0xca ||
        marker === 0xcb
      ) {
        if (offset + 7 <= buf.length) {
          const height = buf.readUInt16BE(offset + 3);
          const width = buf.readUInt16BE(offset + 5);
          return { format: 'jpeg', width, height };
        }
      }
      offset += segLen;
    }
    throw new Error('Could not find SOF marker in JPEG buffer');
  }

  // WebP: RIFF....WEBP
  if (
    buf.length >= 30 &&
    buf.toString('ascii', 0, 4) === 'RIFF' &&
    buf.toString('ascii', 8, 12) === 'WEBP'
  ) {
    const chunk = buf.toString('ascii', 12, 16);
    if (chunk === 'VP8 ' && buf.length >= 30) {
      const width = buf.readUInt16LE(26) & 0x3fff;
      const height = buf.readUInt16LE(28) & 0x3fff;
      return { format: 'webp', width, height };
    }
    if (chunk === 'VP8L' && buf.length >= 25) {
      const bits = buf.readUInt32LE(21);
      const width = (bits & 0x3fff) + 1;
      const height = ((bits >> 14) & 0x3fff) + 1;
      return { format: 'webp', width, height };
    }
    if (chunk === 'VP8X' && buf.length >= 30) {
      const width = 1 + (buf[24] | (buf[25] << 8) | (buf[26] << 16));
      const height = 1 + (buf[27] | (buf[28] << 8) | (buf[29] << 16));
      return { format: 'webp', width, height };
    }
  }

  throw new Error(`Unknown or corrupt image format (first 16 bytes: ${buf.subarray(0, 16).toString('hex')})`);
}

export interface InspectedImageEntry {
  name: string;
  bytes: Buffer;
  header: ParsedImageHeader;
}

export interface InspectedZip {
  entries: string[];
  images: InspectedImageEntry[];
  manifestJson: Record<string, any> | null;
  manifestTxt: string | null;
}

export async function inspectZipBuffer(zipBuf: Buffer): Promise<InspectedZip> {
  const zip = await JSZip.loadAsync(zipBuf);
  const entries: string[] = [];
  const images: InspectedImageEntry[] = [];
  let manifestJson: Record<string, any> | null = null;
  let manifestTxt: string | null = null;

  for (const [name, obj] of Object.entries(zip.files)) {
    if (obj.dir) continue;
    entries.push(name);
    const bytes = await obj.async('nodebuffer');
    if (name.endsWith('manifest.json')) {
      manifestJson = JSON.parse(bytes.toString('utf-8'));
    } else if (name.endsWith('manifest.txt')) {
      manifestTxt = bytes.toString('utf-8');
    } else if (/\.(png|jpe?g|webp)$/i.test(name)) {
      images.push({
        name,
        bytes,
        header: parseImageDimensions(bytes),
      });
    }
  }

  return { entries, images, manifestJson, manifestTxt };
}

export interface PillowPixelProbe {
  width: number;
  height: number;
  mode: string;
  topLeftRgb: [number, number, number];
  bottomRightRgb: [number, number, number];
  centerRgb: [number, number, number];
  topBandMeanRgb: [number, number, number];
}

export function probeImagePixelsWithPillow(imageBuf: Buffer): PillowPixelProbe {
  const py = `
import io, json, sys
from PIL import Image

raw = sys.stdin.buffer.read()
with Image.open(io.BytesIO(raw)) as im:
    rgb = im.convert("RGB")
    w, h = rgb.size
    tl = rgb.getpixel((0, 0))
    br = rgb.getpixel((w - 1, h - 1))
    ctr = rgb.getpixel((w // 2, h // 2))
    # Mean RGB across top 10% strip (useful for EXIF orientation verification)
    strip_h = max(1, h // 10)
    r_sum = g_sum = b_sum = count = 0
    for y in range(0, strip_h, max(1, strip_h // 5)):
        for x in range(0, w, max(1, w // 20)):
            r, g, b = rgb.getpixel((x, y))
            r_sum += r; g_sum += g; b_sum += b; count += 1
    print(json.dumps({
        "width": w,
        "height": h,
        "mode": im.mode,
        "topLeftRgb": list(tl),
        "bottomRightRgb": list(br),
        "centerRgb": list(ctr),
        "topBandMeanRgb": [round(r_sum / count), round(g_sum / count), round(b_sum / count)],
    }))
`;
  const out = execFileSync(PYTHON_EXE, ['-c', py], {
    input: imageBuf,
    stdio: ['pipe', 'pipe', 'pipe'],
  });
  return JSON.parse(out.toString('utf-8')) as PillowPixelProbe;
}
