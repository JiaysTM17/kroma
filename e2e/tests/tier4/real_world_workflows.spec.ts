import fs from 'node:fs';
import { test, expect } from '../../fixtures/testTracker';
import { ensureAllFixtures } from '../../fixtures/imageFixtures';
import { attachErrorMonitor, studioSelectors } from '../../helpers/selectors';
import { inspectZipBuffer, probeImagePixelsWithPillow } from '../../helpers/zipInspect';

test.describe('Tier 4 — Real-World Seller & Reviewer Workflows (7 End-to-End Scenarios)', () => {
  test('T4-01 Shopee Fashion Seller: Sneaker listing upload, cutout, shadow, watermark, reload & WebP ZIP (1440x900)', { tag: ['@m3'] }, async ({ page, tracker }) => {
    const fixtures = ensureAllFixtures();
    await page.setViewportSize({ width: 1440, height: 900 });
    const monitor = attachErrorMonitor(page);

    await page.goto('/');
    await expect(studioSelectors.emptyState(page)).toBeVisible();

    const uploadResPromise = page.waitForResponse(
      (r) => r.url().includes('/assets') && r.request().method() === 'POST' && r.status() === 201,
    );
    await studioSelectors.emptyFileInput(page).setInputFiles([fixtures.shoePng, fixtures.bagJpg]);
    const upJson = await (await uploadResPromise).json();
    tracker.trackProject(upJson.project_id);
    await expect(studioSelectors.leftSidebar(page)).toContainText('(2)');

    const right = studioSelectors.rightSidebar(page);
    await right.getByRole('button', { name: /Tách nền|Cutout/i }).click();
    await right.getByRole('button', { name: /Tách nền tự động|Auto background removal/i }).click();
    await expect(right.getByRole('button', { name: /Khôi phục ảnh gốc|Restore original photo/i })).toBeVisible({ timeout: 10_000 });

    await right.getByRole('button', { name: /Đổ bóng|Shadow/i }).click();
    await right.getByRole('button', { name: /Bóng chân tiếp xúc|Contact ambient shadow/i }).click();

    await right.getByRole('button', { name: /Chỉnh màu|Adjust/i }).click();
    await right.getByRole('button', { name: 'Auto-Enhance' }).click();

    await right.getByRole('button', { name: /Khung tem|Badges/i }).click();
    await right.getByRole('button', { name: 'Flash Sale' }).click();
    await right.locator('input[type="checkbox"]').first().check();
    await right.getByPlaceholder(/Nhập tên Shop|Enter brand name/i).fill('SNEAKER VN');
    await page.waitForTimeout(800);

    await page.reload();
    await expect(studioSelectors.leftSidebar(page)).toContainText('(2)');

    await studioSelectors.exportButton(page).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByRole('button', { name: 'WEBP', exact: true }).click();
    const batchPromise = page.waitForResponse((r) => r.url().includes('/v1/batches') && r.request().method() === 'POST' && r.status() === 202);
    await dialog.getByRole('button', { name: /Tạo lô xuất|Xuất|Submit|Start batch|Tải file ZIP/i }).click();
    tracker.trackBatch((await (await batchPromise).json()).job_id);

    const dlPromise = page.waitForEvent('download', { timeout: 30_000 });
    const dlBtn = dialog.getByRole('button', { name: /Tải.*ZIP|Download ZIP/i });
    if (await dlBtn.isVisible()) await dlBtn.click();
    const inspected = await inspectZipBuffer(fs.readFileSync((await (await dlPromise).path())!));
    expect(inspected.images.length).toBeGreaterThanOrEqual(2);
    expect(inspected.images[0].header).toMatchObject({ format: 'webp', width: 1024, height: 1024 });
    expect(inspected.manifestJson).not.toBeNull();
    monitor.assertClean();
  });

  test('T4-02 TikTok Shop Vertical Creator: EN UI, EXIF portrait, Safe Zone, custom preset & JPEG ZIP (1280x800)', { tag: ['@m3'] }, async ({ page, tracker }) => {
    const fixtures = ensureAllFixtures();
    await page.setViewportSize({ width: 1280, height: 800 });
    const monitor = attachErrorMonitor(page);

    await page.goto('/');
    await studioSelectors.langEnButton(page).click();

    const upPromise = page.waitForResponse((r) => r.url().includes('/assets') && r.request().method() === 'POST' && r.status() === 201);
    await studioSelectors.emptyFileInput(page).setInputFiles(fixtures.portraitExif6Jpg);
    tracker.trackProject((await (await upPromise).json()).project_id);

    await studioSelectors.rightSidebar(page).getByText(/TikTok Shop Vertical/i).click();
    await studioSelectors.topToolbar(page).getByRole('button', { name: /Safe Zone/i }).click();
    await studioSelectors.canvas(page).click();
    await page.keyboard.press('Shift+ArrowUp');
    await page.keyboard.press('Shift+ArrowUp');

    // Create custom preset 1080x1440
    await studioSelectors.rightSidebar(page).getByRole('button', { name: /New preset|Custom preset/i }).click();
    const pDialog = page.getByRole('dialog');
    await pDialog.getByLabel(/Preset name/i).first().fill('TikTok Live Promo');
    await pDialog.getByLabel(/Width/i).fill('1080');
    await pDialog.getByLabel(/Height/i).fill('1440');
    const cpPromise = page.waitForResponse((r) => r.url().includes('/v1/presets') && r.request().method() === 'POST' && r.status() === 201);
    await pDialog.getByRole('button', { name: /Save|Create/i }).click();
    tracker.trackCustomPreset((await (await cpPromise).json()).id);

    await studioSelectors.rightSidebar(page).getByText('TikTok Live Promo').click();
    await expect(studioSelectors.toolbarPresetInfo(page)).toContainText('1080×1440');

    await studioSelectors.exportButton(page).click();
    const bDialog = page.getByRole('dialog');
    await bDialog.getByRole('button', { name: 'JPEG', exact: true }).click();
    const batchPromise = page.waitForResponse((r) => r.url().includes('/v1/batches') && r.request().method() === 'POST' && r.status() === 202);
    await bDialog.getByRole('button', { name: /Submit|Start batch|Export|Download/i }).click();
    tracker.trackBatch((await (await batchPromise).json()).job_id);

    const dlPromise = page.waitForEvent('download', { timeout: 30_000 });
    const dlBtn = bDialog.getByRole('button', { name: /Download ZIP/i });
    if (await dlBtn.isVisible()) await dlBtn.click();
    const inspected = await inspectZipBuffer(fs.readFileSync((await (await dlPromise).path())!));
    expect(inspected.images[0].header).toMatchObject({ format: 'jpeg', width: 1080, height: 1440 });

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    expect(overflow).toBe(false);
    monitor.assertClean();
  });

  test('T4-03 Amazon Global Seller: Pure White 85% + Mobile Client Approval Loop (1440x900 + 375x812)', { tag: ['@m3'] }, async ({ browser, tracker }) => {
    const fixtures = ensureAllFixtures();
    const desktopCtx = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      permissions: ['clipboard-read', 'clipboard-write'],
    });
    const mobileCtx = await browser.newContext({
      viewport: { width: 375, height: 812 },
    });
    const desktop = await desktopCtx.newPage();
    const mobile = await mobileCtx.newPage();
    const mDesktop = attachErrorMonitor(desktop);
    const mMobile = attachErrorMonitor(mobile);

    try {
      await desktop.goto('/');
      const upPromise = desktop.waitForResponse((r) => r.url().includes('/assets') && r.request().method() === 'POST' && r.status() === 201);
      await studioSelectors.emptyFileInput(desktop).setInputFiles(fixtures.bottleWebp);
      const projectId = tracker.trackProject((await (await upPromise).json()).project_id);

      await studioSelectors.rightSidebar(desktop).getByText('Amazon White Hero (2000×2000)').click();
      await studioSelectors.rightSidebar(desktop).getByRole('button', { name: 'Áp dụng căn khung 85% Amazon' }).click();
      await studioSelectors.bottomDock(desktop).getByRole('button', { name: 'Nền trắng chuẩn sàn (Amazon/Shopee)' }).click();

      // Create proofing session
      await studioSelectors.proofingShareButton(desktop).click();
      const pDialog = desktop.getByRole('dialog');
      await pDialog.getByPlaceholder(/Shopee/i).fill('Amazon Main Hero');
      const proofPromise = desktop.waitForResponse((r) => r.url().includes('/v1/proofing') && r.request().method() === 'POST' && r.status() === 201);
      await pDialog.getByRole('button', { name: /Khởi tạo link proofing/i }).click();
      const proofUrl = await pDialog.locator('input[readonly]').inputValue();
      await desktop.keyboard.press('Escape');

      // Mobile client reviews & requests changes
      await mobile.goto(proofUrl);
      const mobileOverflow = await mobile.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
      expect(mobileOverflow).toBe(false);

      const mImg = mobile.locator('main img').first();
      await expect(mImg).toBeVisible();
      const box = await mImg.boundingBox();
      await mobile.mouse.click(box!.x + box!.width * 0.5, box!.y + box!.height * 0.5);
      await mobile.locator('aside input[type="text"], aside textarea').last().fill('Brighten shadow slightly');
      await mobile.locator('aside button[type="submit"]').click();
      await mobile.getByRole('button', { name: /Yêu cầu chỉnh sửa lại|Request Changes/i }).click();
      await expect(mobile.locator('header')).toContainText(/YÊU CẦU CHỈNH SỬA|REVISION/i);

      // Desktop designer adjusts & exports Amazon 2000x2000 pure white JPEG
      await studioSelectors.rightSidebar(desktop).getByRole('button', { name: /Chỉnh màu|Adjust/i }).click();
      const syncPromise = desktop.waitForResponse((r) => r.url().includes(`/v1/projects/${projectId}/state`) && r.request().method() === 'PUT');
      await studioSelectors.rightSidebar(desktop).getByRole('button', { name: 'Auto-Enhance' }).click();
      await syncPromise;

      await studioSelectors.exportButton(desktop).click();
      const bDialog = desktop.getByRole('dialog');
      await bDialog.getByRole('button', { name: 'JPEG', exact: true }).click();
      const batchPromise = desktop.waitForResponse((r) => r.url().includes('/v1/batches') && r.request().method() === 'POST' && r.status() === 202);
      await bDialog.getByRole('button', { name: /Tạo lô xuất|Xuất|Submit|Start batch|Tải file ZIP/i }).click();
      tracker.trackBatch((await (await batchPromise).json()).job_id);
      const dlPromise = desktop.waitForEvent('download', { timeout: 30_000 });
      const dlBtn = bDialog.getByRole('button', { name: /Tải.*ZIP|Download ZIP/i });
      if (await dlBtn.isVisible()) await dlBtn.click();
      const zip = await inspectZipBuffer(fs.readFileSync((await (await dlPromise).path())!));
      expect(zip.images[0].header).toMatchObject({ format: 'jpeg', width: 2000, height: 2000 });
      const pixelProbe = probeImagePixelsWithPillow(zip.images[0].bytes);
      expect(pixelProbe.topLeftRgb[0]).toBeGreaterThanOrEqual(252);
      expect(pixelProbe.topLeftRgb[1]).toBeGreaterThanOrEqual(252);
      expect(pixelProbe.topLeftRgb[2]).toBeGreaterThanOrEqual(252);

      // Mobile client reloads & approves
      await mobile.reload();
      await mobile.getByRole('button', { name: /Duyệt Ảnh Này|Approve/i }).click();
      await expect(mobile.locator('header')).toContainText(/ĐÃ DUYỆT|APPROVED/i);

      mDesktop.assertClean();
      mMobile.assertClean();
    } finally {
      await desktopCtx.close();
      await mobileCtx.close();
    }
  });

  test('T4-04 Multi-Channel Agency: 3 assets x 3 presets (9 outputs) batch ZIP + delete persistence (1440x900)', { tag: ['@m3'] }, async ({ page, tracker }) => {
    const fixtures = ensureAllFixtures();
    await page.setViewportSize({ width: 1440, height: 900 });
    const monitor = attachErrorMonitor(page);

    await page.goto('/');
    await studioSelectors.emptyFileInput(page).setInputFiles([
      fixtures.shoePng,
      fixtures.bagJpg,
      fixtures.bottleWebp,
    ]);
    await expect(studioSelectors.leftSidebar(page)).toContainText('(3)');

    // Inspect Batch Grid and return
    await studioSelectors.topToolbar(page).getByRole('button', { name: /Lưới hàng loạt \(3\)/ }).click();
    await expect(page.locator('main')).toContainText('shoe_solid_white_600x800.png');
    await page.locator('main').getByText('shoe_solid_white_600x800.png').click();
    await expect(studioSelectors.canvas(page)).toBeVisible();

    // Multi-preset batch export
    await studioSelectors.exportButton(page).click();
    const dialog = page.getByRole('dialog');
    for (const label of [/Shopee/i, /TikTok.*3:4|TikTok Shop Dọc/i, /Lazada/i]) {
      const cb = dialog.getByLabel(label);
      if ((await cb.count()) && !(await cb.first().isChecked())) {
        await cb.first().check();
      }
    }
    const batchPromise = page.waitForResponse((r) => r.url().includes('/v1/batches') && r.request().method() === 'POST' && r.status() === 202);
    await dialog.getByRole('button', { name: /Tạo lô xuất|Xuất|Submit|Start batch|Tải file ZIP/i }).click();
    const bJson = await (await batchPromise).json();
    tracker.trackProject(bJson.project_id);
    tracker.trackBatch(bJson.job_id);

    const dlPromise = page.waitForEvent('download', { timeout: 45_000 });
    const dlBtn = dialog.getByRole('button', { name: /Tải.*ZIP|Download ZIP/i });
    if (await dlBtn.isVisible()) await dlBtn.click();
    const inspected = await inspectZipBuffer(fs.readFileSync((await (await dlPromise).path())!));
    expect(inspected.images.length).toBeGreaterThanOrEqual(3);
    expect(inspected.manifestJson).not.toBeNull();
    await page.keyboard.press('Escape');

    // Delete 1 asset & reload
    const delPromise = page.waitForResponse((r) => r.url().includes('/v1/assets/') && r.request().method() === 'DELETE');
    await studioSelectors.leftSidebar(page).getByRole('button', { name: /Xóa ảnh: bag_studio_1200x1200\.jpg/i }).click();
    await delPromise;
    await page.reload();
    await expect(studioSelectors.leftSidebar(page)).toContainText('(2)');
    monitor.assertClean();
  });

  test('T4-05 Tablet Studio Ergonomics: Drawers, Ctrl+V paste, Adjust & Layer toggles (768x1024)', { tag: ['@m3'] }, async ({ page, tracker }) => {
    const fixtures = ensureAllFixtures();
    const pngBase64 = fs.readFileSync(fixtures.shoePng).toString('base64');
    await page.setViewportSize({ width: 768, height: 1024 });
    const monitor = attachErrorMonitor(page);

    await page.goto('/');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

    const upPromise = page.waitForResponse((r) => r.url().includes('/assets') && r.request().method() === 'POST' && r.status() === 201);
    await page.evaluate((b64) => {
      const bin = atob(b64);
      const bytes = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      const dt = new DataTransfer();
      dt.items.add(new File([bytes], 'tablet_paste.png', { type: 'image/png' }));
      window.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true }));
    }, pngBase64);
    tracker.trackProject((await (await upPromise).json()).project_id);

    await studioSelectors.mobileLeftDrawerToggle(page).click();
    await expect(studioSelectors.leftSidebar(page)).toContainText('(1)');
    await studioSelectors.leftSidebar(page).getByRole('button', { name: /Đóng bảng|Close panel/i }).click();

    await studioSelectors.mobileRightDrawerToggle(page).click();
    const right = studioSelectors.rightSidebar(page);
    await right.getByRole('button', { name: /Chỉnh màu|Adjust/i }).click();
    await right.getByRole('button', { name: 'Tươi tắn TMĐT' }).click();
    await right.getByRole('button', { name: 'Layer', exact: true }).click();
    await right.locator('button[title="Hide watermark"]').click();
    await right.getByRole('button', { name: /Đóng bảng|Close panel/i }).click();

    await studioSelectors.topToolbar(page).getByRole('button', { name: 'Before/After' }).click();
    await studioSelectors.topToolbar(page).getByRole('button', { name: /Lưới bố cục 3×3|3×3 composition grid/i }).click();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    monitor.assertClean();
  });

  test('T4-06 Mobile On-the-Go Seller & Reviewer: Compact header, drawer preset & /proof/[id] approval (375x812)', { tag: ['@m3'] }, async ({ page, tracker }) => {
    const fixtures = ensureAllFixtures();
    await page.setViewportSize({ width: 375, height: 812 });
    const monitor = attachErrorMonitor(page);

    await page.goto('/');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await expect(studioSelectors.exportButton(page)).toBeVisible();
    await expect(studioSelectors.proofingShareButton(page)).toBeVisible();

    const upPromise = page.waitForResponse((r) => r.url().includes('/assets') && r.request().method() === 'POST' && r.status() === 201);
    await studioSelectors.emptyFileInput(page).setInputFiles(fixtures.shoePng);
    tracker.trackProject((await (await upPromise).json()).project_id);

    await studioSelectors.mobileRightDrawerToggle(page).click();
    await studioSelectors.rightSidebar(page).getByText(/Shopee/i).first().click();
    await studioSelectors.rightSidebar(page).getByRole('button', { name: /Đóng bảng|Close panel/i }).click();

    await studioSelectors.proofingShareButton(page).click();
    const pDialog = page.getByRole('dialog');
    const proofPromise = page.waitForResponse((r) => r.url().includes('/v1/proofing') && r.request().method() === 'POST' && r.status() === 201);
    await pDialog.getByRole('button', { name: /Khởi tạo link proofing/i }).click();
    await proofPromise;
    const proofUrl = await pDialog.locator('input[readonly]').inputValue();

    await page.goto(proofUrl);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.getByRole('button', { name: /Duyệt Ảnh Này|Approve/i }).click();
    await expect(page.locator('header')).toContainText(/ĐÃ DUYỆT|APPROVED/i);
    monitor.assertClean();
  });

  test('T4-07 Baseline Smoke Regression Workflow: API + Studio Cutout/i18n/ZIP + Proofing (1440x900 & 375x812)', { tag: ['@baseline'] }, async ({ page, api, tracker }) => {
    const fixtures = ensureAllFixtures();

    // 1. Live Backend baseline API smoke
    expect((await api.get('/health')).status).toBe(200);
    expect((await api.get('/v1/presets')).status).toBe(200);
    const proj = await api.post('/v1/projects', { name: `T4-07 Smoke ${Date.now()}` });
    expect(proj.status).toBe(201);
    const projectId = tracker.trackProject(proj.data.id);
    const asset = await api.uploadAsset(projectId, { filePath: fixtures.shoePng });
    expect(asset.status).toBe(201);
    const state = await api.put(`/v1/projects/${projectId}/state`, {
      state: { preset_id: 'shopee_1_1', shadow: { enabled: true } },
    });
    expect(state.status).toBe(200);
    const proof = await api.post('/v1/proofing', {
      project_id: projectId,
      title: 'T4-07 Smoke Proof',
      client_name: 'QA',
      allow_comments: true,
    });
    expect(proof.status).toBe(201);

    // 2. Desktop Studio workflow (1440x900)
    await page.setViewportSize({ width: 1440, height: 900 });
    const monitor = attachErrorMonitor(page);
    await page.goto('/');
    await expect(studioSelectors.emptyState(page)).toBeVisible();

    await studioSelectors.emptyFileInput(page).setInputFiles(fixtures.shoePng);
    await expect(studioSelectors.canvas(page)).toBeVisible();

    const right = studioSelectors.rightSidebar(page);
    await right.getByRole('button', { name: 'Tách nền', exact: true }).click();
    await right.getByRole('button', { name: 'Tách nền tự động (RMBG-1.4)' }).click();
    await expect(right.getByRole('button', { name: 'Khôi phục ảnh gốc' })).toBeVisible({ timeout: 10_000 });

    // Toggle EN and back to VI
    await studioSelectors.langEnButton(page).click();
    await expect(studioSelectors.leftSidebar(page)).toContainText('Product queue (1)');
    await studioSelectors.langViButton(page).click();
    await expect(studioSelectors.leftSidebar(page)).toContainText('Danh sách sản phẩm (1)');

    // Client-side ZIP export
    await studioSelectors.exportButton(page).click();
    const dlPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Tải file ZIP (1 ảnh)' }).click();
    const download = await dlPromise;
    const inspected = await inspectZipBuffer(fs.readFileSync((await download.path())!));
    expect(inspected.images).toHaveLength(1);
    expect(inspected.images[0].header).toMatchObject({ format: 'webp', width: 1024, height: 1024 });

    // Proofing modal -> POST /v1/proofing -> visit /proof/[id] on mobile 375x812
    await studioSelectors.proofingShareButton(page).click();
    const proofCreateRes = page.waitForResponse(
      (r) => r.url().includes('/v1/proofing') && r.request().method() === 'POST' && r.status() === 201,
    );
    await page.getByRole('button', { name: 'Khởi tạo link proofing' }).click();
    await proofCreateRes;
    const createdUrl = await page.locator('input[readonly]').inputValue();

    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto(createdUrl);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.getByRole('button', { name: 'Duyệt Ảnh Này' }).click();
    await expect(page.locator('header')).toContainText('ĐÃ DUYỆT');
    monitor.assertClean();
  });
});
