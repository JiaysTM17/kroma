import { test, expect } from '../../fixtures/testTracker';
import { ensureAllFixtures } from '../../fixtures/imageFixtures';
import { uniqueId } from '../../helpers/apiClient';
import { attachErrorMonitor, studioSelectors } from '../../helpers/selectors';

test.describe('Tier 1 — F9: Frontend Proofing & Approval Portal', () => {
  test('T1-F9-01 Create proofing session in ProofingModal, copy link, and list project sessions', { tag: ['@m3'] }, async ({ browser, api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const context = await browser.newContext({ permissions: ['clipboard-read', 'clipboard-write'] });
    const page = await context.newPage();
    const monitor = attachErrorMonitor(page);

    try {
      await page.goto('/');
      await studioSelectors.emptyFileInput(page).setInputFiles(fixtures.shoePng);
      await expect(studioSelectors.canvas(page)).toBeVisible();

      await studioSelectors.proofingShareButton(page).click();
      const dialog = page.getByRole('dialog');
      await expect(dialog).toBeVisible();

      await dialog.getByPlaceholder(/Brand/i).fill('Shop Hoa Hồng');
      await dialog.getByPlaceholder(/Shopee/i).fill('Bộ ảnh Tết');

      const createPromise = page.waitForResponse(
        (r) => r.url().includes('/v1/proofing') && r.request().method() === 'POST' && r.status() === 201,
      );
      await dialog.getByRole('button', { name: /Khởi tạo link proofing|Create proofing link/i }).click();
      const sessionJson = await (await createPromise).json();
      tracker.trackProject(sessionJson.project_id);

      await expect(dialog.locator('input[readonly]')).toHaveValue(new RegExp(`/proof/${sessionJson.id}`));
      await dialog.getByRole('button', { name: /Sao chép|Copy/i }).click();
      await expect(dialog).toContainText(/Đã chép|Copied/i);

      const listRes = await api.get(`/v1/projects/${sessionJson.project_id}/proofing`);
      expect(listRes.status).toBe(200);
      expect(listRes.data.sessions.some((s: any) => s.id === sessionJson.id)).toBe(true);
      monitor.assertClean();
    } finally {
      await context.close();
    }
  });

  test('T1-F9-02 /proof/[id] renders real project asset instead of placeholder SVG logo', { tag: ['@m3'] }, async ({ page, api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const proj = await api.post('/v1/projects', { name: uniqueId('t1_f9_02') });
    const projectId = tracker.trackProject(proj.data.id);
    const asset = await api.uploadAsset(projectId, { filePath: fixtures.shoePng });
    const session = await api.post('/v1/proofing', {
      project_id: projectId,
      asset_id: asset.data.asset_id,
      title: 'Real Asset Proof',
      client_name: 'Client X',
      allow_comments: true,
    });
    expect(session.status).toBe(201);

    const monitor = attachErrorMonitor(page);
    await page.goto(`/proof/${session.data.id}`);

    const img = page.locator('main img').first();
    await expect(img).toBeVisible();
    await expect.poll(async () => {
      return img.evaluate((el) => ({
        src: (el as HTMLImageElement).src,
        complete: (el as HTMLImageElement).complete,
        naturalWidth: (el as HTMLImageElement).naturalWidth,
      }));
    }).toMatchObject({ complete: true, naturalWidth: 600 });

    const src = await img.getAttribute('src');
    expect(src).not.toContain('kroma-logo-horizontal.svg');
    await expect(page.locator('body')).toContainText('Real Asset Proof');
    monitor.assertClean();
  });

  test('T1-F9-03 Click-to-pin spatial comment persists across page reload', { tag: ['@m3'] }, async ({ page, api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const proj = await api.post('/v1/projects', { name: uniqueId('t1_f9_03') });
    const projectId = tracker.trackProject(proj.data.id);
    const asset = await api.uploadAsset(projectId, { filePath: fixtures.shoePng });
    const session = await api.post('/v1/proofing', {
      project_id: projectId,
      asset_id: asset.data.asset_id,
      title: 'Spatial Pin Proof',
      allow_comments: true,
    });
    const sid = session.data.id;

    const monitor = attachErrorMonitor(page);
    await page.goto(`/proof/${sid}`);

    const img = page.locator('main img').first();
    await expect(img).toBeVisible();
    const box = await img.boundingBox();
    expect(box).not.toBeNull();
    await page.mouse.click(box!.x + box!.width * 0.5, box!.y + box!.height * 0.4);

    const commentInput = page.locator('aside input[type="text"], aside textarea').last();
    await commentInput.fill('Làm nét logo hơn');

    const fbPromise = page.waitForResponse(
      (r) => r.url().includes(`/v1/proofing/${sid}/`) && r.request().method() === 'POST' && r.status() === 200,
    );
    await page.locator('aside button[type="submit"]').click();
    const fbJson = await (await fbPromise).json();
    const items = fbJson.comments ?? fbJson.feedback;
    expect(items[0].pin_x).toBeGreaterThan(0.35);
    expect(items[0].pin_x).toBeLessThan(0.65);
    expect(items[0].pin_y).toBeGreaterThan(0.25);
    expect(items[0].pin_y).toBeLessThan(0.55);

    await page.reload();
    await expect(page.locator('aside')).toContainText('Làm nét logo hơn');
    monitor.assertClean();
  });

  test('T1-F9-04 Resolve comment in /proof/[id] persists across reload', { tag: ['@m3'] }, async ({ page, api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const proj = await api.post('/v1/projects', { name: uniqueId('t1_f9_04') });
    const projectId = tracker.trackProject(proj.data.id);
    const asset = await api.uploadAsset(projectId, { filePath: fixtures.shoePng });
    const session = await api.post('/v1/proofing', {
      project_id: projectId,
      asset_id: asset.data.asset_id,
      title: 'Resolve UI Proof',
      allow_comments: true,
    });
    const sid = session.data.id;
    await api.post(`/v1/proofing/${sid}/feedback`, {
      author: 'Client',
      action: 'comment',
      comment: 'Fix edge shadow',
      pin_x: 0.4,
      pin_y: 0.5,
    });

    const monitor = attachErrorMonitor(page);
    await page.goto(`/proof/${sid}`);
    await expect(page.locator('aside')).toContainText('Fix edge shadow');

    const resolvePromise = page.waitForResponse(
      (r) => r.url().includes(`/v1/proofing/${sid}/comments/`) && r.request().method() === 'PATCH' && r.status() === 200,
    );
    await page.locator('aside').getByRole('button', { name: /Resolve|Đã xử lý/i }).first().click();
    await resolvePromise;

    await page.reload();
    await expect(page.locator('aside')).toContainText(/Resolved|Đã xử lý/i);
    monitor.assertClean();
  });

  test('T1-F9-05 Approve decision syncs back to Studio and revision update marks session stale', { tag: ['@m3'] }, async ({ page, api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const proj = await api.post('/v1/projects', { name: uniqueId('t1_f9_05') });
    const projectId = tracker.trackProject(proj.data.id);
    const asset = await api.uploadAsset(projectId, { filePath: fixtures.shoePng });
    const session = await api.post('/v1/proofing', {
      project_id: projectId,
      asset_id: asset.data.asset_id,
      title: 'Decision Sync Proof',
      allow_comments: true,
    });
    const sid = session.data.id;

    const monitor = attachErrorMonitor(page);
    await page.goto(`/proof/${sid}`);

    const approvePromise = page.waitForResponse(
      (r) => r.url().includes(`/v1/proofing/${sid}/`) && r.request().method() === 'POST' && r.status() === 200,
    );
    await page.getByRole('button', { name: /Duyệt Ảnh Này|Approve/i }).click();
    await approvePromise;
    await expect(page.locator('header')).toContainText(/ĐÃ DUYỆT|APPROVED/i);

    // Return to Studio and inspect session list
    await page.goto(`/?project=${projectId}`);
    await studioSelectors.proofingShareButton(page).click();
    await expect(page.getByRole('dialog')).toContainText(/Decision Sync Proof/);
    await expect(page.getByRole('dialog')).toContainText(/approved|ĐÃ DUYỆT/i);

    // Mutate project state via API -> session becomes stale
    const state = await api.get(`/v1/projects/${projectId}/state`);
    await api.put(`/v1/projects/${projectId}/state`, {
      expected_revision_id: state.data.revision_id,
      state: { preset_id: 'tiktok_3_4' },
    });

    await page.goto(`/proof/${sid}`);
    await expect(page.locator('body')).toContainText(/cũ|stale|cập nhật|outdated/i);
    monitor.assertClean();
  });
});
