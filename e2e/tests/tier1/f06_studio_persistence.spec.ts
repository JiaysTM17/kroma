import { test, expect } from '../../fixtures/testTracker';
import { ensureAllFixtures } from '../../fixtures/imageFixtures';
import { attachErrorMonitor, studioSelectors } from '../../helpers/selectors';

async function captureBootstrappedProjectId(page: import('@playwright/test').Page): Promise<string | null> {
  return page.evaluate(() => {
    const urlId = new URL(window.location.href).searchParams.get('project');
    if (urlId) return urlId;
    for (let i = 0; i < window.localStorage.length; i++) {
      const k = window.localStorage.key(i) ?? '';
      if (k.toLowerCase().includes('project')) {
        const val = window.localStorage.getItem(k);
        if (val && val.length >= 8) return val;
      }
    }
    return null;
  });
}

test.describe('Tier 1 — F6: Frontend Studio Persistence & State Sync', () => {
  test('T1-F6-01 Studio auto-bootstraps active project and persists ID in URL or localStorage', { tag: ['@m3'] }, async ({ page, api, tracker }) => {
    const monitor = attachErrorMonitor(page);
    const createPromise = page.waitForResponse(
      (r) => r.url().includes('/v1/projects') && (r.request().method() === 'POST' || r.request().method() === 'GET'),
    );

    await page.goto('/');
    await createPromise;
    await expect(studioSelectors.emptyState(page)).toBeVisible();

    const projectId = await captureBootstrappedProjectId(page);
    expect(projectId).toBeTruthy();
    tracker.trackProject(projectId);

    const detail = await api.get(`/v1/projects/${projectId}`);
    expect(detail.status).toBe(200);
    monitor.assertClean();
  });

  test('T1-F6-02 Upload image persists to backend and survives full page reload', { tag: ['@m3'] }, async ({ page, api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const monitor = attachErrorMonitor(page);

    await page.goto('/');
    await expect(studioSelectors.emptyState(page)).toBeVisible();

    const uploadPromise = page.waitForResponse(
      (r) => r.url().includes('/assets') && r.request().method() === 'POST' && r.status() === 201,
    );
    await studioSelectors.emptyFileInput(page).setInputFiles(fixtures.shoePng);
    const uploadRes = await uploadPromise;
    const uploadData = await uploadRes.json();
    const projectId = tracker.trackProject(uploadData.project_id ?? (await captureBootstrappedProjectId(page)));

    await expect(studioSelectors.canvas(page)).toBeVisible();
    await expect(studioSelectors.leftSidebar(page)).toContainText('shoe_solid_white_600x800.png');

    await page.reload();
    await expect(studioSelectors.canvas(page)).toBeVisible();
    await expect(studioSelectors.leftSidebar(page)).toContainText('Danh sách sản phẩm (1)');
    await expect(studioSelectors.leftSidebar(page)).toContainText('shoe_solid_white_600x800.png');

    const assetsRes = await api.get(`/v1/projects/${projectId}/assets`);
    expect(assetsRes.status).toBe(200);
    expect(assetsRes.data.total).toBe(1);
    monitor.assertClean();
  });

  test('T1-F6-03 Derived cutout asset persists across page reload', { tag: ['@m3'] }, async ({ page, api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const monitor = attachErrorMonitor(page);

    await page.goto('/');
    const uploadPromise = page.waitForResponse(
      (r) => r.url().includes('/assets') && r.request().method() === 'POST' && r.status() === 201,
    );
    await studioSelectors.emptyFileInput(page).setInputFiles(fixtures.shoePng);
    const upJson = await (await uploadPromise).json();
    const projectId = tracker.trackProject(upJson.project_id ?? (await captureBootstrappedProjectId(page)));

    await studioSelectors.rightSidebar(page).getByRole('button', { name: /Tách nền|Cutout/i }).click();
    const derivedUploadPromise = page.waitForResponse(
      (r) => r.url().includes('/assets') && r.request().method() === 'POST' && r.status() === 201,
    );
    await studioSelectors.rightSidebar(page).getByRole('button', { name: /Tách nền tự động|Auto background removal/i }).click();
    await derivedUploadPromise;

    await expect(
      studioSelectors.rightSidebar(page).getByRole('button', { name: /Khôi phục ảnh gốc|Restore original photo/i }),
    ).toBeVisible();

    await page.reload();
    await expect(studioSelectors.canvas(page)).toBeVisible();
    await studioSelectors.rightSidebar(page).getByRole('button', { name: /Tách nền|Cutout/i }).click();
    await expect(
      studioSelectors.rightSidebar(page).getByRole('button', { name: /Khôi phục ảnh gốc|Restore original photo/i }),
    ).toBeVisible();

    const assetsRes = await api.get(`/v1/projects/${projectId}/assets`);
    expect(assetsRes.status).toBe(200);
    expect(assetsRes.data.assets.some((a: any) => a.kind === 'ai_output' || a.kind === 'mask')).toBe(true);
    monitor.assertClean();
  });

  test('T1-F6-04 Studio state (preset, shadow, adjustments, watermark, transform) syncs to backend and restores on reload', { tag: ['@m3'] }, async ({ page, api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const monitor = attachErrorMonitor(page);

    await page.goto('/');
    const uploadPromise = page.waitForResponse(
      (r) => r.url().includes('/assets') && r.request().method() === 'POST' && r.status() === 201,
    );
    await studioSelectors.emptyFileInput(page).setInputFiles(fixtures.shoePng);
    const upJson = await (await uploadPromise).json();
    const projectId = tracker.trackProject(upJson.project_id ?? (await captureBootstrappedProjectId(page)));

    // Preset -> TikTok Shop Dọc
    await studioSelectors.rightSidebar(page).getByText(/TikTok Shop Dọc|TikTok Shop Vertical/i).click();
    await expect(studioSelectors.toolbarPresetInfo(page)).toContainText('1200×1600');

    // Shadow -> Floor
    await studioSelectors.rightSidebar(page).getByRole('button', { name: /Đổ bóng|Shadow/i }).click();
    await studioSelectors.rightSidebar(page).getByRole('button', { name: /Bóng sàn hướng xiên|Directional floor shadow/i }).click();

    // Adjust -> Auto-Enhance
    await studioSelectors.rightSidebar(page).getByRole('button', { name: /Chỉnh màu|Adjust/i }).click();
    await studioSelectors.rightSidebar(page).getByRole('button', { name: 'Auto-Enhance' }).click();

    // Watermark -> "KROMA TEST"
    await studioSelectors.rightSidebar(page).getByRole('button', { name: /Khung tem|Badges/i }).click();
    const wmCheckbox = studioSelectors.rightSidebar(page).locator('input[type="checkbox"]').first();
    await wmCheckbox.check();
    const wmInput = studioSelectors.rightSidebar(page).locator('input[type="text"]').first();
    await wmInput.fill('KROMA TEST');
    await wmInput.blur();

    // Nudge canvas
    const stateSyncPromise = page.waitForResponse(
      (r) => r.url().includes(`/v1/projects/${projectId}/state`) && r.request().method() === 'PUT' && r.status() === 200,
    );
    await studioSelectors.canvas(page).click();
    await page.keyboard.press('ArrowRight');
    await page.keyboard.press('ArrowRight');
    await page.keyboard.press('ArrowRight');
    await stateSyncPromise;

    await page.reload();
    await expect(studioSelectors.toolbarPresetInfo(page)).toContainText('1200×1600');
    await studioSelectors.rightSidebar(page).getByRole('button', { name: /Khung tem|Badges/i }).click();
    await expect(studioSelectors.rightSidebar(page).locator('input[type="text"]').first()).toHaveValue('KROMA TEST');

    const stateRes = await api.get(`/v1/projects/${projectId}/state`);
    expect(stateRes.status).toBe(200);
    expect(JSON.stringify(stateRes.data.state)).toContain('KROMA TEST');
    monitor.assertClean();
  });

  test('T1-F6-05 Delete asset persists across page reload', { tag: ['@m3'] }, async ({ page, api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const monitor = attachErrorMonitor(page);

    await page.goto('/');
    await studioSelectors.emptyFileInput(page).setInputFiles([fixtures.shoePng, fixtures.bagJpg]);
    await expect(studioSelectors.leftSidebar(page)).toContainText('(2)');

    const projectId = tracker.trackProject(await captureBootstrappedProjectId(page));
    await expect.poll(async () => {
      const res = await api.get(`/v1/projects/${projectId}/assets`);
      return res.data?.total ?? 0;
    }).toBe(2);

    const delPromise = page.waitForResponse(
      (r) => r.url().includes('/v1/assets/') && r.request().method() === 'DELETE' && r.status() === 200,
    );
    await studioSelectors.leftSidebar(page)
      .getByRole('button', { name: /Xóa ảnh: shoe_solid_white_600x800\.png|Remove image: shoe_solid_white_600x800\.png/i })
      .click();
    await delPromise;

    await expect(studioSelectors.leftSidebar(page)).toContainText('(1)');
    await page.reload();
    await expect(studioSelectors.leftSidebar(page)).toContainText('(1)');
    await expect(studioSelectors.leftSidebar(page)).not.toContainText('shoe_solid_white_600x800.png');

    const assetsAfter = await api.get(`/v1/projects/${projectId}/assets`);
    expect(assetsAfter.status).toBe(200);
    expect(assetsAfter.data.total).toBe(1);
    monitor.assertClean();
  });
});
