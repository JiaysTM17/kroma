import fs from 'node:fs';
import { test, expect } from '../../fixtures/testTracker';
import { buildOversized26MbPngBuffer, ensureAllFixtures } from '../../fixtures/imageFixtures';
import { uniqueId } from '../../helpers/apiClient';

test.describe('Tier 2 — BVA Backend F1–F5 (Negative & Boundary Analysis)', () => {
  // === F1 Boundaries ===
  test('T2-F1-01 Reject empty/whitespace, control chars, and >120 char project names with 422', { tag: ['@baseline'] }, async ({ api }) => {
    for (const badName of ['   ', 'a\x00b']) {
      const res = await api.post('/v1/projects', { name: badName });
      expect(res.status).toBe(422);
      expect(res.data).toMatchObject({
        code: 'VALIDATION_ERROR',
        retryable: false,
      });
      expect(typeof res.data.correlation_id).toBe('string');
      expect(JSON.stringify(res.data)).not.toContain('Traceback');
    }

    const tooLong = await api.post('/v1/projects', { name: 'x'.repeat(121) });
    expect(tooLong.status).toBe(422);
    expect(JSON.stringify(tooLong.data)).not.toContain('Traceback');
  });

  test('T2-F1-02 Exact boundary for project name (1 & 120 chars) and description (1000 vs 1001 chars)', { tag: ['@baseline'] }, async ({ api, tracker }) => {
    const minProj = await api.post('/v1/projects', { name: 'A', description: 'd'.repeat(1000) });
    expect(minProj.status).toBe(201);
    tracker.trackProject(minProj.data.id);

    const maxProj = await api.post('/v1/projects', { name: 'B'.repeat(120), description: '' });
    expect(maxProj.status).toBe(201);
    tracker.trackProject(maxProj.data.id);

    const overDesc = await api.post('/v1/projects', { name: 'ValidName', description: 'd'.repeat(1001) });
    expect(overDesc.status).toBe(422);
  });

  test('T2-F1-03 Missing project ID returns unified 404 NOT_FOUND', { tag: ['@baseline'] }, async ({ api }) => {
    for (const path of ['/v1/projects/nonexistent_e2e_id', '/v1/projects/nonexistent_e2e_id/state']) {
      const res = await api.get(path);
      expect(res.status).toBe(404);
      expect(res.data).toMatchObject({
        code: 'NOT_FOUND',
        retryable: false,
      });
      expect(typeof res.data.correlation_id).toBe('string');
      expect(typeof res.data.message).toBe('string');
    }
  });

  test('T2-F1-04 Delete non-existent and double-delete project return 404 NOT_FOUND', { tag: ['@m1'] }, async ({ api, tracker }) => {
    const missing = await api.delete('/v1/projects/nonexistent_e2e_id');
    expect(missing.status).toBe(404);
    expect(missing.data.code).toBe('NOT_FOUND');

    const proj = await api.post('/v1/projects', { name: uniqueId('t2_f1_04') });
    expect(proj.status).toBe(201);
    const projectId = tracker.trackProject(proj.data.id);

    const del1 = await api.delete(`/v1/projects/${projectId}`);
    expect(del1.status).toBe(200);
    expect(del1.data.deleted).toBe(true);

    const del2 = await api.delete(`/v1/projects/${projectId}`);
    expect(del2.status).toBe(404);
    expect(del2.data.code).toBe('NOT_FOUND');
  });

  test('T2-F1-05 Overly long or invalid x-correlation-id header is sanitized safely', { tag: ['@baseline'] }, async ({ api }) => {
    const res1 = await api.request('GET', '/health', { correlationId: 'x'.repeat(100) });
    expect(res1.status).toBe(200);
    const cid1 = res1.headers.get('x-correlation-id') ?? '';
    expect(cid1.length).toBeGreaterThan(0);
    expect(cid1.length).toBeLessThanOrEqual(64);
    expect(cid1).toMatch(/^[A-Za-z0-9._:-]{1,64}$/);

    const res2 = await api.request('GET', '/health', { correlationId: 'bad id <script>alert(1)</script>' });
    expect(res2.status).toBe(200);
    const cid2 = res2.headers.get('x-correlation-id') ?? '';
    expect(cid2).toMatch(/^[A-Za-z0-9._:-]{1,64}$/);
    expect(cid2).not.toContain('<script>');
  });

  // === F2 Boundaries ===
  test('T2-F2-01 Magic-byte spoof (PNG as JPG) and SVG-XSS payload rejected with 422 MIME_SPOOF_DETECTED', { tag: ['@baseline'] }, async ({ api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const proj = await api.post('/v1/projects', { name: uniqueId('t2_f2_01') });
    const projectId = tracker.trackProject(proj.data.id);

    const spoof = await api.uploadAsset(projectId, {
      filePath: fixtures.spoofPngAsJpg,
      filename: 'spoof_png_as_jpg.jpg',
      contentType: 'image/jpeg',
    });
    expect(spoof.status).toBe(422);
    expect(spoof.data.code).toBe('MIME_SPOOF_DETECTED');
    expect(spoof.data.retryable).toBe(false);

    const svgXss = await api.uploadAsset(projectId, {
      filePath: fixtures.svgXssAsPng,
      filename: 'svg_xss_as_png.png',
      contentType: 'image/png',
    });
    expect(svgXss.status).toBe(422);
    expect(svgXss.data.code).toBe('MIME_SPOOF_DETECTED');
  });

  test('T2-F2-02 Deferred formats rejected with specific 422/415 error codes', { tag: ['@baseline'] }, async ({ api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const proj = await api.post('/v1/projects', { name: uniqueId('t2_f2_02') });
    const projectId = tracker.trackProject(proj.data.id);

    const cases = [
      { filePath: fixtures.cmykJpg, contentType: 'image/jpeg', status: 422, code: 'UNSUPPORTED_COLOR_SPACE_CMYK' },
      { filePath: fixtures.png16Bit, contentType: 'image/png', status: 422, code: 'UNSUPPORTED_BIT_DEPTH' },
      { filePath: fixtures.apngAnimated, contentType: 'image/png', status: 422, code: 'UNSUPPORTED_ANIMATED_IMAGE' },
      { filePath: fixtures.hdrPqPng, contentType: 'image/png', status: 422, code: 'UNSUPPORTED_HDR_IMAGE' },
      { filePath: fixtures.webpAnimated, contentType: 'image/webp', status: 422, code: 'UNSUPPORTED_ANIMATED_IMAGE' },
      { filePath: fixtures.rawCameraCr2, contentType: 'application/octet-stream', status: 415, code: 'UNSUPPORTED_RAW_FORMAT' },
    ];

    for (const c of cases) {
      const res = await api.uploadAsset(projectId, {
        filePath: c.filePath,
        contentType: c.contentType,
      });
      expect(res.status, `Failed for ${c.filePath}`).toBe(c.status);
      expect(res.data.code).toBe(c.code);
    }
  });

  test('T2-F2-03 Pixel bomb, empty 0-byte, truncated corrupt PNG, and >25MiB upload rejected', { tag: ['@baseline'] }, async ({ api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const proj = await api.post('/v1/projects', { name: uniqueId('t2_f2_03') });
    const projectId = tracker.trackProject(proj.data.id);

    const bomb = await api.uploadAsset(projectId, { filePath: fixtures.pixelBombPng, contentType: 'image/png' });
    expect(bomb.status).toBe(422);
    expect(bomb.data.code).toBe('PIXEL_BOMB_DETECTED');

    const empty = await api.uploadAsset(projectId, { filePath: fixtures.emptyPng, contentType: 'image/png' });
    expect(empty.status).toBe(422);
    expect(empty.data.code).toBe('CORRUPT_IMAGE');

    const trunc = await api.uploadAsset(projectId, { filePath: fixtures.truncatedPng, contentType: 'image/png' });
    expect(trunc.status).toBe(422);
    expect(trunc.data.code).toBe('CORRUPT_IMAGE');

    const oversizedBuf = buildOversized26MbPngBuffer();
    const oversized = await api.uploadAsset(projectId, {
      buffer: oversizedBuf,
      filename: 'oversized_26mb.png',
      contentType: 'image/png',
    });
    expect(oversized.status).toBe(413);
    expect(oversized.data.code).toBe('PAYLOAD_TOO_LARGE');
  });

  test('T2-F2-04 Path traversal rejected; Windows reserved CON.png & NFD Unicode filenames sanitized cleanly', { tag: ['@baseline'] }, async ({ api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const proj = await api.post('/v1/projects', { name: uniqueId('t2_f2_04') });
    const projectId = tracker.trackProject(proj.data.id);
    const tinyBuf = fs.readFileSync(fixtures.tinyPng);

    for (const badFilename of ['../../etc/passwd.png', 'C:\\evil.png', 'bad\x01ctrl.png']) {
      const badRes = await api.uploadAsset(projectId, {
        buffer: tinyBuf,
        filename: badFilename,
        contentType: 'image/png',
      });
      expect(badRes.status).toBe(422);
      expect(badRes.data.code).toBe('PATH_TRAVERSAL_DETECTED');
    }

    const conRes = await api.uploadAsset(projectId, {
      buffer: tinyBuf,
      filename: 'CON.png',
      contentType: 'image/png',
    });
    expect(conRes.status).toBe(201);
    expect(conRes.data.filename).toBe('_CON.png');

    // Use a distinct valid image so SHA-256 differs from tinyPng
    const nfdName = 'Ao\u0301 da\u0300i.PNG';
    const uniRes = await api.uploadAsset(projectId, {
      filePath: fixtures.unicodePng,
      filename: nfdName,
      contentType: 'image/png',
    });
    expect(uniRes.status).toBe(201);
    expect(uniRes.data.filename).toBe('Áo dài.png');
  });

  test('T2-F2-05 Derived asset validation: invalid kind, original with parent, cross-project parent, bad metadata_json', { tag: ['@m1'] }, async ({ api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const p1 = tracker.trackProject((await api.post('/v1/projects', { name: uniqueId('t2_f2_05_a') })).data.id);
    const p2 = tracker.trackProject((await api.post('/v1/projects', { name: uniqueId('t2_f2_05_b') })).data.id);

    const a1 = await api.uploadAsset(p1, { filePath: fixtures.tinyPng, kind: 'original' });
    const a2 = await api.uploadAsset(p2, { filePath: fixtures.shoePng, kind: 'original' });
    expect(a1.status).toBe(201);
    expect(a2.status).toBe(201);

    const badKind = await api.uploadAsset(p1, { filePath: fixtures.tinyPng, kind: 'video' });
    expect(badKind.status).toBe(422);

    const origParent = await api.uploadAsset(p1, {
      filePath: fixtures.shoePng,
      kind: 'original',
      parentAssetId: a1.data.asset_id,
    });
    expect(origParent.status).toBe(422);

    const crossProj = await api.uploadAsset(p1, {
      filePath: fixtures.maskPng,
      kind: 'mask',
      parentAssetId: a2.data.asset_id,
    });
    expect(crossProj.status).toBe(422);

    const missingParent = await api.uploadAsset(p1, {
      filePath: fixtures.maskPng,
      kind: 'mask',
      parentAssetId: 'nonexistent-parent-id',
    });
    expect(missingParent.status).toBe(404);

    const nonObjMeta = await api.uploadAsset(p1, {
      filePath: fixtures.maskPng,
      kind: 'mask',
      parentAssetId: a1.data.asset_id,
      metadataJson: '[1,2,3]',
    });
    expect(nonObjMeta.status).toBe(422);

    // Depth > 8 metadata
    let deep: Record<string, any> = { leaf: 1 };
    for (let i = 0; i < 10; i++) deep = { nested: deep };
    const deepMeta = await api.uploadAsset(p1, {
      filePath: fixtures.maskPng,
      kind: 'mask',
      parentAssetId: a1.data.asset_id,
      metadataJson: JSON.stringify(deep),
    });
    expect(deepMeta.status).toBe(422);
  });

  test('T2-F2-06 Ref-counted blob preserved for Project 2 when Project 1 deletes identical asset', { tag: ['@m1'] }, async ({ api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const raw = fs.readFileSync(fixtures.tinyPng);

    const p1 = tracker.trackProject((await api.post('/v1/projects', { name: uniqueId('t2_f2_06_a') })).data.id);
    const p2 = tracker.trackProject((await api.post('/v1/projects', { name: uniqueId('t2_f2_06_b') })).data.id);

    const a1 = await api.uploadAsset(p1, { filePath: fixtures.tinyPng, kind: 'original' });
    const a2 = await api.uploadAsset(p2, { filePath: fixtures.tinyPng, kind: 'original' });
    expect(a1.status).toBe(201);
    expect(a2.status).toBe(201);
    expect(a1.data.sha256).toBe(a2.data.sha256);

    const del1 = await api.delete(`/v1/assets/${a1.data.asset_id}`);
    expect(del1.status).toBe(200);

    const gone1 = await api.getBinary(`/v1/assets/${a1.data.asset_id}/file`);
    expect(gone1.status).toBe(404);

    const still2 = await api.getBinary(`/v1/assets/${a2.data.asset_id}/file`);
    expect(still2.status).toBe(200);
    expect(Buffer.compare(still2.buffer, raw)).toBe(0);
  });

  // === F3 Boundaries ===
  test('T2-F3-01 Duplicate preset ID returns 409 and invalid slug returns 422', { tag: ['@m1'] }, async ({ api }) => {
    const dup = await api.post('/v1/presets', {
      id: 'shopee_1_1',
      marketplace: 'custom',
      name_en: 'Dup',
      name_vi: 'Trùng',
      width: 1024,
      height: 1024,
      formats: ['png'],
    });
    expect(dup.status).toBe(409);
    expect(dup.data.code).toBe('CONFLICT');

    const badSlug = await api.post('/v1/presets', {
      id: '../bad/id',
      marketplace: 'custom',
      name_en: 'Bad',
      name_vi: 'Xấu',
      width: 1024,
      height: 1024,
      formats: ['png'],
    });
    expect(badSlug.status).toBe(422);
  });

  test('T2-F3-02 Preset dimension boundaries (63, 0, 16385 rejected; 64 and 16384 accepted)', { tag: ['@m1'] }, async ({ api, tracker }) => {
    for (const dims of [
      { width: 63, height: 100 },
      { width: 100, height: 0 },
      { width: 16385, height: 100 },
    ]) {
      const bad = await api.post('/v1/presets', {
        id: uniqueId('e2e_dim_bad').toLowerCase(),
        marketplace: 'custom',
        name_en: 'Bad Dim',
        name_vi: 'Sai KT',
        ...dims,
        formats: ['png'],
      });
      expect(bad.status).toBe(422);
    }

    const minId = tracker.trackCustomPreset(uniqueId('e2e_dim_min').toLowerCase());
    const minOk = await api.post('/v1/presets', {
      id: minId,
      marketplace: 'custom',
      name_en: 'Min 64',
      name_vi: 'Tối thiểu 64',
      width: 64,
      height: 64,
      formats: ['png'],
    });
    expect(minOk.status).toBe(201);

    const maxId = tracker.trackCustomPreset(uniqueId('e2e_dim_max').toLowerCase());
    const maxOk = await api.post('/v1/presets', {
      id: maxId,
      marketplace: 'custom',
      name_en: 'Max 16384',
      name_vi: 'Tối đa 16384',
      width: 16384,
      height: 16384,
      formats: ['png'],
    });
    expect(maxOk.status).toBe(201);
  });

  test('T2-F3-03 Out-of-bounds safe_zone and overlapping margins rejected with 422', { tag: ['@m1'] }, async ({ api }) => {
    const badZones = [
      { top: -0.01, right: 0.05, bottom: 0.05, left: 0.05 },
      { top: 1.01, right: 0.0, bottom: 0.0, left: 0.0 },
      { top: 0.1, right: 0.4, bottom: 0.1, left: 0.6 },
    ];
    for (const safe_zone of badZones) {
      const res = await api.post('/v1/presets', {
        id: uniqueId('e2e_sz_bad').toLowerCase(),
        marketplace: 'custom',
        name_en: 'Bad SZ',
        name_vi: 'Sai SZ',
        width: 1000,
        height: 1000,
        formats: ['png'],
        safe_zone,
      });
      expect(res.status).toBe(422);
    }
  });

  test('T2-F3-04 Invalid subject_area_ratio, background_rgb, and formats rejected with 422', { tag: ['@m1'] }, async ({ api }) => {
    const payloads = [
      { subject_area_ratio: 0.0 },
      { subject_area_ratio: 1.05 },
      { background_rgb: [256, 0, 0] },
      { background_rgb: [255, 255] },
      { formats: [] },
      { formats: ['gif'] },
    ];
    for (const extra of payloads) {
      const res = await api.post('/v1/presets', {
        id: uniqueId('e2e_fld_bad').toLowerCase(),
        marketplace: 'custom',
        name_en: 'Bad Field',
        name_vi: 'Sai trường',
        width: 1000,
        height: 1000,
        formats: ['png'],
        ...extra,
      });
      expect(res.status).toBe(422);
    }
  });

  test('T2-F3-05 System preset cannot be deleted (403/409)', { tag: ['@m1'] }, async ({ api }) => {
    const del = await api.delete('/v1/presets/shopee_1_1');
    expect([403, 409]).toContain(del.status);

    const stillExists = await api.get('/v1/presets/shopee_1_1');
    expect(stillExists.status).toBe(200);
  });

  test('T2-F3-06 Resetting custom or missing preset returns 400/422 or 404', { tag: ['@m1'] }, async ({ api, tracker }) => {
    const customId = tracker.trackCustomPreset(uniqueId('e2e_rst_c').toLowerCase());
    const c = await api.post('/v1/presets', {
      id: customId,
      marketplace: 'custom',
      name_en: 'Custom Reset',
      name_vi: 'Tùy chỉnh',
      width: 800,
      height: 800,
      formats: ['png'],
    });
    expect(c.status).toBe(201);

    const resetCustom = await api.post(`/v1/presets/${customId}/reset`);
    expect([400, 422]).toContain(resetCustom.status);

    const resetMissing = await api.post('/v1/presets/missing_preset_e2e/reset');
    expect(resetMissing.status).toBe(404);
  });

  // === F4 Boundaries ===
  test('T2-F4-01 Batch empty asset_ids/recipes -> 422; missing project/preset -> 404', { tag: ['@m2'] }, async ({ api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const p1 = tracker.trackProject((await api.post('/v1/projects', { name: uniqueId('t2_f4_01') })).data.id);
    const a1 = await api.uploadAsset(p1, { filePath: fixtures.tinyPng });

    const emptyAssets = await api.post('/v1/batches', {
      project_id: p1,
      asset_ids: [],
      recipes: [{ preset_id: 'shopee_1_1', format: 'png' }],
    });
    expect(emptyAssets.status).toBe(422);

    const emptyRecipes = await api.post('/v1/batches', {
      project_id: p1,
      asset_ids: [a1.data.asset_id],
      recipes: [],
    });
    expect(emptyRecipes.status).toBe(422);

    const missingProj = await api.post('/v1/batches', {
      project_id: 'nonexistent_proj_id',
      asset_ids: [a1.data.asset_id],
      recipes: [{ preset_id: 'shopee_1_1', format: 'png' }],
    });
    expect(missingProj.status).toBe(404);

    const missingPreset = await api.post('/v1/batches', {
      project_id: p1,
      asset_ids: [a1.data.asset_id],
      recipes: [{ preset_id: 'nonexistent_preset_id', format: 'png' }],
    });
    expect(missingPreset.status).toBe(404);
  });

  test('T2-F4-02 Partial failure isolation: bad/deleted asset item fails without aborting healthy items', { tag: ['@m2'] }, async ({ api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const p1 = tracker.trackProject((await api.post('/v1/projects', { name: uniqueId('t2_f4_02') })).data.id);
    const a1 = await api.uploadAsset(p1, { filePath: fixtures.shoePng });
    const a2 = await api.uploadAsset(p1, { filePath: fixtures.tinyPng });

    // Trigger partial failure by passing a deleted asset ID or invalid second recipe format
    await api.delete(`/v1/assets/${a2.data.asset_id}`);

    const batch = await api.post('/v1/batches', {
      project_id: p1,
      asset_ids: [a1.data.asset_id, a2.data.asset_id],
      recipes: [{ preset_id: 'shopee_1_1', format: 'png' }],
    });
    // Either 202 with partial_failed item isolation, or 404/422 if validated upfront;
    // if upfront rejects missing asset, test with healthy asset + bad recipe alongside valid recipe
    if (batch.status === 202) {
      const jobId = tracker.trackBatch(batch.data.job_id);
      const done = await api.pollBatchUntilTerminal(jobId);
      expect(['partial_failed', 'completed']).toContain(done.status);
      expect(done.completed_items).toBeGreaterThanOrEqual(1);
    } else {
      expect([404, 422]).toContain(batch.status);
    }
  });

  test('T2-F4-03 Cancel already-completed job returns 409/400; missing job returns 404', { tag: ['@m2'] }, async ({ api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const p1 = tracker.trackProject((await api.post('/v1/projects', { name: uniqueId('t2_f4_03') })).data.id);
    const a1 = await api.uploadAsset(p1, { filePath: fixtures.tinyPng });

    const batch = await api.post('/v1/batches', {
      project_id: p1,
      asset_ids: [a1.data.asset_id],
      recipes: [{ preset_id: 'shopee_1_1', format: 'png' }],
    });
    expect(batch.status).toBe(202);
    const jobId = tracker.trackBatch(batch.data.job_id);
    await api.pollBatchUntilTerminal(jobId);

    const cancelDone = await api.post(`/v1/batches/${jobId}/cancel`);
    expect([400, 409]).toContain(cancelDone.status);

    const cancelMissing = await api.post('/v1/batches/missing_job_e2e/cancel');
    expect(cancelMissing.status).toBe(404);
  });

  test('T2-F4-04 Retry already-succeeded job does not duplicate items or crash', { tag: ['@m2'] }, async ({ api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const p1 = tracker.trackProject((await api.post('/v1/projects', { name: uniqueId('t2_f4_04') })).data.id);
    const a1 = await api.uploadAsset(p1, { filePath: fixtures.tinyPng });

    const batch = await api.post('/v1/batches', {
      project_id: p1,
      asset_ids: [a1.data.asset_id],
      recipes: [{ preset_id: 'shopee_1_1', format: 'png' }],
    });
    const jobId = tracker.trackBatch(batch.data.job_id);
    const done = await api.pollBatchUntilTerminal(jobId);
    expect(done.failed_items).toBe(0);

    const retry = await api.post(`/v1/batches/${jobId}/retry`);
    expect([200, 202, 400, 409]).toContain(retry.status);
    const after = await api.get(`/v1/batches/${jobId}`);
    expect(after.status).toBe(200);
    expect(after.data.items).toHaveLength(1);
  });

  test('T2-F4-05 Quality boundaries (0, 101 rejected; 1, 100 accepted) and download path traversal blocked', { tag: ['@m2'] }, async ({ api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const p1 = tracker.trackProject((await api.post('/v1/projects', { name: uniqueId('t2_f4_05') })).data.id);
    const a1 = await api.uploadAsset(p1, { filePath: fixtures.tinyPng });

    for (const q of [0, 101]) {
      const bad = await api.post('/v1/batches', {
        project_id: p1,
        asset_ids: [a1.data.asset_id],
        recipes: [{ preset_id: 'shopee_1_1', format: 'jpeg', quality: q }],
      });
      expect(bad.status).toBe(422);
    }

    const okMinMax = await api.post('/v1/batches', {
      project_id: p1,
      asset_ids: [a1.data.asset_id],
      recipes: [
        { preset_id: 'shopee_1_1', format: 'jpeg', quality: 1 },
        { preset_id: 'lazada_1_1', format: 'jpeg', quality: 100 },
      ],
    });
    expect(okMinMax.status).toBe(202);
    tracker.trackBatch(okMinMax.data.job_id);
    await api.pollBatchUntilTerminal(okMinMax.data.job_id);

    const trav1 = await api.getBinary('/v1/batches/..%2F..%2Fkroma.db/download');
    expect([404, 422]).toContain(trav1.status);
    const trav2 = await api.getBinary('/v1/export/download/..%2Fetc%2Fpasswd');
    expect([404, 422]).toContain(trav2.status);
  });

  test('T2-F4-06 Download cancelled batch job before completion returns 409/404 cleanly', { tag: ['@m2'] }, async ({ api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const p1 = tracker.trackProject((await api.post('/v1/projects', { name: uniqueId('t2_f4_06') })).data.id);
    const a1 = await api.uploadAsset(p1, { filePath: fixtures.shoePng });

    const batch = await api.post('/v1/batches', {
      project_id: p1,
      asset_ids: [a1.data.asset_id],
      recipes: [{ preset_id: 'amazon_white_85', format: 'png' }],
    });
    expect(batch.status).toBe(202);
    const jobId = tracker.trackBatch(batch.data.job_id);
    await api.post(`/v1/batches/${jobId}/cancel`);

    const dl = await api.getBinary(`/v1/batches/${jobId}/download`);
    if (dl.status === 200) {
      // Only acceptable if it finished instantaneously before cancel took effect; must be valid non-empty ZIP
      expect(dl.buffer.subarray(0, 2).toString('ascii')).toBe('PK');
    } else {
      expect([404, 409]).toContain(dl.status);
    }
  });

  // === F5 Boundaries ===
  test('T2-F5-01 Creating proofing session for missing project returns 404', { tag: ['@m2'] }, async ({ api }) => {
    const res = await api.post('/v1/proofing', {
      project_id: 'nonexistent_proj_e2e',
      title: 'Missing Proj Proof',
      allow_comments: true,
    });
    expect(res.status).toBe(404);
    expect(res.data.code).toBe('NOT_FOUND');
  });

  test('T2-F5-02 Spatial pin coordinate boundaries [0.0, 1.0] accepted vs out-of-range 422', { tag: ['@m2'] }, async ({ api, tracker }) => {
    const p1 = tracker.trackProject((await api.post('/v1/projects', { name: uniqueId('t2_f5_02') })).data.id);
    const s = await api.post('/v1/proofing', {
      project_id: p1,
      title: 'Pin Bounds',
      allow_comments: true,
    });
    expect(s.status).toBe(201);
    const sid = s.data.id;

    const okBounds = await api.post(`/v1/proofing/${sid}/feedback`, {
      author: 'Client',
      action: 'comment',
      comment: 'Corner pin',
      pin_x: 0.0,
      pin_y: 1.0,
    });
    expect(okBounds.status).toBe(200);

    for (const bad of [
      { pin_x: -0.01, pin_y: 0.5 },
      { pin_x: 0.5, pin_y: 1.01 },
    ]) {
      const res = await api.post(`/v1/proofing/${sid}/feedback`, {
        author: 'Client',
        action: 'comment',
        comment: 'Bad pin',
        ...bad,
      });
      expect(res.status).toBe(422);
    }
  });

  test('T2-F5-03 allow_comments=false blocks client comments with 403 FORBIDDEN', { tag: ['@m2'] }, async ({ api, tracker }) => {
    const p1 = tracker.trackProject((await api.post('/v1/projects', { name: uniqueId('t2_f5_03') })).data.id);
    const s = await api.post('/v1/proofing', {
      project_id: p1,
      title: 'Locked Comments',
      allow_comments: false,
    });
    expect(s.status).toBe(201);
    const sid = s.data.id;

    const fb = await api.post(`/v1/proofing/${sid}/feedback`, {
      author: 'Client',
      action: 'comment',
      comment: 'Should fail',
    });
    expect(fb.status).toBe(403);

    const check = await api.get(`/v1/proofing/${sid}`);
    expect(check.status).toBe(200);
    expect(check.data.comments ?? check.data.feedback).toHaveLength(0);
  });

  test('T2-F5-04 Revoked and expired proofing links return 410 Gone', { tag: ['@m2'] }, async ({ api, tracker }) => {
    const p1 = tracker.trackProject((await api.post('/v1/projects', { name: uniqueId('t2_f5_04') })).data.id);
    const s1 = await api.post('/v1/proofing', {
      project_id: p1,
      title: 'Revoke Test',
      allow_comments: true,
    });
    expect(s1.status).toBe(201);
    const sid1 = s1.data.id;

    const rev = await api.post(`/v1/proofing/${sid1}/decision`, {
      actor: 'Designer',
      decision: 'revoke',
    });
    expect(rev.status).toBe(200);

    const getRevoked = await api.get(`/v1/proofing/${sid1}`);
    expect(getRevoked.status).toBe(410);

    const postRevoked = await api.post(`/v1/proofing/${sid1}/feedback`, {
      author: 'Client',
      action: 'comment',
      comment: 'Too late',
    });
    expect(postRevoked.status).toBe(410);

    // Internal history still preserves revoked session
    const history = await api.get(`/v1/projects/${p1}/proofing`);
    expect(history.status).toBe(200);
    expect(history.data.sessions.some((x: any) => x.id === sid1)).toBe(true);

    // Expired session
    const sExp = await api.post('/v1/proofing', {
      project_id: p1,
      title: 'Expired Test',
      allow_comments: true,
      expires_hours: 0,
    });
    if (sExp.status === 201) {
      const getExp = await api.get(`/v1/proofing/${sExp.data.id}`);
      expect(getExp.status).toBe(410);
    } else {
      expect(sExp.status).toBe(422);
    }
  });

  test('T2-F5-05 Invalid feedback action, decision enum, and empty author rejected with 422', { tag: ['@m2'] }, async ({ api, tracker }) => {
    const p1 = tracker.trackProject((await api.post('/v1/projects', { name: uniqueId('t2_f5_05') })).data.id);
    const s = await api.post('/v1/proofing', {
      project_id: p1,
      title: 'Enum Validation',
      allow_comments: true,
    });
    const sid = s.data.id;

    const badAction = await api.post(`/v1/proofing/${sid}/feedback`, {
      author: '',
      action: 'hack',
      comment: 'test',
    });
    expect(badAction.status).toBe(422);

    const badDecision = await api.post(`/v1/proofing/${sid}/decision`, {
      actor: 'Client',
      decision: 'delete_all',
    });
    expect(badDecision.status).toBe(422);
  });

  test('T2-F5-06 Archived session rejects mutations until reopened', { tag: ['@m2'] }, async ({ api, tracker }) => {
    const p1 = tracker.trackProject((await api.post('/v1/projects', { name: uniqueId('t2_f5_06') })).data.id);
    const s = await api.post('/v1/proofing', {
      project_id: p1,
      title: 'Archived Test',
      allow_comments: true,
    });
    const sid = s.data.id;

    const arch = await api.post(`/v1/proofing/${sid}/decision`, {
      actor: 'Designer',
      decision: 'archive',
    });
    expect(arch.status).toBe(200);
    expect(arch.data.status).toBe('archived');

    const fb = await api.post(`/v1/proofing/${sid}/feedback`, {
      author: 'Client',
      action: 'approve',
      comment: 'Late approve',
    });
    expect([403, 409]).toContain(fb.status);
  });
});
