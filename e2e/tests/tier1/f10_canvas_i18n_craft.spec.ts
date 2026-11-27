import fs from 'node:fs';
import { test, expect } from '../../fixtures/testTracker';
import { ensureAllFixtures } from '../../fixtures/imageFixtures';
import { attachErrorMonitor, pasteImageFile, studioSelectors } from '../../helpers/selectors';

test.describe('Tier 1 — F10: Studio Canvas Pipeline, Ergonomics, i18n, ARIA & Craft', () => {
  test('T1-F10-01 Canvas cutout, shadow, filter, badge & watermark mutate rendered canvas pixels', { tag: ['@baseline'] }, async ({ page }) => {
    const fixtures = ensureAllFixtures();
    const monitor = attachErrorMonitor(page);

    await page.goto('/');
    await studioSelectors.emptyFileInput(page).setInputFiles(fixtures.shoePng);
    const canvas = studioSelectors.canvas(page);
    await expect(canvas).toBeVisible();

    const initialDataUrl = await canvas.evaluate((el) => (el as HTMLCanvasElement).toDataURL());

    // 1. Run Cutout -> wait for Restore button + verify Batch Grid badge 'AI Cutout'
    const right = studioSelectors.rightSidebar(page);
    await right.getByRole('button', { name: 'Tách nền', exact: true }).click();
    await right.getByRole('button', { name: 'Tách nền tự động (RMBG-1.4)' }).click();
    await expect(right.getByRole('button', { name: 'Khôi phục ảnh gốc' })).toBeVisible({ timeout: 10_000 });

    await studioSelectors.topToolbar(page).getByRole('button', { name: /Lưới hàng loạt \(\d+\)/ }).click();
    await expect(page.locator('main')).toContainText('AI Cutout');
    await studioSelectors.topToolbar(page).getByRole('button', { name: 'Canvas Studio' }).click();

    // 2. Floor shadow
    await right.getByRole('button', { name: 'Đổ bóng', exact: true }).click();
    await right.getByRole('button', { name: /Bóng sàn hướng xiên/ }).click();

    // 3. Filter
    await right.getByRole('button', { name: 'Chỉnh màu', exact: true }).click();
    await right.getByRole('button', { name: 'Tươi tắn TMĐT' }).click();

    // 4. Badge + Watermark
    await right.getByRole('button', { name: 'Khung tem', exact: true }).click();
    await right.getByRole('button', { name: 'Flash Sale' }).click();
    await right.locator('input[type="checkbox"]').first().check();
    await right.getByPlaceholder('Nhập tên Shop hoặc số điện thoại').fill('KROMA');

    const afterDataUrl = await canvas.evaluate((el) => (el as HTMLCanvasElement).toDataURL());
    expect(afterDataUrl).not.toBe(initialDataUrl);
    monitor.assertClean();
  });

  test('T1-F10-02 Layers tab toggles, Before/After split, Safe Zone, 3x3 grid & Zoom controls', { tag: ['@baseline'] }, async ({ page }) => {
    const fixtures = ensureAllFixtures();
    const monitor = attachErrorMonitor(page);

    await page.goto('/');
    await studioSelectors.emptyFileInput(page).setInputFiles(fixtures.shoePng);
    await expect(studioSelectors.canvas(page)).toBeVisible();

    const toolbar = studioSelectors.topToolbar(page);
    await toolbar.getByRole('button', { name: 'Before/After' }).click();
    await toolbar.getByRole('button', { name: 'Safe Zone' }).click();
    await toolbar.getByRole('button', { name: 'Lưới bố cục 3×3' }).click();

    const dock = studioSelectors.bottomDock(page);
    await expect(dock).toContainText('100%');
    await dock.getByRole('button', { name: 'Phóng to' }).click();
    await expect(dock).toContainText('115%');
    await dock.getByRole('button', { name: 'Thu nhỏ' }).click();
    await expect(dock).toContainText('100%');
    await dock.getByRole('button', { name: 'Phóng to' }).click();
    await dock.getByRole('button', { name: 'Về 100%' }).click();
    await expect(dock).toContainText('100%');

    const right = studioSelectors.rightSidebar(page);
    await right.getByRole('button', { name: 'Layer', exact: true }).click();
    const hideShadow = right.locator('button[title="Hide shadow"]');
    await expect(hideShadow).toBeVisible();
    await hideShadow.click();
    await expect(right.locator('button[title="Show shadow"]')).toBeVisible();
    await right.getByRole('button', { name: 'Căn giữa' }).click();
    monitor.assertClean();
  });

  test('T1-F10-03 Synthetic clipboard paste (Ctrl+V) and keyboard Arrow nudge / Delete', { tag: ['@baseline'] }, async ({ page }) => {
    const fixtures = ensureAllFixtures();
    const pngBase64 = fs.readFileSync(fixtures.tinyPng).toString('base64');
    const monitor = attachErrorMonitor(page);

    await page.goto('/');
    await expect(studioSelectors.emptyState(page)).toBeVisible();

    await pasteImageFile(page, pngBase64, 'pasted.png');

    await expect(studioSelectors.canvas(page)).toBeVisible();
    await expect(studioSelectors.leftSidebar(page)).toContainText('Danh sách sản phẩm (1)');

    await page.keyboard.press('ArrowRight');
    await page.keyboard.press('Shift+ArrowDown');
    await expect(
      studioSelectors.topToolbar(page).getByRole('button', { name: 'Đặt lại vị trí căn giữa' }),
    ).toBeVisible();

    await page.keyboard.press('Delete');
    await expect(studioSelectors.emptyState(page)).toBeVisible();
    monitor.assertClean();
  });

  test('T1-F10-04 Complete VI / EN switching across Studio, Modals and /proof/[id]', { tag: ['@m3'] }, async ({ page, api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const proj = await api.post('/v1/projects', { name: 'T1-F10-04 i18n' });
    const projectId = tracker.trackProject(proj.data.id);
    const asset = await api.uploadAsset(projectId, { filePath: fixtures.shoePng });
    const session = await api.post('/v1/proofing', {
      project_id: projectId,
      asset_id: asset.data.asset_id,
      title: 'i18n Proof',
      allow_comments: true,
    });

    const monitor = attachErrorMonitor(page);
    await page.goto(`/?project=${projectId}`);

    await studioSelectors.langEnButton(page).click();
    await expect(studioSelectors.leftSidebar(page)).toContainText('Product queue');

    // Batch modal translates to EN
    await studioSelectors.exportButton(page).click();
    const batchDialog = page.getByRole('dialog');
    await expect(batchDialog).toContainText(/Batch Export/i);
    await expect(batchDialog).not.toContainText('Xuất ảnh hàng loạt');
    await page.keyboard.press('Escape');

    // Proofing modal translates to EN
    await studioSelectors.proofingShareButton(page).click();
    const proofDialog = page.getByRole('dialog');
    await expect(proofDialog).toContainText(/Proofing|Share/i);
    await expect(proofDialog).not.toContainText('Tạo link duyệt ảnh cho khách');
    await page.keyboard.press('Escape');

    // /proof/[id] respects EN toggle or ?lang=en
    await page.goto(`/proof/${session.data.id}?lang=en`);
    const enBtn = page.getByRole('button', { name: 'EN', exact: true });
    if (await enBtn.isVisible()) {
      await enBtn.click();
    }
    await expect(page.locator('body')).toContainText(/Approve|Request Changes/i);
    monitor.assertClean();
  });

  test('T1-F10-05 Modals expose role="dialog", aria-modal="true" and close on Escape', { tag: ['@m3'] }, async ({ page }) => {
    const fixtures = ensureAllFixtures();
    const monitor = attachErrorMonitor(page);

    await page.goto('/');
    await studioSelectors.emptyFileInput(page).setInputFiles(fixtures.shoePng);
    await expect(studioSelectors.canvas(page)).toBeVisible();

    await studioSelectors.exportButton(page).click();
    const exportDialog = page.getByRole('dialog');
    await expect(exportDialog).toHaveAttribute('aria-modal', 'true');
    await page.keyboard.press('Escape');
    await expect(exportDialog).toBeHidden();

    await studioSelectors.proofingShareButton(page).click();
    const proofDialog = page.getByRole('dialog');
    await expect(proofDialog).toHaveAttribute('aria-modal', 'true');
    await page.keyboard.press('Escape');
    await expect(proofDialog).toBeHidden();
    monitor.assertClean();
  });

  test('T1-F10-06 Light neutral /proof/[id] craft surface and clean non-emoji toasts', { tag: ['@m3'] }, async ({ page, api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const proj = await api.post('/v1/projects', { name: 'T1-F10-06 Craft' });
    const projectId = tracker.trackProject(proj.data.id);
    const asset = await api.uploadAsset(projectId, { filePath: fixtures.shoePng });
    const session = await api.post('/v1/proofing', {
      project_id: projectId,
      asset_id: asset.data.asset_id,
      title: 'Light Craft Proof',
    });

    const monitor = attachErrorMonitor(page);
    await page.goto(`/proof/${session.data.id}`);

    const bgLuminance = await page.evaluate(() => {
      const root = document.querySelector('body > div') ?? document.body;
      const bg = getComputedStyle(root).backgroundColor;
      const match = bg.match(/\d+/g);
      if (!match || match.length < 3) return 0;
      const [r, g, b] = match.slice(0, 3).map((n) => Number(n) / 255);
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    });
    expect(bgLuminance).toBeGreaterThan(0.7);

    // Check clipboard paste toast on / has no clipboard emoji
    await page.goto('/');
    const pngBase64 = fs.readFileSync(fixtures.tinyPng).toString('base64');
    await pasteImageFile(page, pngBase64, 'paste.png');

    await expect(studioSelectors.canvas(page)).toBeVisible();
    const bodyText = await page.locator('body').innerText();
    expect(bodyText).not.toContain('📋');
    monitor.assertClean();
  });
});
