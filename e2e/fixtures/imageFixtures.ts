import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';

export const FIXTURES_DIR = path.resolve(__dirname, '..', 'test-results', 'fixtures');
export const PYTHON_EXE = process.env.KROMA_PYTHON_EXE || 'D:\\Dự Án\\XLAS\\backend\\.venv\\Scripts\\python.exe';

export interface FixturePaths {
  shoePng: string;
  bagJpg: string;
  bottleWebp: string;
  portraitExif6Jpg: string;
  maskPng: string;
  tinyPng: string;
  unicodePng: string;
  cmykJpg: string;
  emptyPng: string;
  truncatedPng: string;
  spoofPngAsJpg: string;
  svgXssAsPng: string;
  pixelBombPng: string;
  png16Bit: string;
  apngAnimated: string;
  hdrPqPng: string;
  webpAnimated: string;
  rawCameraCr2: string;
}

export function getFixturePaths(): FixturePaths {
  return {
    shoePng: path.join(FIXTURES_DIR, 'shoe_solid_white_600x800.png'),
    bagJpg: path.join(FIXTURES_DIR, 'bag_studio_1200x1200.jpg'),
    bottleWebp: path.join(FIXTURES_DIR, 'bottle_1000x1000.webp'),
    portraitExif6Jpg: path.join(FIXTURES_DIR, 'portrait_exif6_400x600.jpg'),
    maskPng: path.join(FIXTURES_DIR, 'mask_alpha_600x800.png'),
    tinyPng: path.join(FIXTURES_DIR, 'tiny_16x16.png'),
    unicodePng: path.join(FIXTURES_DIR, 'unicode_name_SanPham_ThoiTrang.png'),
    cmykJpg: path.join(FIXTURES_DIR, 'cmyk_print.jpg'),
    emptyPng: path.join(FIXTURES_DIR, 'empty_0bytes.png'),
    truncatedPng: path.join(FIXTURES_DIR, 'truncated_corrupt.png'),
    spoofPngAsJpg: path.join(FIXTURES_DIR, 'spoof_png_as_jpg.jpg'),
    svgXssAsPng: path.join(FIXTURES_DIR, 'svg_xss_as_png.png'),
    pixelBombPng: path.join(FIXTURES_DIR, 'pixel_bomb_20000x20000.png'),
    png16Bit: path.join(FIXTURES_DIR, 'png_16bit.png'),
    apngAnimated: path.join(FIXTURES_DIR, 'apng_animated.png'),
    hdrPqPng: path.join(FIXTURES_DIR, 'hdr_pq.png'),
    webpAnimated: path.join(FIXTURES_DIR, 'webp_animated.webp'),
    rawCameraCr2: path.join(FIXTURES_DIR, 'raw_camera.cr2'),
  };
}

const PNG_SIG = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

function makePngChunk(type: string, payload: Buffer): Buffer {
  const typeBuf = Buffer.from(type, 'ascii');
  const lenBuf = Buffer.alloc(4);
  lenBuf.writeUInt32BE(payload.length, 0);
  const crcInput = Buffer.concat([typeBuf, payload]);
  const crcVal = zlib.crc32(crcInput) >>> 0;
  const crcBuf = Buffer.alloc(4);
  crcBuf.writeUInt32BE(crcVal, 0);
  return Buffer.concat([lenBuf, typeBuf, payload, crcBuf]);
}

function buildMinimalPng(options: {
  width: number;
  height: number;
  bitDepth?: number;
  colorType?: number;
  extraChunks?: Array<{ type: string; payload: Buffer }>;
  includeIdat?: boolean;
}): Buffer {
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(options.width, 0);
  ihdr.writeUInt32BE(options.height, 4);
  ihdr[8] = options.bitDepth ?? 8;
  ihdr[9] = options.colorType ?? 2; // RGB
  ihdr[10] = 0;
  ihdr[11] = 0;
  ihdr[12] = 0;

  const chunks: Buffer[] = [PNG_SIG, makePngChunk('IHDR', ihdr)];
  for (const extra of options.extraChunks ?? []) {
    chunks.push(makePngChunk(extra.type, extra.payload));
  }
  if (options.includeIdat) {
    // 1x1 RGB scanline (filter=0 + 3 bytes)
    const rawScanline = Buffer.from([0x00, 0x4f, 0x46, 0xe5]);
    const compressed = zlib.deflateSync(rawScanline);
    chunks.push(makePngChunk('IDAT', compressed));
  }
  chunks.push(makePngChunk('IEND', Buffer.alloc(0)));
  return Buffer.concat(chunks);
}

function buildAnimatedWebp(): Buffer {
  // RIFF <size> WEBP VP8X <10 bytes>
  const vp8xPayload = Buffer.alloc(10, 0);
  vp8xPayload[0] = 0x02; // Animation bit
  // canvas width - 1 (15 -> 16px)
  vp8xPayload[4] = 15;
  // canvas height - 1 (15 -> 16px)
  vp8xPayload[7] = 15;
  const header = Buffer.alloc(12);
  header.write('RIFF', 0, 'ascii');
  header.writeUInt32LE(4 + 8 + vp8xPayload.length, 4);
  header.write('WEBP', 8, 'ascii');
  const chunkHdr = Buffer.alloc(8);
  chunkHdr.write('VP8X', 0, 'ascii');
  chunkHdr.writeUInt32LE(vp8xPayload.length, 4);
  return Buffer.concat([header, chunkHdr, vp8xPayload]);
}

function generatePillowFixtures(paths: FixturePaths): void {
  const script = `
import os, sys
from PIL import Image, ImageDraw

out_dir = sys.argv[1]
os.makedirs(out_dir, exist_ok=True)

# 1. shoe_solid_white_600x800.png
shoe = Image.new("RGBA", (600, 800), (255, 255, 255, 255))
d = ImageDraw.Draw(shoe)
d.rectangle([150, 180, 450, 640], fill=(79, 70, 229, 255))
d.rectangle([150, 580, 450, 640], fill=(30, 27, 75, 255))
shoe.save(os.path.join(out_dir, "shoe_solid_white_600x800.png"), format="PNG")

# 2. bag_studio_1200x1200.jpg
bag = Image.new("RGB", (1200, 1200), (248, 250, 252))
d2 = ImageDraw.Draw(bag)
d2.rectangle([300, 300, 900, 900], fill=(244, 63, 94))
bag.save(os.path.join(out_dir, "bag_studio_1200x1200.jpg"), format="JPEG", quality=92)

# 3. bottle_1000x1000.webp
bottle = Image.new("RGBA", (1000, 1000), (0, 0, 0, 0))
d3 = ImageDraw.Draw(bottle)
d3.rectangle([300, 150, 700, 850], fill=(6, 182, 212, 255))
bottle.save(os.path.join(out_dir, "bottle_1000x1000.webp"), format="WEBP", quality=92)

# 4. portrait_exif6_400x600.jpg (stored 600x400 with EXIF Orientation=6 Rotate 90 CW -> portrait 400x600)
p = Image.new("RGB", (600, 400), (240, 245, 255))
dp = ImageDraw.Draw(p)
dp.rectangle([0, 0, 120, 400], fill=(220, 38, 38))
dp.rectangle([200, 100, 460, 300], fill=(37, 99, 235))
exif = p.getexif()
exif[274] = 6
p.save(os.path.join(out_dir, "portrait_exif6_400x600.jpg"), format="JPEG", quality=92, exif=exif)

# 5. mask_alpha_600x800.png
mask = Image.new("RGBA", (600, 800), (0, 0, 0, 0))
dm = ImageDraw.Draw(mask)
dm.rectangle([150, 180, 450, 640], fill=(255, 255, 255, 255))
mask.save(os.path.join(out_dir, "mask_alpha_600x800.png"), format="PNG")

# 6. tiny_16x16.png
tiny = Image.new("RGBA", (16, 16), (255, 255, 255, 255))
dt = ImageDraw.Draw(tiny)
dt.rectangle([4, 4, 12, 12], fill=(79, 70, 229, 255))
tiny.save(os.path.join(out_dir, "tiny_16x16.png"), format="PNG")

# 7. unicode_name_SanPham_ThoiTrang.png
uni = Image.new("RGBA", (128, 128), (255, 255, 255, 255))
du = ImageDraw.Draw(uni)
du.rectangle([24, 24, 104, 104], fill=(16, 185, 129, 255))
uni.save(os.path.join(out_dir, "unicode_name_SanPham_ThoiTrang.png"), format="PNG")

# 8. cmyk_print.jpg
cmyk = Image.new("CMYK", (64, 64), (10, 20, 30, 0))
cmyk.save(os.path.join(out_dir, "cmyk_print.jpg"), format="JPEG")
`;

  execFileSync(PYTHON_EXE, ['-c', script, FIXTURES_DIR], {
    stdio: 'pipe',
  });

  // Verify primary output exists
  if (!fs.existsSync(paths.shoePng)) {
    throw new Error(`Failed to generate Pillow fixtures in ${FIXTURES_DIR}`);
  }
}

export function ensureAllFixtures(): FixturePaths {
  fs.mkdirSync(FIXTURES_DIR, { recursive: true });
  const paths = getFixturePaths();

  if (
    !fs.existsSync(paths.shoePng) ||
    !fs.existsSync(paths.bagJpg) ||
    !fs.existsSync(paths.bottleWebp) ||
    !fs.existsSync(paths.portraitExif6Jpg) ||
    !fs.existsSync(paths.cmykJpg)
  ) {
    generatePillowFixtures(paths);
  }

  // Corrupt / Security / Boundary binary fixtures
  fs.writeFileSync(paths.emptyPng, Buffer.alloc(0));
  fs.writeFileSync(
    paths.truncatedPng,
    Buffer.concat([PNG_SIG, Buffer.alloc(32, 0x41)]),
  );
  fs.copyFileSync(paths.tinyPng, paths.spoofPngAsJpg);
  fs.writeFileSync(
    paths.svgXssAsPng,
    Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"><script>alert(1)</script></svg>', 'utf-8'),
  );
  fs.writeFileSync(
    paths.pixelBombPng,
    buildMinimalPng({ width: 20_000, height: 20_000, bitDepth: 8, colorType: 2 }),
  );
  fs.writeFileSync(
    paths.png16Bit,
    buildMinimalPng({ width: 16, height: 16, bitDepth: 16, colorType: 2, includeIdat: true }),
  );
  const acTLPayload = Buffer.alloc(8);
  acTLPayload.writeUInt32BE(2, 0); // num_frames
  acTLPayload.writeUInt32BE(0, 4); // num_plays
  fs.writeFileSync(
    paths.apngAnimated,
    buildMinimalPng({
      width: 1,
      height: 1,
      extraChunks: [{ type: 'acTL', payload: acTLPayload }],
      includeIdat: true,
    }),
  );
  fs.writeFileSync(
    paths.hdrPqPng,
    buildMinimalPng({
      width: 1,
      height: 1,
      extraChunks: [{ type: 'cICP', payload: Buffer.from([9, 16, 16, 1]) }],
      includeIdat: true,
    }),
  );
  fs.writeFileSync(paths.webpAnimated, buildAnimatedWebp());
  fs.writeFileSync(
    paths.rawCameraCr2,
    Buffer.from('II*\x00\x10\x00\x00\x00CR\x02\x00FAKE_RAW_SENSOR_DATA', 'latin1'),
  );

  return paths;
}

export function buildOversized26MbPngBuffer(): Buffer {
  const base = buildMinimalPng({ width: 1, height: 1, includeIdat: true });
  const targetSize = 26 * 1024 * 1024;
  const padded = Buffer.alloc(targetSize, 0x00);
  base.copy(padded, 0);
  return padded;
}
