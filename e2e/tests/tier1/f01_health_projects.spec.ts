import { test, expect } from '../../fixtures/testTracker';
import { ensureAllFixtures } from '../../fixtures/imageFixtures';
import { uniqueId } from '../../helpers/apiClient';

test.describe('Tier 1 — F1: Health, Error Envelope & Project Lifecycle', () => {
  test('T1-F1-01 Root /health echoes valid x-correlation-id', { tag: ['@baseline'] }, async ({ api }) => {
    const corrId = 'e2e-corr-001';
    const res = await api.request('GET', '/health', { correlationId: corrId });
    expect(res.status).toBe(200);
    expect(res.headers.get('x-correlation-id')).toBe(corrId);
    expect(res.data).toMatchObject({
      status: 'healthy',
      service: 'kroma-api',
      version: '0.1.0',
      mode: 'local-first-sqlite',
    });
  });

  test('T1-F1-02 Versioned /v1/health and /api/v1/health verify DB readiness', { tag: ['@m1'] }, async ({ api }) => {
    const v1 = await api.get('/v1/health');
    expect(v1.status).toBe(200);
    expect(v1.data.status).toBe('healthy');
    expect(v1.data.db).toBe('ok');

    const legacy = await api.get('/api/v1/health');
    expect(legacy.status).toBe(200);
    expect(legacy.data.status).toBe('healthy');
    expect(legacy.data.db).toBe('ok');
  });

  test('T1-F1-03 Create project with NFC Vietnamese name and list in /v1/projects', { tag: ['@baseline'] }, async ({ api, tracker }) => {
    const nfcName = `E2E Áo dài Studio ${uniqueId('p')}`;
    const createRes = await api.post('/v1/projects', {
      name: nfcName,
      description: 'Shopee Q4 campaign',
    });
    expect(createRes.status).toBe(201);
    tracker.trackProject(createRes.data.id);

    expect(createRes.data.id).toBeTruthy();
    expect(createRes.data.name).toBe(nfcName);
    expect(createRes.data.active_variant).toBe('default');
    expect(createRes.data.created_at).toMatch(/^\d{4}-\d{2}-\d{2}T/);
    expect(createRes.data.updated_at).toMatch(/^\d{4}-\d{2}-\d{2}T/);

    const listRes = await api.get('/v1/projects');
    expect(listRes.status).toBe(200);
    const list: Array<{ id: string; name: string }> = listRes.data.projects ?? listRes.data.items;
    expect(Array.isArray(list)).toBe(true);
    expect(list.some((p) => p.id === createRes.data.id && p.name === nfcName)).toBe(true);
  });

  test('T1-F1-04 Fetch project detail by ID', { tag: ['@baseline'] }, async ({ api, tracker }) => {
    const name = uniqueId('t1_f1_04');
    const createRes = await api.post('/v1/projects', { name, description: 'Detail check' });
    expect(createRes.status).toBe(201);
    const projectId = tracker.trackProject(createRes.data.id);

    const detailRes = await api.get(`/v1/projects/${projectId}`);
    expect(detailRes.status).toBe(200);
    expect(detailRes.data.id).toBe(projectId);
    expect(detailRes.data.name).toBe(name);
    expect(detailRes.data.description).toBe('Detail check');
    expect(Array.isArray(detailRes.data.assets)).toBe(true);
    expect(detailRes.data.assets).toHaveLength(0);
  });

  test('T1-F1-05 Cascade delete project removes project and its assets', { tag: ['@m1'] }, async ({ api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const createRes = await api.post('/v1/projects', { name: uniqueId('t1_f1_05') });
    expect(createRes.status).toBe(201);
    const projectId = tracker.trackProject(createRes.data.id);

    const uploadRes = await api.uploadAsset(projectId, {
      filePath: fixtures.tinyPng,
      kind: 'original',
    });
    expect(uploadRes.status).toBe(201);
    const assetId = uploadRes.data.asset_id ?? uploadRes.data.id;

    const delRes = await api.delete(`/v1/projects/${projectId}`);
    expect(delRes.status).toBe(200);
    expect(delRes.data).toMatchObject({ deleted: true, project_id: projectId });

    const projAfter = await api.get(`/v1/projects/${projectId}`);
    expect(projAfter.status).toBe(404);
    expect(projAfter.data).toMatchObject({
      code: 'NOT_FOUND',
      retryable: false,
    });
    expect(typeof projAfter.data.correlation_id).toBe('string');

    const assetAfter = await api.getBinary(`/v1/assets/${assetId}/file`);
    expect(assetAfter.status).toBe(404);
  });
});
