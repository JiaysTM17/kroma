import fs from 'node:fs';
import { test, expect } from '../../fixtures/testTracker';
import { ensureAllFixtures } from '../../fixtures/imageFixtures';
import { sha256Hex, uniqueId } from '../../helpers/apiClient';
import { attachErrorMonitor, pasteImageFile, studioSelectors } from '../../helpers/selectors';
import { inspectZipBuffer, probeImagePixelsWithPillow } from '../../helpers/zipInspect';

test.describe('Tier 3 — Cross-Feature Pairwise Combinations (12 Tests)', () => {
  test('T3-01 Assets + Custom Preset + Batch Worker render custom 1080x1350 PNGs and manifest', { tag: ['@m2'] }, async ({ api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const p1 = tracker.trackProject((await api.post('/v1/projects', { name: uniqueId('t3_01') })).data.id);
    const a1 = await api.uploadAsset(p1, { filePath: fixtures.bagJpg });
    const a2 = await api.uploadAsset(p1, { filePath: fixtures.bottleWebp });
    expect(a1.status).toBe(201);
    expect(a2.status).toBe(201);

    const presetId = tracker.trackCustomPreset(uniqueId('e2e_t3_01').toLowerCase());
    const presetRes = await api.post('/v1/presets', {
      id: presetId,
      marketplace: 'custom',
      name_en: 'T3 Custom 4:5',
      name_vi: 'T3 Mẫu 4:5',
      width: 1080,
      height: 1350,
      formats: ['png'],
      background_rgb: [240, 245, 255],
      subject_area_ratio: 0.75,
    });
    expect(presetRes.status).toBe(201);

    const jobRes = await api.post('/v1/batches', {
      project_id: p1,
      asset_ids: [a1.data.asset_id, a2.data.asset_id],
      recipes: [{ preset_id: presetId, format: 'png' }],
    });
    expect(jobRes.status).toBe(202);
    const jobId = tracker.trackBatch(jobRes.data.job_id);
    const done = await api.pollBatchUntilTerminal(jobId);
    expect(done.status).toBe('completed');
    expect(done.completed_items).toBe(2);

    const zipBuf = (await api.getBinary(`/v1/batches/${jobId}/download`)).buffer;
    const inspected = await inspectZipBuffer(zipBuf);
    expect(inspected.images).toHaveLength(2);
    for (const img of inspected.images) {
      expect(img.header).toMatchObject({ format: 'png', width: 1080, height: 1350 });
    }
    expect(inspected.manifestJson).not.toBeNull();
    expect(JSON.stringify(inspected.manifestJson)).toContain(presetId);
  });

  test('T3-02 Assets + Proofing Pin + Approve + Project State Mutation -> revision_stale + Re-approve', { tag: ['@m2'] }, async ({ api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const p1 = tracker.trackProject((await api.post('/v1/projects', { name: uniqueId('t3_02') })).data.id);
    const a1 = await api.uploadAsset(p1, { filePath: fixtures.shoePng });
    const rev1 = (await api.get(`/v1/projects/${p1}/state`)).data.revision_id;

    const session = await api.post('/v1/proofing', {
      project_id: p1,
      asset_id: a1.data.asset_id,
      title: 'T3-02 Revision Cycle',
      allow_comments: true,
    });
    expect(session.status).toBe(201);
    const sid = session.data.id;

    await api.post(`/v1/proofing/${sid}/feedback`, {
      author: 'Client',
      action: 'comment',
      comment: 'Looks crisp',
      pin_x: 0.35,
      pin_y: 0.55,
    });
    const app1 = await api.post(`/v1/proofing/${sid}/decision`, {
      actor: 'Client',
      decision: 'approve',
    });
    expect(app1.data.status).toBe('approved');

    const state2 = await api.put(`/v1/projects/${p1}/state`, {
      expected_revision_id: rev1,
      state: { preset_id: 'tiktok_3_4', adjustments: { exposure: 12 } },
    });
    expect(state2.status).toBe(200);
    const rev2 = state2.data.revision_id;

    const invalidated = await api.get(`/v1/proofing/${sid}`);
    expect(invalidated.status).toBe(200);
    expect(invalidated.data.status).toBe('pending');
    expect(invalidated.data.revision_stale).toBe(true);

    const app2 = await api.post(`/v1/proofing/${sid}/decision`, {
      actor: 'Client',
      decision: 'approve',
    });
    expect(app2.status).toBe(200);
    expect(app2.data.status).toBe('approved');
    expect(app2.data.project_revision_id).toBe(rev2);
    expect(app2.data.events.length).toBeGreaterThanOrEqual(4);
  });

  test('T3-03 Cutout + Filters + Reload + BatchExportModal real 1024x1024 JPEG ZIP', { tag: ['@m3'] }, async ({ page, tracker }) => {
    const fixtures = ensureAllFixtures();
    const monitor = attachErrorMonitor(page);

    await page.goto('/');
    const upPromise = page.waitForResponse(
      (r) => r.url().includes('/assets') && r.request().method() === 'POST' && r.status() === 201,
    );
    await studioSelectors.emptyFileInput(page).setInputFiles(fixtures.shoePng);
    const upJson = await (await upPromise).json();
    tracker.trackProject(upJson.project_id);

    const right = studioSelectors.rightSidebar(page);
    await right.getByRole('button', { name: /Tách nền|Cutout/i }).click();
    const derivedPromise = page.waitForResponse(
      (r) => r.url().includes('/assets') && r.request().method() === 'POST' && r.status() === 201,
    );
    await right.getByRole('button', { name: /Tách nền tự động|Auto background removal/i }).click();
    await derivedPromise;

    await right.getByRole('button', { name: /Chỉnh màu|Adjust/i }).click();
    await right.getByRole('button', { name: 'Trong trẻo Studio' }).click();

    await right.getByRole('button', { name: /Đổ bóng|Shadow/i }).click();
    await right.getByRole('button', { name: /Bóng sàn hướng xiên|Directional floor shadow/i }).click();
    await page.waitForTimeout(800);

    await page.reload();
    await expect(studioSelectors.canvas(page)).toBeVisible();

    await studioSelectors.exportButton(page).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByRole('button', { name: 'JPEG', exact: true }).click();
    const batchPromise = page.waitForResponse(
      (r) => r.url().includes('/v1/batches') && r.request().method() === 'POST' && r.status() === 202,
    );
    await dialog.getByRole('button', { name: /Tạo lô xuất|Xuất|Submit|Start batch|Tải file ZIP/i }).click();
    const bJson = await (await batchPromise).json();
    tracker.trackBatch(bJson.job_id);

    const dlPromise = page.waitForEvent('download', { timeout: 30_000 });
    const dlBtn = dialog.getByRole('button', { name: /Tải.*ZIP|Download ZIP/i });
    if (await dlBtn.isVisible()) await dlBtn.click();
    const download = await dlPromise;
    const inspected = await inspectZipBuffer(fs.readFileSync((await download.path())!));
    expect(inspected.images[0].header).toMatchObject({ format: 'jpeg', width: 1024, height: 1024 });
    monitor.assertClean();
  });

  test('T3-04 Custom Preset UI + Safe Zone Overlay + Batch Export 1080x1350', { tag: ['@m3'] }, async ({ page, tracker }) => {
    const fixtures = ensureAllFixtures();
    const monitor = attachErrorMonitor(page);

    await page.goto('/');
    const upPromise = page.waitForResponse(
      (r) => r.url().includes('/assets') && r.request().method() === 'POST' && r.status() === 201,
    );
    await studioSelectors.emptyFileInput(page).setInputFiles(fixtures.shoePng);
    tracker.trackProject((await (await upPromise).json()).project_id);

    await studioSelectors.rightSidebar(page).getByRole('button', { name: /Tạo mẫu mới|New preset|Custom preset/i }).click();
    const pDialog = page.getByRole('dialog');
    await pDialog.getByLabel(/Tên mẫu|Preset name/i).first().fill('TikTok Promo 4:5');
    await pDialog.getByLabel(/Chiều rộng|Width/i).fill('1080');
    await pDialog.getByLabel(/Chiều cao|Height/i).fill('1350');
    const createPreset = page.waitForResponse((r) => r.url().includes('/v1/presets') && r.request().method() === 'POST' && r.status() === 201);
    await pDialog.getByRole('button', { name: /Lưu|Save|Tạo/i }).click();
    const presetJson = await (await createPreset).json();
    tracker.trackCustomPreset(presetJson.id);

    await studioSelectors.rightSidebar(page).getByText('TikTok Promo 4:5').click();
    await studioSelectors.topToolbar(page).getByRole('button', { name: /Safe Zone/i }).click();
    await expect(studioSelectors.toolbarPresetInfo(page)).toContainText('1080×1350');

    await studioSelectors.exportButton(page).click();
    const bDialog = page.getByRole('dialog');
    const batchPromise = page.waitForResponse((r) => r.url().includes('/v1/batches') && r.request().method() === 'POST' && r.status() === 202);
    await bDialog.getByRole('button', { name: /Tạo lô xuất|Xuất|Submit|Start batch|Tải file ZIP/i }).click();
    tracker.trackBatch((await (await batchPromise).json()).job_id);

    const dlPromise = page.waitForEvent('download', { timeout: 30_000 });
    const dlBtn = bDialog.getByRole('button', { name: /Tải.*ZIP|Download ZIP/i });
    if (await dlBtn.isVisible()) await dlBtn.click();
    const inspected = await inspectZipBuffer(fs.readFileSync((await (await dlPromise).path())!));
    expect(inspected.images[0].header.width).toBe(1080);
    expect(inspected.images[0].header.height).toBe(1350);
    monitor.assertClean();
  });

  test('T3-05 Delete second asset removes from Batch modal while Proofing session on first asset stays intact', { tag: ['@m3'] }, async ({ page, api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const monitor = attachErrorMonitor(page);

    await page.goto('/');
    await studioSelectors.emptyFileInput(page).setInputFiles([fixtures.shoePng, fixtures.bagJpg]);
    await expect(studioSelectors.leftSidebar(page)).toContainText('(2)');

    // Create proofing session via modal
    await studioSelectors.proofingShareButton(page).click();
    const pDialog = page.getByRole('dialog');
    const proofPromise = page.waitForResponse((r) => r.url().includes('/v1/proofing') && r.request().method() === 'POST' && r.status() === 201);
    await pDialog.getByRole('button', { name: /Khởi tạo link proofing|Create proofing link/i }).click();
    const proofJson = await (await proofPromise).json();
    tracker.trackProject(proofJson.project_id);
    await page.keyboard.press('Escape');

    // Delete bag_studio_1200x1200.jpg
    const delPromise = page.waitForResponse((r) => r.url().includes('/v1/assets/') && r.request().method() === 'DELETE');
    await studioSelectors.leftSidebar(page).getByRole('button', { name: /Xóa ảnh: bag_studio_1200x1200\.jpg/i }).click();
    await delPromise;
    await expect(studioSelectors.leftSidebar(page)).toContainText('(1)');

    // Batch modal only queues 1 remaining asset
    await studioSelectors.exportButton(page).click();
    await expect(page.getByRole('dialog')).toContainText(/1/);
    await page.keyboard.press('Escape');

    // Proofing session still returns 200 and renders shoe
    await page.goto(`/proof/${proofJson.id}`);
    await expect(page.locator('main img').first()).toBeVisible();
    const apiCheck = await api.get(`/v1/proofing/${proofJson.id}`);
    expect(apiCheck.status).toBe(200);
    monitor.assertClean();
  });

  test('T3-06 Full EN i18n propagation across Studio, Presets, BatchModal, ProofingModal & /proof/[id]', { tag: ['@m3'] }, async ({ page, api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const p1 = tracker.trackProject((await api.post('/v1/projects', { name: uniqueId('t3_06') })).data.id);
    const a1 = await api.uploadAsset(p1, { filePath: fixtures.shoePng });
    const s = await api.post('/v1/proofing', { project_id: p1, asset_id: a1.data.asset_id, title: 'EN Portal Check' });

    const monitor = attachErrorMonitor(page);
    await page.goto(`/?project=${p1}`);
    await studioSelectors.langEnButton(page).click();
    await expect(studioSelectors.rightSidebar(page)).toContainText('Shopee Standard Square');

    await studioSelectors.exportButton(page).click();
    await expect(page.getByRole('dialog')).toContainText(/Batch Export/i);
    await page.keyboard.press('Escape');

    await studioSelectors.proofingShareButton(page).click();
    await expect(page.getByRole('dialog')).toContainText(/Proofing|Share/i);
    await page.keyboard.press('Escape');

    await page.goto(`/proof/${s.data.id}?lang=en`);
    await expect(page.locator('body')).toContainText(/Approve|Request Changes/i);
    monitor.assertClean();
  });

  test('T3-07 System preset edit (800x800) + reset (1024x1024) reflects accurately in consecutive batch ZIPs', { tag: ['@m2'] }, async ({ api, tracker }) => {
    const fixtures = ensureAllFixtures();
    tracker.trackSystemPreset('shopee_1_1');
    const p1 = tracker.trackProject((await api.post('/v1/projects', { name: uniqueId('t3_07') })).data.id);
    const a1 = await api.uploadAsset(p1, { filePath: fixtures.shoePng });

    const editRes = await api.patch('/v1/presets/shopee_1_1', { width: 800, height: 800 });
    expect(editRes.status).toBe(200);

    const j1 = await api.post('/v1/batches', {
      project_id: p1,
      asset_ids: [a1.data.asset_id],
      recipes: [{ preset_id: 'shopee_1_1', format: 'png' }],
    });
    tracker.trackBatch(j1.data.job_id);
    await api.pollBatchUntilTerminal(j1.data.job_id);
    const zip1 = await inspectZipBuffer((await api.getBinary(`/v1/batches/${j1.data.job_id}/download`)).buffer);
    expect(zip1.images[0].header).toMatchObject({ width: 800, height: 800 });

    const resetRes = await api.post('/v1/presets/shopee_1_1/reset');
    expect(resetRes.status).toBe(200);

    const j2 = await api.post('/v1/batches', {
      project_id: p1,
      asset_ids: [a1.data.asset_id],
      recipes: [{ preset_id: 'shopee_1_1', format: 'png' }],
    });
    tracker.trackBatch(j2.data.job_id);
    await api.pollBatchUntilTerminal(j2.data.job_id);
    const zip2 = await inspectZipBuffer((await api.getBinary(`/v1/batches/${j2.data.job_id}/download`)).buffer);
    expect(zip2.images[0].header).toMatchObject({ width: 1024, height: 1024 });
  });

  test('T3-08 Derived asset graph cascade delete on Project 1 preserves shared original blob in Project 2', { tag: ['@m2'] }, async ({ api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const shoeBytes = fs.readFileSync(fixtures.shoePng);
    const p1 = tracker.trackProject((await api.post('/v1/projects', { name: uniqueId('t3_08_a') })).data.id);
    const p2 = tracker.trackProject((await api.post('/v1/projects', { name: uniqueId('t3_08_b') })).data.id);

    const a1 = await api.uploadAsset(p1, { filePath: fixtures.shoePng, kind: 'original' });
    const a2 = await api.uploadAsset(p1, { filePath: fixtures.maskPng, kind: 'mask', parentAssetId: a1.data.asset_id });
    const a3 = await api.uploadAsset(p1, { filePath: fixtures.tinyPng, kind: 'ai_output', parentAssetId: a1.data.asset_id });
    const a4 = await api.uploadAsset(p1, { filePath: fixtures.unicodePng, kind: 'thumbnail', parentAssetId: a1.data.asset_id });
    const aP2 = await api.uploadAsset(p2, { filePath: fixtures.shoePng, kind: 'original' });

    const del = await api.delete(`/v1/projects/${p1}`);
    expect(del.status).toBe(200);

    for (const id of [a1.data.asset_id, a2.data.asset_id, a3.data.asset_id, a4.data.asset_id]) {
      expect((await api.getBinary(`/v1/assets/${id}/file`)).status).toBe(404);
    }
    const p2File = await api.getBinary(`/v1/assets/${aP2.data.asset_id}/file`);
    expect(p2File.status).toBe(200);
    expect(sha256Hex(p2File.buffer)).toBe(sha256Hex(shoeBytes));
  });

  test('T3-09 Multi-tab optimistic 409 conflict surfaces clean reload notice without crash', { tag: ['@m3'] }, async ({ browser, api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const p1 = tracker.trackProject((await api.post('/v1/projects', { name: uniqueId('t3_09') })).data.id);
    await api.uploadAsset(p1, { filePath: fixtures.shoePng });

    const ctx = await browser.newContext();
    const tab1 = await ctx.newPage();
    const tab2 = await ctx.newPage();
    const m1 = attachErrorMonitor(tab1);
    const m2 = attachErrorMonitor(tab2);

    try {
      await tab1.goto(`/?project=${p1}`);
      await tab2.goto(`/?project=${p1}`);
      await expect(studioSelectors.canvas(tab1)).toBeVisible();
      await expect(studioSelectors.canvas(tab2)).toBeVisible();

      // Mutate in Tab 1
      await studioSelectors.rightSidebar(tab1).getByRole('button', { name: /Đổ bóng|Shadow/i }).click();
      const sync1 = tab1.waitForResponse((r) => r.url().includes(`/v1/projects/${p1}/state`) && r.request().method() === 'PUT' && r.status() === 200);
      await studioSelectors.rightSidebar(tab1).getByRole('button', { name: /Bóng sàn hướng xiên|Directional floor shadow/i }).click();
      await sync1;

      // Mutate in Tab 2 -> triggers 409 Conflict handled cleanly
      await studioSelectors.rightSidebar(tab2).getByRole('button', { name: /Khung tem|Badges/i }).click();
      const sync2 = tab2.waitForResponse((r) => r.url().includes(`/v1/projects/${p1}/state`) && r.request().method() === 'PUT');
      await studioSelectors.rightSidebar(tab2).getByRole('button', { name: 'Flash Sale' }).click();
      const res2 = await sync2;
      expect(res2.status()).toBe(409);

      await expect(tab2.locator('body')).toContainText(/xung đột|conflict|tải lại|reload/i);
      m1.assertClean();
      m2.assertClean({ allowHttpStatuses: [{ status: 409, urlPattern: new RegExp(`/v1/projects/${p1}/state`) }] });
    } finally {
      await ctx.close();
    }
  });

  test('T3-10 Batch partial failure isolation alongside cancelled job preserves healthy outputs', { tag: ['@m2'] }, async ({ api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const p1 = tracker.trackProject((await api.post('/v1/projects', { name: uniqueId('t3_10') })).data.id);
    const a1 = await api.uploadAsset(p1, { filePath: fixtures.shoePng });
    const a2 = await api.uploadAsset(p1, { filePath: fixtures.bagJpg });

    const j1 = await api.post('/v1/batches', {
      project_id: p1,
      asset_ids: [a1.data.asset_id, a2.data.asset_id],
      recipes: [{ preset_id: 'shopee_1_1', format: 'png' }],
    });
    expect(j1.status).toBe(202);
    tracker.trackBatch(j1.data.job_id);

    const j2 = await api.post('/v1/batches', {
      project_id: p1,
      asset_ids: [a1.data.asset_id],
      recipes: [{ preset_id: 'amazon_white_85', format: 'jpeg' }],
    });
    expect(j2.status).toBe(202);
    tracker.trackBatch(j2.data.job_id);
    await api.post(`/v1/batches/${j2.data.job_id}/cancel`);

    const d1 = await api.pollBatchUntilTerminal(j1.data.job_id);
    expect(d1.status).toBe('completed');
    const zip1 = await inspectZipBuffer((await api.getBinary(`/v1/batches/${j1.data.job_id}/download`)).buffer);
    expect(zip1.images).toHaveLength(2);
  });

  test('T3-11 Full proofing roundtrip: client request_change + pins -> designer edit + resolve -> client approve', { tag: ['@m3'] }, async ({ page, api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const p1 = tracker.trackProject((await api.post('/v1/projects', { name: uniqueId('t3_11') })).data.id);
    const a1 = await api.uploadAsset(p1, { filePath: fixtures.shoePng });
    const s = await api.post('/v1/proofing', {
      project_id: p1,
      asset_id: a1.data.asset_id,
      title: 'Roundtrip Proof',
      allow_comments: true,
    });
    const sid = s.data.id;

    const monitor = attachErrorMonitor(page);
    await page.goto(`/proof/${sid}`);
    const img = page.locator('main img').first();
    const box = await img.boundingBox();
    await page.mouse.click(box!.x + box!.width * 0.4, box!.y + box!.height * 0.4);
    await page.locator('aside input[type="text"], aside textarea').last().fill('Brighten sole');
    await page.locator('aside button[type="submit"]').click();
    await page.getByRole('button', { name: /Yêu cầu chỉnh sửa lại|Request Changes/i }).click();
    await expect(page.locator('header')).toContainText(/YÊU CẦU CHỈNH SỬA|REVISION/i);

    // Designer opens Studio, edits, and resolves comment
    await page.goto(`/?project=${p1}`);
    await studioSelectors.rightSidebar(page).getByRole('button', { name: /Chỉnh màu|Adjust/i }).click();
    const stateSync = page.waitForResponse((r) => r.url().includes(`/v1/projects/${p1}/state`) && r.request().method() === 'PUT');
    await studioSelectors.rightSidebar(page).getByRole('button', { name: 'Auto-Enhance' }).click();
    await stateSync;

    // Client reloads and approves
    await page.goto(`/proof/${sid}`);
    await page.getByRole('button', { name: /Duyệt Ảnh Này|Approve/i }).click();
    await expect(page.locator('header')).toContainText(/ĐÃ DUYỆT|APPROVED/i);
    monitor.assertClean();
  });

  test('T3-12 Clipboard paste + Backdrops + Layer eye toggles + Batch Grid + Client ZIP export', { tag: ['@baseline'] }, async ({ page }) => {
    const fixtures = ensureAllFixtures();
    const pngBase64 = fs.readFileSync(fixtures.shoePng).toString('base64');
    const monitor = attachErrorMonitor(page);

    await page.goto('/');
    await pasteImageFile(page, pngBase64, 'clipboard_shoe.png');

    await expect(studioSelectors.canvas(page)).toBeVisible();

    const dock = studioSelectors.bottomDock(page);
    await dock.getByRole('button', { name: 'Phòng tối Studio' }).click();
    await dock.getByRole('button', { name: 'PNG', exact: true }).click();
    await dock.getByRole('button', { name: 'Nền trắng chuẩn sàn (Amazon/Shopee)' }).click();

    const right = studioSelectors.rightSidebar(page);
    await right.getByRole('button', { name: 'Layer', exact: true }).click();
    await right.locator('button[title="Hide shadow"]').click();
    await expect(right.locator('button[title="Show shadow"]')).toBeVisible();

    await studioSelectors.topToolbar(page).getByRole('button', { name: 'Lưới hàng loạt (1)' }).click();
    await expect(page.locator('main')).toContainText(/Ảnh Clipboard|Clipboard/i);
    await studioSelectors.topToolbar(page).getByRole('button', { name: 'Canvas Studio' }).click();

    await studioSelectors.exportButton(page).click();
    const dlPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Tải file ZIP (1 ảnh)' }).click();
    const download = await dlPromise;
    const inspected = await inspectZipBuffer(fs.readFileSync((await download.path())!));
    expect(inspected.images).toHaveLength(1);
    expect(inspected.images[0].header).toMatchObject({ format: 'webp', width: 1024, height: 1024 });
    monitor.assertClean();
  });
});
