import fs from 'node:fs';
import { test, expect } from '../../fixtures/testTracker';
import { ensureAllFixtures } from '../../fixtures/imageFixtures';
import { sha256Hex, uniqueId } from '../../helpers/apiClient';

test.describe('Tier 1 — F2: Enhanced Asset Persistence (API & Storage)', () => {
  test('T1-F2-01 Upload original PNG, JPEG, and WebP assets with exact metadata', { tag: ['@baseline'] }, async ({ api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const proj = await api.post('/v1/projects', { name: uniqueId('t1_f2_01') });
    expect(proj.status).toBe(201);
    const projectId = tracker.trackProject(proj.data.id);

    const cases = [
      { filePath: fixtures.shoePng, mime: 'image/png', width: 600, height: 800 },
      { filePath: fixtures.bagJpg, mime: 'image/jpeg', width: 1200, height: 1200 },
      { filePath: fixtures.bottleWebp, mime: 'image/webp', width: 1000, height: 1000 },
    ];

    for (const c of cases) {
      const raw = fs.readFileSync(c.filePath);
      const res = await api.uploadAsset(projectId, {
        filePath: c.filePath,
        contentType: c.mime,
      });
      expect(res.status).toBe(201);
      expect(res.data.asset_id).toBeTruthy();
      expect(res.data.project_id).toBe(projectId);
      expect(res.data.sha256).toBe(sha256Hex(raw));
      expect(res.data.byte_size).toBe(raw.length);
      expect(res.data.width).toBe(c.width);
      expect(res.data.height).toBe(c.height);
      expect(res.data.mime_type).toBe(c.mime);
      expect(res.data.is_readonly).toBe(true);
    }
  });

  test('T1-F2-02 Stream original asset byte-for-byte with ETag, nosniff, and immutable Cache-Control', { tag: ['@baseline'] }, async ({ api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const proj = await api.post('/v1/projects', { name: uniqueId('t1_f2_02') });
    expect(proj.status).toBe(201);
    const projectId = tracker.trackProject(proj.data.id);

    const origBytes = fs.readFileSync(fixtures.shoePng);
    const up = await api.uploadAsset(projectId, {
      filePath: fixtures.shoePng,
      contentType: 'image/png',
    });
    expect(up.status).toBe(201);

    const dl = await api.getBinary(`/v1/assets/${up.data.asset_id}/file`);
    expect(dl.status).toBe(200);
    expect(Buffer.compare(dl.buffer, origBytes)).toBe(0);
    expect(dl.headers.get('etag')).toBe(`"${up.data.sha256}"`);
    expect(dl.headers.get('x-content-type-options')).toBe('nosniff');
    expect(dl.headers.get('cache-control') ?? '').toContain('immutable');
  });

  test('T1-F2-03 SHA-256 deduplication returns existing asset within project', { tag: ['@baseline'] }, async ({ api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const proj = await api.post('/v1/projects', { name: uniqueId('t1_f2_03') });
    expect(proj.status).toBe(201);
    const projectId = tracker.trackProject(proj.data.id);

    const first = await api.uploadAsset(projectId, {
      filePath: fixtures.tinyPng,
      filename: 'first.png',
      contentType: 'image/png',
    });
    expect(first.status).toBe(201);

    const dup = await api.uploadAsset(projectId, {
      filePath: fixtures.tinyPng,
      filename: 'duplicate_copy.png',
      contentType: 'image/png',
    });
    expect(dup.status).toBe(201);
    expect(dup.data.asset_id).toBe(first.data.asset_id);
    expect(dup.data.sha256).toBe(first.data.sha256);

    const detail = await api.get(`/v1/projects/${projectId}`);
    expect(detail.status).toBe(200);
    expect(detail.data.assets).toHaveLength(1);
  });

  test('T1-F2-04 Upload derived mask, ai_output, and thumbnail linked to original asset', { tag: ['@m1'] }, async ({ api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const proj = await api.post('/v1/projects', { name: uniqueId('t1_f2_04') });
    expect(proj.status).toBe(201);
    const projectId = tracker.trackProject(proj.data.id);

    const orig = await api.uploadAsset(projectId, {
      filePath: fixtures.shoePng,
      kind: 'original',
    });
    expect(orig.status).toBe(201);
    const origId = orig.data.asset_id;

    for (const kind of ['mask', 'ai_output', 'thumbnail'] as const) {
      const filePath = kind === 'mask' ? fixtures.maskPng : fixtures.tinyPng;
      const derived = await api.uploadAsset(projectId, {
        filePath,
        kind,
        parentAssetId: origId,
        variant: 'rmbg_v1',
        metadataJson: JSON.stringify({ brush_strokes: 2, stage: kind }),
      });
      expect(derived.status).toBe(201);
      expect(derived.data.id).toBe(derived.data.asset_id);
      expect(derived.data.kind).toBe(kind);
      expect(derived.data.parent_asset_id).toBe(origId);
      expect(derived.data.variant).toBe('rmbg_v1');
      expect(derived.data.is_readonly).toBe(false);
      expect(derived.data.metadata).toEqual({ brush_strokes: 2, stage: kind });
      expect(derived.data.file_url).toBe(`/v1/assets/${derived.data.id}/file`);
    }
  });

  test('T1-F2-05 Filter project assets by kind and parent_asset_id and fetch single asset metadata', { tag: ['@m1'] }, async ({ api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const proj = await api.post('/v1/projects', { name: uniqueId('t1_f2_05') });
    expect(proj.status).toBe(201);
    const projectId = tracker.trackProject(proj.data.id);

    const orig = await api.uploadAsset(projectId, { filePath: fixtures.shoePng, kind: 'original' });
    expect(orig.status).toBe(201);
    const mask = await api.uploadAsset(projectId, {
      filePath: fixtures.maskPng,
      kind: 'mask',
      parentAssetId: orig.data.asset_id,
      variant: 'rmbg_v1',
    });
    expect(mask.status).toBe(201);

    const listRes = await api.get(
      `/v1/projects/${projectId}/assets?kind=mask&parent_asset_id=${encodeURIComponent(orig.data.asset_id)}`,
    );
    expect(listRes.status).toBe(200);
    expect(listRes.data.total).toBe(1);
    expect(listRes.data.assets).toHaveLength(1);
    expect(listRes.data.assets[0].asset_id).toBe(mask.data.asset_id);

    const singleRes = await api.get(`/v1/assets/${mask.data.asset_id}`);
    expect(singleRes.status).toBe(200);
    expect(singleRes.data.asset_id).toBe(mask.data.asset_id);
    expect(singleRes.data.kind).toBe('mask');
    expect(singleRes.data.parent_asset_id).toBe(orig.data.asset_id);
  });

  test('T1-F2-06 PATCH derived asset metadata and DELETE parent sets child parent_asset_id to null', { tag: ['@m1'] }, async ({ api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const proj = await api.post('/v1/projects', { name: uniqueId('t1_f2_06') });
    expect(proj.status).toBe(201);
    const projectId = tracker.trackProject(proj.data.id);

    const orig = await api.uploadAsset(projectId, { filePath: fixtures.shoePng, kind: 'original' });
    expect(orig.status).toBe(201);
    const origId = orig.data.asset_id;

    const mask = await api.uploadAsset(projectId, {
      filePath: fixtures.maskPng,
      kind: 'mask',
      parentAssetId: origId,
      variant: 'initial',
    });
    expect(mask.status).toBe(201);
    const maskId = mask.data.asset_id;

    const patchRes = await api.patch(`/v1/assets/${maskId}`, {
      filename: 'hero_mask.png',
      variant: 'refined',
      metadata: { feather: 4 },
    });
    expect(patchRes.status).toBe(200);
    expect(patchRes.data.filename).toBe('hero_mask.png');
    expect(patchRes.data.variant).toBe('refined');
    expect(patchRes.data.metadata).toEqual({ feather: 4 });

    const delRes = await api.delete(`/v1/assets/${origId}`);
    expect(delRes.status).toBe(200);
    expect(delRes.data).toMatchObject({ deleted: true, asset_id: origId });

    const origFile = await api.getBinary(`/v1/assets/${origId}/file`);
    expect(origFile.status).toBe(404);

    const childAfter = await api.get(`/v1/assets/${maskId}`);
    expect(childAfter.status).toBe(200);
    expect(childAfter.data.parent_asset_id).toBeNull();
  });
});
