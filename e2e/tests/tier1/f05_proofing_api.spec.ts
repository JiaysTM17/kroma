import { test, expect } from '../../fixtures/testTracker';
import { ensureAllFixtures } from '../../fixtures/imageFixtures';
import { uniqueId } from '../../helpers/apiClient';

test.describe('Tier 1 — F5: Proofing Comments & Approval Lifecycle API', () => {
  test('T1-F5-01 Create revision-bound proofing session and list by project', { tag: ['@m2'] }, async ({ api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const proj = await api.post('/v1/projects', { name: uniqueId('t1_f5_01') });
    expect(proj.status).toBe(201);
    const projectId = tracker.trackProject(proj.data.id);

    const asset = await api.uploadAsset(projectId, { filePath: fixtures.shoePng });
    expect(asset.status).toBe(201);
    const state = await api.get(`/v1/projects/${projectId}/state`);
    expect(state.status).toBe(200);

    const createRes = await api.post('/v1/proofing', {
      project_id: projectId,
      asset_id: asset.data.asset_id,
      title: 'Duyệt Shopee Hero',
      client_name: 'Brand A',
      allow_comments: true,
      expires_hours: 48,
    });
    expect(createRes.status).toBe(201);
    expect(createRes.data.project_id).toBe(projectId);
    expect(createRes.data.asset_id).toBe(asset.data.asset_id);
    expect(createRes.data.project_revision_id).toBe(state.data.revision_id);
    expect(createRes.data.revision_stale).toBe(false);
    expect(createRes.data.status).toBe('pending');
    expect(createRes.data.asset_url).toBeTruthy();

    const listRes = await api.get(`/v1/projects/${projectId}/proofing`);
    expect(listRes.status).toBe(200);
    expect(listRes.data.total).toBeGreaterThanOrEqual(1);
    expect(listRes.data.sessions.some((s: any) => s.id === createRes.data.id)).toBe(true);
  });

  test('T1-F5-02 Submit spatial pin comment via /v1/proofing/{id}/feedback', { tag: ['@baseline'] }, async ({ api, tracker }) => {
    const proj = await api.post('/v1/projects', { name: uniqueId('t1_f5_02') });
    expect(proj.status).toBe(201);
    const projectId = tracker.trackProject(proj.data.id);

    const session = await api.post('/v1/proofing', {
      project_id: projectId,
      title: 'Baseline Proof Pin',
      client_name: 'Client Lan',
      allow_comments: true,
    });
    expect(session.status).toBe(201);
    const sessionId = session.data.id;

    const fbRes = await api.post(`/v1/proofing/${sessionId}/feedback`, {
      author: 'Lan',
      action: 'comment',
      comment: 'Sáng hơn 5%',
      pin_x: 0.42,
      pin_y: 0.68,
    });
    expect(fbRes.status).toBe(200);
    const list = fbRes.data.comments ?? fbRes.data.feedback;
    expect(Array.isArray(list)).toBe(true);
    expect(list).toHaveLength(1);
    expect(list[0].author).toBe('Lan');
    expect(list[0].pin_x).toBeCloseTo(0.42, 4);
    expect(list[0].pin_y).toBeCloseTo(0.68, 4);
    expect(['pending', 'in_review']).toContain(fbRes.data.status);
  });

  test('T1-F5-03 Resolve and edit comment via PATCH /v1/proofing/{id}/comments/{cid}', { tag: ['@m2'] }, async ({ api, tracker }) => {
    const proj = await api.post('/v1/projects', { name: uniqueId('t1_f5_03') });
    expect(proj.status).toBe(201);
    const projectId = tracker.trackProject(proj.data.id);

    const session = await api.post('/v1/proofing', {
      project_id: projectId,
      title: 'Resolve Comment Test',
      client_name: 'Brand B',
      allow_comments: true,
    });
    expect(session.status).toBe(201);
    const sessionId = session.data.id;

    const fb = await api.post(`/v1/proofing/${sessionId}/comments`, {
      author: 'Client',
      action: 'comment',
      comment: 'Tăng sáng góc phải',
      pin_x: 0.8,
      pin_y: 0.2,
    });
    expect(fb.status).toBe(200);
    const commentId = (fb.data.comments ?? fb.data.feedback)[0].id;

    const patch = await api.patch(`/v1/proofing/${sessionId}/comments/${commentId}`, {
      resolved: true,
      resolved_by: 'Designer',
      body: 'Đã tăng sáng 5%',
    });
    expect(patch.status).toBe(200);
    expect(patch.data.resolved).toBe(true);
    expect(patch.data.resolved_by).toBe('Designer');
    expect(patch.data.resolved_at).toBeTruthy();
    expect(patch.data.body ?? patch.data.comment).toBe('Đã tăng sáng 5%');

    const getAfter = await api.get(`/v1/proofing/${sessionId}`);
    expect(getAfter.status).toBe(200);
    const c = (getAfter.data.comments ?? getAfter.data.feedback)[0];
    expect(c.resolved).toBe(true);
    expect(c.body ?? c.comment).toBe('Đã tăng sáng 5%');
  });

  test('T1-F5-04 Delete comment via DELETE /v1/proofing/{id}/comments/{cid}', { tag: ['@m2'] }, async ({ api, tracker }) => {
    const proj = await api.post('/v1/projects', { name: uniqueId('t1_f5_04') });
    expect(proj.status).toBe(201);
    const projectId = tracker.trackProject(proj.data.id);

    const session = await api.post('/v1/proofing', {
      project_id: projectId,
      title: 'Delete Comment Test',
      allow_comments: true,
    });
    expect(session.status).toBe(201);
    const sessionId = session.data.id;

    const fb = await api.post(`/v1/proofing/${sessionId}/feedback`, {
      author: 'Client',
      action: 'comment',
      comment: 'Temp comment',
    });
    expect(fb.status).toBe(200);
    const commentId = (fb.data.comments ?? fb.data.feedback)[0].id;

    const del = await api.delete(`/v1/proofing/${sessionId}/comments/${commentId}`);
    expect(del.status).toBe(200);
    expect(del.data.deleted).toBe(true);

    const after = await api.get(`/v1/proofing/${sessionId}`);
    expect(after.status).toBe(200);
    expect(after.data.comments ?? after.data.feedback).toHaveLength(0);
  });

  test('T1-F5-05 Full decision lifecycle transitions and audit trail', { tag: ['@m2'] }, async ({ api, tracker }) => {
    const proj = await api.post('/v1/projects', { name: uniqueId('t1_f5_05') });
    expect(proj.status).toBe(201);
    const projectId = tracker.trackProject(proj.data.id);

    const session = await api.post('/v1/proofing', {
      project_id: projectId,
      title: 'Decision Lifecycle',
      allow_comments: true,
    });
    expect(session.status).toBe(201);
    const sid = session.data.id;

    const r1 = await api.post(`/v1/proofing/${sid}/decision`, {
      actor: 'Client',
      decision: 'request_change',
      note: 'Need brighter shadow',
    });
    expect(r1.status).toBe(200);
    expect(r1.data.status).toBe('revision_requested');

    const r2 = await api.post(`/v1/proofing/${sid}/decision`, {
      actor: 'Designer',
      decision: 'reopen',
      note: 'Updated exposure',
    });
    expect(r2.status).toBe(200);
    expect(['pending', 'in_review']).toContain(r2.data.status);

    const r3 = await api.post(`/v1/proofing/${sid}/decision`, {
      actor: 'Client Lead',
      decision: 'approve',
      note: 'LGTM',
    });
    expect(r3.status).toBe(200);
    expect(r3.data.status).toBe('approved');
    expect(r3.data.approved_by).toBe('Client Lead');
    expect(r3.data.approved_at).toBeTruthy();

    const r4 = await api.post(`/v1/proofing/${sid}/decision`, {
      actor: 'Admin',
      decision: 'archive',
    });
    expect(r4.status).toBe(200);
    expect(r4.data.status).toBe('archived');
    expect(Array.isArray(r4.data.events)).toBe(true);
    expect(r4.data.events.length).toBeGreaterThanOrEqual(4);
  });

  test('T1-F5-06 Updating project state auto-invalidates approved proofing session on older revision', { tag: ['@m2'] }, async ({ api, tracker }) => {
    const proj = await api.post('/v1/projects', { name: uniqueId('t1_f5_06') });
    expect(proj.status).toBe(201);
    const projectId = tracker.trackProject(proj.data.id);

    const s1 = await api.get(`/v1/projects/${projectId}/state`);
    expect(s1.status).toBe(200);
    const rev1 = s1.data.revision_id;

    const session = await api.post('/v1/proofing', {
      project_id: projectId,
      title: 'Revision Stale Test',
      allow_comments: true,
    });
    expect(session.status).toBe(201);
    const sid = session.data.id;

    const approve = await api.post(`/v1/proofing/${sid}/decision`, {
      actor: 'Client',
      decision: 'approve',
    });
    expect(approve.status).toBe(200);
    expect(approve.data.status).toBe('approved');

    const s2 = await api.put(`/v1/projects/${projectId}/state`, {
      expected_revision_id: rev1,
      state: { preset_id: 'amazon_white_85', adjustments: { exposure: 10 } },
    });
    expect(s2.status).toBe(200);
    expect(s2.data.revision_id).not.toBe(rev1);

    const after = await api.get(`/v1/proofing/${sid}`);
    expect(after.status).toBe(200);
    expect(after.data.status).toBe('pending');
    expect(after.data.revision_stale).toBe(true);
    expect(after.data.approved_by).toBeNull();
    expect(Array.isArray(after.data.events)).toBe(true);
    expect(after.data.events.length).toBeGreaterThanOrEqual(2);
  });
});
