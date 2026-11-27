import fs from 'node:fs';
import { test, expect } from '../../fixtures/testTracker';
import { ensureAllFixtures } from '../../fixtures/imageFixtures';
import { attachErrorMonitor, studioSelectors } from '../../helpers/selectors';
import { inspectZipBuffer } from '../../helpers/zipInspect';

test.describe('Tier 1 — F8: Frontend Batch Worker Integration', () => {
  test('T1-F8-01 Multi-asset multi-preset batch submission and live polling', { tag: ['@m3'] }, async ({ page, tracker }) => {
    const fixtures = ensureAllFixtures();
    const monitor = attachErrorMonitor(page);

    await page.goto('/');
    await studioSelectors.emptyFileInput(page).setInputFiles([fixtures.shoePng, fixtures.bagJpg]);
    await expect(studioSelectors.leftSidebar(page)).toContainText('(2)');

    await studioSelectors.exportButton(page).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();

    await dialog.getByRole('button', { name: 'WEBP' }).click();
    const submitPromise = page.waitForResponse(
      (r) => r.url().includes('/v1/batches') && r.request().method() === 'POST' && r.status() === 202,
    );
    await dialog.getByRole('button', { name: /Tạo lô xuất|Xuất|Submit|Start batch|Tải file ZIP/i }).click();
    const batchRes = await submitPromise;
    const batchJson = await batchRes.json();
    tracker.trackProject(batchJson.project_id);
    tracker.trackBatch(batchJson.job_id);

    await expect(dialog).toContainText(/100%|Hoàn tất|completed/i, { timeout: 30_000 });
    monitor.assertClean();
  });

  test('T1-F8-02 Download real server-rendered ZIP from BatchExportModal and inspect contents', { tag: ['@m3'] }, async ({ page, tracker }) => {
    const fixtures = ensureAllFixtures();
    const monitor = attachErrorMonitor(page);

    await page.goto('/');
    await studioSelectors.emptyFileInput(page).setInputFiles([fixtures.shoePng, fixtures.bagJpg]);
    await expect(studioSelectors.leftSidebar(page)).toContainText('(2)');

    await studioSelectors.exportButton(page).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();

    const submitPromise = page.waitForResponse(
      (r) => r.url().includes('/v1/batches') && r.request().method() === 'POST' && r.status() === 202,
    );
    await dialog.getByRole('button', { name: /Tạo lô xuất|Xuất|Submit|Start batch|Tải file ZIP/i }).click();
    const batchJson = await (await submitPromise).json();
    tracker.trackProject(batchJson.project_id);
    tracker.trackBatch(batchJson.job_id);

    const downloadPromise = page.waitForEvent('download', { timeout: 30_000 });
    const dlBtn = dialog.getByRole('button', { name: /Tải.*ZIP|Download ZIP/i });
    if (await dlBtn.isVisible()) {
      await dlBtn.click();
    }
    const download = await downloadPromise;
    const dlPath = await download.path();
    expect(dlPath).toBeTruthy();

    const inspected = await inspectZipBuffer(fs.readFileSync(dlPath!));
    expect(inspected.images.length).toBeGreaterThanOrEqual(2);
    expect(inspected.manifestJson).not.toBeNull();
    monitor.assertClean();
  });

  test('T1-F8-03 BatchExportModal displays project job history and supports re-download', { tag: ['@m3'] }, async ({ page, api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const proj = await api.post('/v1/projects', { name: 'T1-F8-03 Batch History' });
    const projectId = tracker.trackProject(proj.data.id);
    const a1 = await api.uploadAsset(projectId, { filePath: fixtures.shoePng });
    const job = await api.post('/v1/batches', {
      project_id: projectId,
      asset_ids: [a1.data.asset_id],
      recipes: [{ preset_id: 'shopee_1_1', format: 'webp', quality: 85 }],
    });
    const jobId = tracker.trackBatch(job.data.job_id);
    await api.pollBatchUntilTerminal(jobId);

    const monitor = attachErrorMonitor(page);
    await page.goto(`/?project=${projectId}`);
    await expect(studioSelectors.leftSidebar(page)).toContainText('(1)');

    const historyPromise = page.waitForResponse(
      (r) => r.url().includes(`/v1/projects/${projectId}/batches`) && r.request().method() === 'GET' && r.status() === 200,
    );
    await studioSelectors.exportButton(page).click();
    await historyPromise;

    const dialog = page.getByRole('dialog');
    await expect(dialog).toContainText(/completed|Hoàn tất/i);
    const dlPromise = page.waitForEvent('download');
    await dialog.getByRole('button', { name: /Tải|Download/i }).first().click();
    const download = await dlPromise;
    expect(download.suggestedFilename()).toContain('.zip');
    monitor.assertClean();
  });

  test('T1-F8-04 Cancel in-progress batch job from BatchExportModal', { tag: ['@m3'] }, async ({ page, tracker }) => {
    const fixtures = ensureAllFixtures();
    const monitor = attachErrorMonitor(page);

    await page.goto('/');
    await studioSelectors.emptyFileInput(page).setInputFiles([fixtures.shoePng, fixtures.bagJpg, fixtures.bottleWebp]);
    await expect(studioSelectors.leftSidebar(page)).toContainText('(3)');

    await studioSelectors.exportButton(page).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByRole('button', { name: /Tạo lô xuất|Xuất|Submit|Start batch/i }).click();

    const cancelPromise = page.waitForResponse(
      (r) => r.url().includes('/cancel') && r.request().method() === 'POST',
    );
    await dialog.getByRole('button', { name: /Hủy tiến trình|Cancel job|Hủy/i }).click();
    const cancelRes = await cancelPromise;
    expect([200, 409]).toContain(cancelRes.status());
    monitor.assertClean({ allowHttpStatuses: [{ status: 409, urlPattern: /\/cancel/ }] });
  });

  test('T1-F8-05 Retry failed batch job from BatchExportModal history', { tag: ['@m3'] }, async ({ page, api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const proj = await api.post('/v1/projects', { name: 'T1-F8-05 Retry Modal' });
    const projectId = tracker.trackProject(proj.data.id);
    const a1 = await api.uploadAsset(projectId, { filePath: fixtures.shoePng });

    const job = await api.post('/v1/batches', {
      project_id: projectId,
      asset_ids: [a1.data.asset_id],
      recipes: [{ preset_id: 'shopee_1_1', format: 'png' }],
    });
    const jobId = tracker.trackBatch(job.data.job_id);
    // Cancel immediately or simulate failed item if needed
    await api.post(`/v1/batches/${jobId}/cancel`);

    const monitor = attachErrorMonitor(page);
    await page.goto(`/?project=${projectId}`);
    await studioSelectors.exportButton(page).click();
    const dialog = page.getByRole('dialog');

    const retryBtn = dialog.getByRole('button', { name: /Thử lại|Retry/i }).first();
    await expect(retryBtn).toBeVisible();
    const retryPromise = page.waitForResponse(
      (r) => r.url().includes(`/v1/batches/${jobId}/retry`) && r.request().method() === 'POST',
    );
    await retryBtn.click();
    const retryRes = await retryPromise;
    expect(retryRes.status()).toBe(202);
    monitor.assertClean();
  });
});
