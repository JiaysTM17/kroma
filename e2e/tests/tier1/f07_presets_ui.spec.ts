import { test, expect } from '../../fixtures/testTracker';
import { ensureAllFixtures } from '../../fixtures/imageFixtures';
import { uniqueId } from '../../helpers/apiClient';
import { attachErrorMonitor, studioSelectors } from '../../helpers/selectors';

test.describe('Tier 1 — F7: Frontend Preset Customization UI & Safe-Zone Canvas', () => {
  test('T1-F7-01 Studio hydrates presets from live GET /v1/presets including custom presets', { tag: ['@m3'] }, async ({ page, api, tracker }) => {
    const customId = uniqueId('e2e_preset_ui').toLowerCase();
    tracker.trackCustomPreset(customId);
    const created = await api.post('/v1/presets', {
      id: customId,
      marketplace: 'custom',
      name_en: 'E2E Custom Hydrate',
      name_vi: 'E2E Mẫu Tùy Chỉnh',
      rule_description_en: 'Hydrated from SQLite',
      rule_description_vi: 'Tải từ SQLite',
      width: 1080,
      height: 1080,
      formats: ['png'],
    });
    expect(created.status).toBe(201);

    const monitor = attachErrorMonitor(page);
    const presetReq = page.waitForResponse(
      (r) => r.url().includes('/v1/presets') && r.request().method() === 'GET' && r.status() === 200,
    );
    await page.goto('/');
    await presetReq;

    await expect(studioSelectors.rightSidebar(page)).toContainText('E2E Mẫu Tùy Chỉnh');
    monitor.assertClean();
  });

  test('T1-F7-02 Switching marketplace presets updates toolbar info and Amazon 85% CTA', { tag: ['@baseline'] }, async ({ page }) => {
    const fixtures = ensureAllFixtures();
    const monitor = attachErrorMonitor(page);

    await page.goto('/');
    await studioSelectors.emptyFileInput(page).setInputFiles(fixtures.shoePng);
    await expect(studioSelectors.canvas(page)).toBeVisible();

    await studioSelectors.rightSidebar(page).getByText('TikTok Shop Dọc (1200×1600)').click();
    await expect(studioSelectors.toolbarPresetInfo(page)).toContainText('1200×1600');
    await expect(studioSelectors.toolbarPresetInfo(page)).toContainText('3:4');

    await studioSelectors.rightSidebar(page).getByText('Amazon White Hero (2000×2000)').click();
    await expect(studioSelectors.toolbarPresetInfo(page)).toContainText('2000×2000');
    await expect(studioSelectors.toolbarPresetInfo(page)).toContainText('1:1');
    await expect(
      studioSelectors.rightSidebar(page).getByRole('button', { name: 'Áp dụng căn khung 85% Amazon' }),
    ).toBeVisible();
    monitor.assertClean();
  });

  test('T1-F7-03 Create and apply custom preset via Preset Builder UI and persist across reload', { tag: ['@m3'] }, async ({ page, api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const monitor = attachErrorMonitor(page);

    await page.goto('/');
    await studioSelectors.emptyFileInput(page).setInputFiles(fixtures.shoePng);
    await expect(studioSelectors.canvas(page)).toBeVisible();

    const sidebar = studioSelectors.rightSidebar(page);
    await sidebar.getByRole('button', { name: /Tạo mẫu mới|New preset|Custom preset/i }).click();

    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await dialog.getByLabel(/Tên mẫu|Preset name/i).first().fill('Custom IG 4:5');
    await dialog.getByLabel(/Chiều rộng|Width/i).fill('1080');
    await dialog.getByLabel(/Chiều cao|Height/i).fill('1350');

    const createPromise = page.waitForResponse(
      (r) => r.url().includes('/v1/presets') && r.request().method() === 'POST' && r.status() === 201,
    );
    await dialog.getByRole('button', { name: /Lưu|Save|Tạo/i }).click();
    const createdJson = await (await createPromise).json();
    tracker.trackCustomPreset(createdJson.id);

    await sidebar.getByText('Custom IG 4:5').click();
    await expect(studioSelectors.toolbarPresetInfo(page)).toContainText('1080×1350');
    await expect(studioSelectors.toolbarPresetInfo(page)).toContainText('4:5');

    await page.reload();
    await expect(studioSelectors.rightSidebar(page)).toContainText('Custom IG 4:5');
    const fetched = await api.get(`/v1/presets/${createdJson.id}`);
    expect(fetched.status).toBe(200);
    monitor.assertClean();
  });

  test('T1-F7-04 Edit custom preset and reset system preset via UI', { tag: ['@m3'] }, async ({ page, api, tracker }) => {
    const customId = uniqueId('e2e_preset_edit').toLowerCase();
    tracker.trackCustomPreset(customId);
    tracker.trackSystemPreset('shopee_1_1');

    await api.post('/v1/presets', {
      id: customId,
      marketplace: 'custom',
      name_en: 'Editable Preset',
      name_vi: 'Mẫu có thể sửa',
      width: 1080,
      height: 1350,
      formats: ['png'],
    });

    const monitor = attachErrorMonitor(page);
    await page.goto('/');
    const sidebar = studioSelectors.rightSidebar(page);
    await expect(sidebar).toContainText('Mẫu có thể sửa');

    // Edit custom preset width -> 1200
    const customCard = sidebar.locator('[data-preset-id="' + customId + '"], div').filter({ hasText: 'Mẫu có thể sửa' }).first();
    await customCard.getByRole('button', { name: /Sửa|Edit/i }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel(/Chiều rộng|Width/i).fill('1200');
    const patchCustom = page.waitForResponse(
      (r) => r.url().includes(`/v1/presets/${customId}`) && (r.request().method() === 'PATCH' || r.request().method() === 'PUT') && r.status() === 200,
    );
    await dialog.getByRole('button', { name: /Lưu|Save/i }).click();
    await patchCustom;
    await expect(sidebar).toContainText('1200×1350');

    // Modify shopee_1_1 via API then reset from UI
    await api.patch('/v1/presets/shopee_1_1', { width: 900, height: 900 });
    await page.reload();
    const shopeeCard = studioSelectors.rightSidebar(page).locator('[data-preset-id="shopee_1_1"], div').filter({ hasText: 'Shopee' }).first();
    const resetPromise = page.waitForResponse(
      (r) => r.url().includes('/v1/presets/shopee_1_1/reset') && r.request().method() === 'POST' && r.status() === 200,
    );
    await shopeeCard.getByRole('button', { name: /Khôi phục|Reset/i }).click();
    await resetPromise;

    await expect(studioSelectors.rightSidebar(page)).toContainText('1024×1024');
    monitor.assertClean();
  });

  test('T1-F7-05 Normalized safe-zone overlay and Amazon 85% framing render cleanly', { tag: ['@m3'] }, async ({ page }) => {
    const fixtures = ensureAllFixtures();
    const monitor = attachErrorMonitor(page);

    await page.goto('/');
    await studioSelectors.emptyFileInput(page).setInputFiles(fixtures.shoePng);
    await expect(studioSelectors.canvas(page)).toBeVisible();

    await studioSelectors.rightSidebar(page).getByText(/TikTok Shop Dọc|TikTok Shop Vertical/i).click();
    const beforeSafeZone = await studioSelectors.canvas(page).evaluate((el) => (el as HTMLCanvasElement).toDataURL());
    await studioSelectors.topToolbar(page).getByRole('button', { name: /Safe Zone/i }).click();
    const afterSafeZone = await studioSelectors.canvas(page).evaluate((el) => (el as HTMLCanvasElement).toDataURL());
    expect(afterSafeZone).not.toBe(beforeSafeZone);

    await studioSelectors.rightSidebar(page).getByText(/Amazon White Hero/i).click();
    await studioSelectors.rightSidebar(page).getByRole('button', { name: /Áp dụng căn khung 85% Amazon|Apply Amazon 85% framing/i }).click();
    await expect(studioSelectors.toolbarPresetInfo(page)).toContainText('2000×2000');

    // Watermark and badge are disabled by Amazon framing
    await studioSelectors.rightSidebar(page).getByRole('button', { name: /Khung tem|Badges/i }).click();
    const wmToggle = studioSelectors.rightSidebar(page).locator('input[type="checkbox"]').first();
    await expect(wmToggle).not.toBeChecked();
    monitor.assertClean();
  });
});
