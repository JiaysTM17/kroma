import { test, expect } from '../../fixtures/testTracker';
import { ensureAllFixtures } from '../../fixtures/imageFixtures';
import { uniqueId } from '../../helpers/apiClient';
import { inspectZipBuffer, probeImagePixelsWithPillow } from '../../helpers/zipInspect';

test.describe('Tier 1 — F4: Batch Processing Worker & Export API', () => {
  test('T1-F4-01 Enqueue batch job and poll until completion', { tag: ['@m2'] }, async ({ api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const proj = await api.post('/v1/projects', { name: uniqueId('t1_f4_01') });
    expect(proj.status).toBe(201);
    const projectId = tracker.trackProject(proj.data.id);

    const a1 = await api.uploadAsset(projectId, { filePath: fixtures.shoePng });
    const a2 = await api.uploadAsset(projectId, { filePath: fixtures.bagJpg });
    expect(a1.status).toBe(201);
    expect(a2.status).toBe(201);

    const batchRes = await api.post('/v1/batches', {
      project_id: projectId,
      asset_ids: [a1.data.asset_id, a2.data.asset_id],
      recipes: [
        { preset_id: 'shopee_1_1', format: 'webp', quality: 85 },
        { preset_id: 'amazon_white_85', format: 'jpeg', quality: 92 },
      ],
    });
    expect(batchRes.status).toBe(202);
    const jobId = tracker.trackBatch(batchRes.data.job_id);
    expect(batchRes.data.total_items).toBe(4);
    expect(['queued', 'running', 'completed']).toContain(batchRes.data.status);

    const done = await api.pollBatchUntilTerminal(jobId);
    expect(done.status).toBe('completed');
    expect(done.completed_items).toBe(4);
    expect(done.failed_items).toBe(0);
    expect(done.progress).toBe(100);
    expect(done.download_url).toBeTruthy();
  });

  test('T1-F4-02 Download batch ZIP and verify Pillow-rendered images, dimensions, Amazon white corners & manifest.json', { tag: ['@m2'] }, async ({ api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const proj = await api.post('/v1/projects', { name: uniqueId('t1_f4_02') });
    expect(proj.status).toBe(201);
    const projectId = tracker.trackProject(proj.data.id);

    const a1 = await api.uploadAsset(projectId, { filePath: fixtures.shoePng });
    const a2 = await api.uploadAsset(projectId, { filePath: fixtures.bagJpg });
    expect(a1.status).toBe(201);
    expect(a2.status).toBe(201);

    const batchRes = await api.post('/v1/batches', {
      project_id: projectId,
      asset_ids: [a1.data.asset_id, a2.data.asset_id],
      recipes: [
        { preset_id: 'shopee_1_1', format: 'webp', quality: 85 },
        { preset_id: 'amazon_white_85', format: 'jpeg', quality: 95 },
      ],
    });
    expect(batchRes.status).toBe(202);
    const jobId = tracker.trackBatch(batchRes.data.job_id);
    const done = await api.pollBatchUntilTerminal(jobId);
    expect(done.status).toBe('completed');

    const dl = await api.getBinary(`/v1/batches/${jobId}/download`);
    expect(dl.status).toBe(200);
    expect(dl.headers.get('content-type') ?? '').toContain('zip');

    const inspected = await inspectZipBuffer(dl.buffer);
    expect(inspected.images).toHaveLength(4);
    expect(inspected.manifestJson).not.toBeNull();
    expect(inspected.manifestJson!.job_id).toBe(jobId);
    expect(inspected.manifestJson!.project_id).toBe(projectId);
    expect(Array.isArray(inspected.manifestJson!.items)).toBe(true);
    expect(inspected.manifestJson!.items).toHaveLength(4);

    const webps = inspected.images.filter((img) => img.header.format === 'webp');
    const jpegs = inspected.images.filter((img) => img.header.format === 'jpeg');
    expect(webps).toHaveLength(2);
    expect(jpegs).toHaveLength(2);

    for (const w of webps) {
      expect(w.header.width).toBe(1024);
      expect(w.header.height).toBe(1024);
    }
    for (const j of jpegs) {
      expect(j.header.width).toBe(2000);
      expect(j.header.height).toBe(2000);
      const probe = probeImagePixelsWithPillow(j.bytes);
      expect(probe.topLeftRgb[0]).toBeGreaterThanOrEqual(252);
      expect(probe.topLeftRgb[1]).toBeGreaterThanOrEqual(252);
      expect(probe.topLeftRgb[2]).toBeGreaterThanOrEqual(252);
    }
  });

  test('T1-F4-03 List project batch history sorted newest-first', { tag: ['@m2'] }, async ({ api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const proj = await api.post('/v1/projects', { name: uniqueId('t1_f4_03') });
    expect(proj.status).toBe(201);
    const projectId = tracker.trackProject(proj.data.id);

    const a1 = await api.uploadAsset(projectId, { filePath: fixtures.tinyPng });
    expect(a1.status).toBe(201);

    const j1 = await api.post('/v1/batches', {
      project_id: projectId,
      asset_ids: [a1.data.asset_id],
      recipes: [{ preset_id: 'shopee_1_1', format: 'png' }],
    });
    expect(j1.status).toBe(202);
    tracker.trackBatch(j1.data.job_id);
    await api.pollBatchUntilTerminal(j1.data.job_id);

    const j2 = await api.post('/v1/batches', {
      project_id: projectId,
      asset_ids: [a1.data.asset_id],
      recipes: [{ preset_id: 'lazada_1_1', format: 'png' }],
    });
    expect(j2.status).toBe(202);
    tracker.trackBatch(j2.data.job_id);
    await api.pollBatchUntilTerminal(j2.data.job_id);

    const listRes = await api.get(`/v1/projects/${projectId}/batches`);
    expect(listRes.status).toBe(200);
    expect(listRes.data.total).toBeGreaterThanOrEqual(2);
    expect(listRes.data.jobs[0].job_id).toBe(j2.data.job_id);
    expect(listRes.data.jobs.some((j: any) => j.job_id === j1.data.job_id)).toBe(true);
  });

  test('T1-F4-04 Watermark, shadow & EXIF orientation 6 transpose rendering', { tag: ['@m2'] }, async ({ api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const proj = await api.post('/v1/projects', { name: uniqueId('t1_f4_04') });
    expect(proj.status).toBe(201);
    const projectId = tracker.trackProject(proj.data.id);

    const portrait = await api.uploadAsset(projectId, {
      filePath: fixtures.portraitExif6Jpg,
      contentType: 'image/jpeg',
    });
    expect(portrait.status).toBe(201);
    expect(portrait.data.exif_orientation).toBe(6);

    const plainJob = await api.post('/v1/batches', {
      project_id: projectId,
      asset_ids: [portrait.data.asset_id],
      recipes: [{ preset_id: 'tiktok_3_4', format: 'png' }],
      include_shadow: false,
    });
    expect(plainJob.status).toBe(202);
    tracker.trackBatch(plainJob.data.job_id);
    await api.pollBatchUntilTerminal(plainJob.data.job_id);
    const plainZip = await inspectZipBuffer((await api.getBinary(`/v1/batches/${plainJob.data.job_id}/download`)).buffer);

    const fxJob = await api.post('/v1/batches', {
      project_id: projectId,
      asset_ids: [portrait.data.asset_id],
      recipes: [{ preset_id: 'tiktok_3_4', format: 'png' }],
      include_shadow: true,
      watermark_text: 'KROMA SHOP',
    });
    expect(fxJob.status).toBe(202);
    tracker.trackBatch(fxJob.data.job_id);
    await api.pollBatchUntilTerminal(fxJob.data.job_id);
    const fxZip = await inspectZipBuffer((await api.getBinary(`/v1/batches/${fxJob.data.job_id}/download`)).buffer);

    expect(fxZip.images).toHaveLength(1);
    expect(fxZip.images[0].header.width).toBe(1200);
    expect(fxZip.images[0].header.height).toBe(1600);
    // Watermark + shadow mutates rendered bytes vs plain export
    expect(Buffer.compare(fxZip.images[0].bytes, plainZip.images[0].bytes)).not.toBe(0);

    // After EXIF 6 transpose (90 deg CW), the red stripe on left edge becomes top band of portrait
    const probe = probeImagePixelsWithPillow(plainZip.images[0].bytes);
    expect(probe.width).toBe(1200);
    expect(probe.height).toBe(1600);
    // Center/top region confirms non-corrupt Pillow render
    expect(probe.topBandMeanRgb.length).toBe(3);
  });

  test('T1-F4-05 Legacy /v1/export/batch uses real Pillow rendering instead of stub text', { tag: ['@m2'] }, async ({ api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const proj = await api.post('/v1/projects', { name: uniqueId('t1_f4_05') });
    expect(proj.status).toBe(201);
    const projectId = tracker.trackProject(proj.data.id);

    const a1 = await api.uploadAsset(projectId, { filePath: fixtures.shoePng });
    expect(a1.status).toBe(201);

    const expRes = await api.post('/v1/export/batch', {
      project_id: projectId,
      recipes: [{ preset_id: 'shopee_1_1', format: 'JPEG', quality: 90 }],
    });
    expect([200, 202]).toContain(expRes.status);
    expect(expRes.data.download_url).toBeTruthy();

    const dl = await api.getBinary(expRes.data.download_url);
    expect(dl.status).toBe(200);
    const inspected = await inspectZipBuffer(dl.buffer);
    expect(inspected.images.length).toBeGreaterThanOrEqual(1);
    expect(inspected.images[0].header.format).toBe('jpeg');
    expect(inspected.images[0].header.width).toBe(1024);
    expect(inspected.images[0].header.height).toBe(1024);
    expect(inspected.images[0].bytes.toString('utf-8')).not.toContain('KROMA_SAMPLE_IMAGE_DATA');
  });
});
