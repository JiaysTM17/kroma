import { test, expect } from '../../fixtures/testTracker';
import { MarketplacePresetDto, uniqueId } from '../../helpers/apiClient';

test.describe('Tier 1 — F3: Preset Customization API', () => {
  test('T1-F3-01 List 5 canonical system presets with normalized safe_zone and bilingual descriptions', { tag: ['@m1'] }, async ({ api }) => {
    const res = await api.get('/v1/presets');
    expect(res.status).toBe(200);
    expect(Array.isArray(res.data.presets)).toBe(true);
    expect(res.data.total).toBeGreaterThanOrEqual(5);

    const byId = new Map<string, MarketplacePresetDto>(
      res.data.presets.map((p: MarketplacePresetDto) => [p.id, p]),
    );

    for (const id of ['shopee_1_1', 'tiktok_3_4', 'tiktok_1_1', 'lazada_1_1', 'amazon_white_85']) {
      const p = byId.get(id);
      expect(p, `Missing system preset ${id}`).toBeDefined();
      expect(p!.is_system).toBe(true);
      expect(p!.rule_description_en).toBeTruthy();
      expect(p!.rule_description_vi).toBeTruthy();
      if (p!.safe_zone) {
        for (const edge of ['top', 'right', 'bottom', 'left'] as const) {
          expect(p!.safe_zone[edge]).toBeGreaterThanOrEqual(0);
          expect(p!.safe_zone[edge]).toBeLessThanOrEqual(1);
        }
      }
    }

    expect(byId.get('shopee_1_1')!.width).toBe(1024);
    expect(byId.get('shopee_1_1')!.height).toBe(1024);
    expect(byId.get('tiktok_3_4')!.width).toBe(1200);
    expect(byId.get('tiktok_3_4')!.height).toBe(1600);
    expect(byId.get('lazada_1_1')!.width).toBe(1000);
    expect(byId.get('lazada_1_1')!.height).toBe(1000);
    expect(byId.get('amazon_white_85')!.width).toBe(2000);
    expect(byId.get('amazon_white_85')!.height).toBe(2000);
    expect(byId.get('amazon_white_85')!.background_rgb).toEqual([255, 255, 255]);
    expect(byId.get('amazon_white_85')!.subject_area_ratio).toBe(0.85);
  });

  test('T1-F3-02 Get single preset by ID and legacy /api/v1/presets/amazon_hero compatibility', { tag: ['@m1'] }, async ({ api }) => {
    const tiktok = await api.get('/v1/presets/tiktok_3_4');
    expect(tiktok.status).toBe(200);
    expect(tiktok.data.width).toBe(1200);
    expect(tiktok.data.height).toBe(1600);

    const legacyAmazon = await api.get('/api/v1/presets/amazon_hero');
    expect(legacyAmazon.status).toBe(200);
    expect(legacyAmazon.data.width).toBe(2000);
    expect(legacyAmazon.data.height).toBe(2000);
  });

  test('T1-F3-03 Create custom preset with derived aspect ratio and normalized safe_zone', { tag: ['@m1'] }, async ({ api, tracker }) => {
    const id = uniqueId('e2e_preset_c').toLowerCase();
    tracker.trackCustomPreset(id);

    const createRes = await api.post('/v1/presets', {
      id,
      marketplace: 'custom',
      name_en: 'Flash Banner',
      name_vi: 'Banner Flash',
      rule_description_en: 'Custom 4:5 promotional banner',
      rule_description_vi: 'Banner khuyến mãi 4:5 tùy chỉnh',
      width: 1080,
      height: 1350,
      formats: ['webp', 'png'],
      background_rgb: [248, 250, 252],
      subject_area_ratio: 0.8,
      safe_zone: { top: 0.05, right: 0.05, bottom: 0.1, left: 0.05 },
    });
    expect(createRes.status).toBe(201);
    expect(createRes.data.id).toBe(id);
    expect(createRes.data.aspect_ratio).toBe('4:5');
    expect(createRes.data.is_system).toBe(false);
    expect(createRes.data.editable).toBe(true);

    const fetchRes = await api.get(`/v1/presets/${id}`);
    expect(fetchRes.status).toBe(200);
    expect(fetchRes.data.width).toBe(1080);
    expect(fetchRes.data.height).toBe(1350);
  });

  test('T1-F3-04 Update custom preset via PATCH and PUT', { tag: ['@m1'] }, async ({ api, tracker }) => {
    const id = uniqueId('e2e_preset_u').toLowerCase();
    tracker.trackCustomPreset(id);

    const createRes = await api.post('/v1/presets', {
      id,
      marketplace: 'custom',
      name_en: 'Initial Preset',
      name_vi: 'Mẫu ban đầu',
      width: 1080,
      height: 1350,
      formats: ['webp', 'png'],
      background_rgb: [255, 255, 255],
      subject_area_ratio: 0.8,
    });
    expect(createRes.status).toBe(201);
    const createdAtUpdated = createRes.data.updated_at;

    const patchRes = await api.patch(`/v1/presets/${id}`, {
      width: 1200,
      height: 1200,
      background_rgb: null,
    });
    expect(patchRes.status).toBe(200);
    expect(patchRes.data.aspect_ratio).toBe('1:1');
    expect(patchRes.data.background_rgb).toBeNull();

    const putRes = await api.put(`/v1/presets/${id}`, {
      marketplace: 'custom',
      name_en: 'Updated Preset',
      name_vi: 'Mẫu đã cập nhật',
      width: 1200,
      height: 1200,
      formats: ['jpeg'],
      background_rgb: null,
      subject_area_ratio: 0.8,
    });
    expect(putRes.status).toBe(200);
    expect(putRes.data.name_vi).toBe('Mẫu đã cập nhật');
    expect(putRes.data.formats).toEqual(['jpeg']);
    if (createdAtUpdated && putRes.data.updated_at) {
      expect(putRes.data.updated_at >= createdAtUpdated).toBe(true);
    }
  });

  test('T1-F3-05 Delete custom preset removes it from /v1/presets/{id}', { tag: ['@m1'] }, async ({ api, tracker }) => {
    const id = uniqueId('e2e_preset_d').toLowerCase();
    tracker.trackCustomPreset(id);

    const createRes = await api.post('/v1/presets', {
      id,
      marketplace: 'custom',
      name_en: 'Temp Delete',
      name_vi: 'Xóa tạm',
      width: 800,
      height: 800,
      formats: ['png'],
    });
    expect(createRes.status).toBe(201);

    const delRes = await api.delete(`/v1/presets/${id}`);
    expect(delRes.status).toBe(200);
    expect(delRes.data).toMatchObject({ deleted: true, preset_id: id });

    const getAfter = await api.get(`/v1/presets/${id}`);
    expect(getAfter.status).toBe(404);
  });

  test('T1-F3-06 Customize system preset and restore canonical defaults via /reset', { tag: ['@m1'] }, async ({ api, tracker }) => {
    tracker.trackSystemPreset('shopee_1_1');

    const patchRes = await api.patch('/v1/presets/shopee_1_1', {
      width: 1200,
      height: 1200,
    });
    expect(patchRes.status).toBe(200);
    expect(patchRes.data.width).toBe(1200);
    expect(patchRes.data.height).toBe(1200);

    const verifyGet = await api.get('/v1/presets/shopee_1_1');
    expect(verifyGet.status).toBe(200);
    expect(verifyGet.data.width).toBe(1200);

    const resetRes = await api.post('/v1/presets/shopee_1_1/reset');
    expect(resetRes.status).toBe(200);
    expect(resetRes.data.width).toBe(1024);
    expect(resetRes.data.height).toBe(1024);
    expect(resetRes.data.formats).toEqual(['webp', 'jpeg']);
  });
});
