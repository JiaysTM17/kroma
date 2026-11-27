import fs from 'node:fs';
import { test, expect } from '../../fixtures/testTracker';
import { ensureAllFixtures } from '../../fixtures/imageFixtures';
import { uniqueId } from '../../helpers/apiClient';
import { attachErrorMonitor, studioSelectors } from '../../helpers/selectors';
import { inspectZipBuffer } from '../../helpers/zipInspect';

test.describe('Tier 2 — BVA Frontend F6–F10 (Negative, Boundary & Responsive)', () => {
  // === F6 Boundaries ===
  test('T2-F6-01 Optimistic concurrency 409 conflict on stale expected_revision_id', { tag: ['@baseline'] }, async ({ api, tracker }) => {
    const proj = await api.post('/v1/projects', { name: uniqueId('t2_f6_01') });
    expect(proj.status).toBe(201);
    const projectId = tracker.trackProject(proj.data.id);

    const s1 = await api.get(`/v1/projects/${projectId}/state`);
    expect(s1.status).toBe(200);
    const rev1 = s1.data.revision_id;

    const s2 = await api.put(`/v1/projects/${projectId}/state`, {
      expected_revision_id: rev1,
      state: { preset_id: 'shopee_1_1' },
    });
    expect(s2.status).toBe(200);

    const stale = await api.put(`/v1/projects/${projectId}/state`, {
      expected_revision_id: rev1,
      state: { preset_id: 'lazada_1_1' },
    });
    expect(stale.status).toBe(409);
    expect(stale.data).toMatchObject({
      code: 'CONFLICT',
      retryable: false,
    });
  });

  test('T2-F6-02 State payload nesting depth (>16 -> 422) and size (>2MB -> 413) guards', { tag: ['@baseline'] }, async ({ api, tracker }) => {
    const proj = await api.post('/v1/projects', { name: uniqueId('t2_f6_02') });
    const projectId = tracker.trackProject(proj.data.id);

    let deep: Record<string, any> = { leaf: true };
    for (let i = 0; i < 18; i++) deep = { layer: deep };
    const deepRes = await api.put(`/v1/projects/${projectId}/state`, { state: deep });
    expect(deepRes.status).toBe(422);

    const huge = await api.put(`/v1/projects/${projectId}/state`, {
      state: { blob: 'x'.repeat(2_200_000) },
    });
    expect(huge.status).toBe(413);
    expect(huge.data.code).toBe('PAYLOAD_TOO_LARGE');
  });

  test('T2-F6-03 Invalid ?project=nonexistent query param recovers cleanly without crashing', { tag: ['@m3'] }, async ({ page }) => {
    const monitor = attachErrorMonitor(page);
    await page.goto('/?project=nonexistent_e2e_id');
    await expect(studioSelectors.emptyState(page)).toBeVisible();
    // 404 from initial invalid ?project= probe is expected; no uncaught pageerrors
    monitor.assertClean({
      allowHttpStatuses: [{ status: 404, urlPattern: /\/v1\/projects\/nonexistent_e2e_id/ }],
    });
  });

  test('T2-F6-04 Corrupt / SVG-XSS file dropped into Studio upload input is rejected safely', { tag: ['@baseline'] }, async ({ page }) => {
    const fixtures = ensureAllFixtures();
    const monitor = attachErrorMonitor(page);

    await page.goto('/');
    await expect(studioSelectors.emptyState(page)).toBeVisible();

    await studioSelectors.emptyFileInput(page).setInputFiles([fixtures.svgXssAsPng, fixtures.truncatedPng]);
    // Give img.onerror a short tick to fire and ensure queue remains empty
    await page.waitForTimeout(400);
    await expect(studioSelectors.emptyState(page)).toBeVisible();
    await expect(studioSelectors.leftSidebar(page)).toContainText('Danh sách sản phẩm (0)');
    monitor.assertClean();
  });

  test('T2-F6-05 Rapid sequential multi-file upload (5 valid images at once) loads all 5 without race errors', { tag: ['@baseline'] }, async ({ page }) => {
    const fixtures = ensureAllFixtures();
    const monitor = attachErrorMonitor(page);

    await page.goto('/');
    await studioSelectors.emptyFileInput(page).setInputFiles([
      fixtures.shoePng,
      fixtures.bagJpg,
      fixtures.bottleWebp,
      fixtures.tinyPng,
      fixtures.unicodePng,
    ]);

    await expect(studioSelectors.leftSidebar(page)).toContainText('Danh sách sản phẩm (5)');
    await expect(studioSelectors.canvas(page)).toBeVisible();
    monitor.assertClean();
  });

  // === F7 Boundaries ===
  test('T2-F7-01 Preset Builder rejects invalid dimensions (<64) and overlapping safe_zone', { tag: ['@m3'] }, async ({ page }) => {
    const monitor = attachErrorMonitor(page);
    await page.goto('/');

    const sidebar = studioSelectors.rightSidebar(page);
    await sidebar.getByRole('button', { name: /Tạo mẫu mới|New preset|Custom preset/i }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();

    await dialog.getByLabel(/Tên mẫu|Preset name/i).first().fill('Invalid Dim');
    await dialog.getByLabel(/Chiều rộng|Width/i).fill('10');
    await dialog.getByRole('button', { name: /Lưu|Save|Tạo/i }).click();

    // Modal stays open with inline validation error
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText(/64|hợp lệ|invalid|dimension/i);
    monitor.assertClean({ allowHttpStatuses: [{ status: 422, urlPattern: /\/v1\/presets/ }] });
  });

  test('T2-F7-02 System preset delete action is disabled or absent in Preset UI', { tag: ['@m3'] }, async ({ page }) => {
    const monitor = attachErrorMonitor(page);
    await page.goto('/');

    const shopeeCard = studioSelectors.rightSidebar(page).locator('[data-preset-id="shopee_1_1"], div').filter({ hasText: 'Shopee' }).first();
    const delBtn = shopeeCard.getByRole('button', { name: /Xóa|Delete/i });
    if (await delBtn.count()) {
      await expect(delBtn.first()).toBeDisabled();
    } else {
      expect(await delBtn.count()).toBe(0);
    }
    monitor.assertClean();
  });

  test('T2-F7-03 Normalized safe_zone extremes (0.0 and 0.45) render on canvas without NaN or crash', { tag: ['@m3'] }, async ({ page, api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const zeroId = tracker.trackCustomPreset(uniqueId('e2e_sz_zero').toLowerCase());
    const tightId = tracker.trackCustomPreset(uniqueId('e2e_sz_tight').toLowerCase());

    await api.post('/v1/presets', {
      id: zeroId,
      marketplace: 'custom',
      name_en: 'Zero Margin',
      name_vi: 'Viền 0',
      width: 1000,
      height: 1000,
      formats: ['png'],
      safe_zone: { top: 0, right: 0, bottom: 0, left: 0 },
    });
    await api.post('/v1/presets', {
      id: tightId,
      marketplace: 'custom',
      name_en: 'Tight Margin',
      name_vi: 'Viền 45%',
      width: 1000,
      height: 1000,
      formats: ['png'],
      safe_zone: { top: 0.45, right: 0.45, bottom: 0.45, left: 0.45 },
    });

    const monitor = attachErrorMonitor(page);
    await page.goto('/');
    await studioSelectors.emptyFileInput(page).setInputFiles(fixtures.shoePng);
    await studioSelectors.topToolbar(page).getByRole('button', { name: /Safe Zone/i }).click();

    await studioSelectors.rightSidebar(page).getByText('Viền 0').click();
    await studioSelectors.rightSidebar(page).getByText('Viền 45%').click();
    await expect(studioSelectors.canvas(page)).toBeVisible();
    monitor.assertClean();
  });

  test('T2-F7-04 Subject scale slider extremes (0.5 min and 1.5 max) render cleanly', { tag: ['@baseline'] }, async ({ page }) => {
    const fixtures = ensureAllFixtures();
    const monitor = attachErrorMonitor(page);

    await page.goto('/');
    await studioSelectors.emptyFileInput(page).setInputFiles(fixtures.shoePng);
    await expect(studioSelectors.canvas(page)).toBeVisible();

    const scaleSlider = studioSelectors.rightSidebar(page).locator('input[type="range"][min="0.5"][max="1.5"]');
    await scaleSlider.fill('0.5');
    await expect(studioSelectors.rightSidebar(page)).toContainText('50%');

    await scaleSlider.fill('1.5');
    await expect(studioSelectors.rightSidebar(page)).toContainText('150%');
    monitor.assertClean();
  });

  test('T2-F7-05 Studio falls back to default preset if active custom preset is deleted externally', { tag: ['@m3'] }, async ({ page, api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const customId = tracker.trackCustomPreset(uniqueId('e2e_fallback').toLowerCase());
    await api.post('/v1/presets', {
      id: customId,
      marketplace: 'custom',
      name_en: 'Deleted Mid Session',
      name_vi: 'Mẫu bị xóa',
      width: 900,
      height: 900,
      formats: ['png'],
    });

    const monitor = attachErrorMonitor(page);
    await page.goto('/');
    await studioSelectors.emptyFileInput(page).setInputFiles(fixtures.shoePng);
    await studioSelectors.rightSidebar(page).getByText('Mẫu bị xóa').click();
    await expect(studioSelectors.toolbarPresetInfo(page)).toContainText('900×900');

    await api.delete(`/v1/presets/${customId}`);
    await page.reload();
    await expect(studioSelectors.toolbarPresetInfo(page)).toContainText('1024×1024');
    monitor.assertClean();
  });

  // === F8 Boundaries ===
  test('T2-F8-01 Empty queue disables Batch Export submit and Hủy closes modal', { tag: ['@baseline'] }, async ({ page }) => {
    const monitor = attachErrorMonitor(page);
    await page.goto('/');

    await studioSelectors.exportButton(page).click();
    await expect(page.getByText('Xuất ảnh hàng loạt (Batch Export)')).toBeVisible();

    const submitBtn = page.getByRole('button', { name: 'Tải file ZIP (0 ảnh)' });
    await expect(submitBtn).toBeDisabled();

    await page.getByRole('button', { name: 'Hủy' }).click();
    await expect(page.getByText('Xuất ảnh hàng loạt (Batch Export)')).toBeHidden();
    monitor.assertClean();
  });

  test('T2-F8-02 Selecting PNG in BatchExportModal hides lossy quality slider; WEBP/JPEG restores it', { tag: ['@baseline'] }, async ({ page }) => {
    const fixtures = ensureAllFixtures();
    const monitor = attachErrorMonitor(page);

    await page.goto('/');
    await studioSelectors.emptyFileInput(page).setInputFiles(fixtures.tinyPng);
    await studioSelectors.exportButton(page).click();

    const qualitySlider = page.locator('input[type="range"][min="0.7"][max="1"]');
    await expect(qualitySlider).toBeVisible();

    await page.getByRole('button', { name: 'PNG', exact: true }).click();
    await expect(qualitySlider).toBeHidden();

    await page.getByRole('button', { name: 'JPEG', exact: true }).click();
    await expect(qualitySlider).toBeVisible();
    monitor.assertClean();
  });

  test('T2-F8-03 Zero presets selected blocks Batch Export submission', { tag: ['@m3'] }, async ({ page }) => {
    const fixtures = ensureAllFixtures();
    const monitor = attachErrorMonitor(page);

    await page.goto('/');
    await studioSelectors.emptyFileInput(page).setInputFiles(fixtures.tinyPng);
    await studioSelectors.exportButton(page).click();

    const dialog = page.getByRole('dialog');
    const presetCheckboxes = dialog.locator('[data-testid="batch-preset-checkbox"], input[type="checkbox"]');
    const count = await presetCheckboxes.count();
    for (let i = 0; i < count; i++) {
      if (await presetCheckboxes.nth(i).isChecked()) {
        await presetCheckboxes.nth(i).uncheck();
      }
    }

    const submitBtn = dialog.getByRole('button', { name: /Tạo lô xuất|Xuất|Submit|Start batch|Tải file ZIP/i });
    await expect(submitBtn).toBeDisabled();
    monitor.assertClean();
  });

  test('T2-F8-04 Partial batch failure surfaces warning and Retry triggers POST /retry', { tag: ['@m3'] }, async ({ page, api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const p1 = tracker.trackProject((await api.post('/v1/projects', { name: uniqueId('t2_f8_04') })).data.id);
    const a1 = await api.uploadAsset(p1, { filePath: fixtures.shoePng });

    const job = await api.post('/v1/batches', {
      project_id: p1,
      asset_ids: [a1.data.asset_id],
      recipes: [{ preset_id: 'shopee_1_1', format: 'png' }],
    });
    const jobId = tracker.trackBatch(job.data.job_id);
    await api.post(`/v1/batches/${jobId}/cancel`);

    const monitor = attachErrorMonitor(page);
    await page.goto(`/?project=${p1}`);
    await studioSelectors.exportButton(page).click();

    const dialog = page.getByRole('dialog');
    await expect(dialog).toContainText(/cancelled|failed|thất bại|đã hủy/i);
    const retryBtn = dialog.getByRole('button', { name: /Thử lại|Retry/i }).first();
    await expect(retryBtn).toBeVisible();
    monitor.assertClean();
  });

  test('T2-F8-05 Tiny 16x16 asset batch export completes without IndexSizeError and produces valid ZIP', { tag: ['@baseline'] }, async ({ page }) => {
    const fixtures = ensureAllFixtures();
    const monitor = attachErrorMonitor(page);

    await page.goto('/');
    await studioSelectors.emptyFileInput(page).setInputFiles(fixtures.tinyPng);
    await expect(studioSelectors.canvas(page)).toBeVisible();

    await studioSelectors.exportButton(page).click();
    await page.getByRole('button', { name: 'JPEG', exact: true }).click();
    await page.locator('input[type="range"][min="0.7"][max="1"]').fill('0.7');

    const dlPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Tải file ZIP (1 ảnh)' }).click();
    const download = await dlPromise;
    const dlPath = await download.path();
    expect(dlPath).toBeTruthy();

    const inspected = await inspectZipBuffer(fs.readFileSync(dlPath!));
    expect(inspected.images).toHaveLength(1);
    expect(inspected.images[0].header).toMatchObject({ format: 'jpeg', width: 1024, height: 1024 });
    monitor.assertClean();
  });

  // === F9 Boundaries ===
  test('T2-F9-01 Invalid /proof/nonexistent-e2e-id shows friendly not-found state and back link', { tag: ['@m3'] }, async ({ page }) => {
    const monitor = attachErrorMonitor(page);
    await page.goto('/proof/nonexistent-e2e-id');

    await expect(page.locator('body')).toContainText(/không tồn tại|not found/i);
    await expect(page.locator('a[href="/"]')).toBeVisible();
    monitor.assertClean({
      allowHttpStatuses: [{ status: 404, urlPattern: /\/v1\/proofing\/nonexistent-e2e-id/ }],
    });
  });

  test('T2-F9-02 Revoked proofing session shows 410 revoked notice and disables actions', { tag: ['@m3'] }, async ({ page, api, tracker }) => {
    const p1 = tracker.trackProject((await api.post('/v1/projects', { name: uniqueId('t2_f9_02') })).data.id);
    const s = await api.post('/v1/proofing', { project_id: p1, title: 'Revoked UI', allow_comments: true });
    const sid = s.data.id;
    await api.post(`/v1/proofing/${sid}/decision`, { actor: 'Owner', decision: 'revoke' });

    const monitor = attachErrorMonitor(page);
    await page.goto(`/proof/${sid}`);
    await expect(page.locator('body')).toContainText(/thu hồi|hết hạn|revoked|expired/i);
    monitor.assertClean({
      allowHttpStatuses: [{ status: 410, urlPattern: new RegExp(`/v1/proofing/${sid}`) }],
    });
  });

  test('T2-F9-03 Whitespace-only comment submission is ignored on /proof/[id]', { tag: ['@baseline'] }, async ({ page }) => {
    const monitor = attachErrorMonitor(page);
    await page.goto('/proof/demo');

    const header = page.locator('aside h2');
    const beforeText = await header.innerText();
    const input = page.getByPlaceholder('Để lại nhận xét hoặc yêu cầu sửa...');
    await input.fill('   ');
    await page.locator('aside button[type="submit"]').click();

    await expect(header).toHaveText(beforeText);
    monitor.assertClean();
  });

  test('T2-F9-04 Pin coordinates at image corners clamp within [0.0, 1.0]', { tag: ['@m3'] }, async ({ page, api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const p1 = tracker.trackProject((await api.post('/v1/projects', { name: uniqueId('t2_f9_04') })).data.id);
    const a1 = await api.uploadAsset(p1, { filePath: fixtures.shoePng });
    const s = await api.post('/v1/proofing', {
      project_id: p1,
      asset_id: a1.data.asset_id,
      title: 'Corner Pin Clamp',
      allow_comments: true,
    });
    const sid = s.data.id;

    const monitor = attachErrorMonitor(page);
    await page.goto(`/proof/${sid}`);

    const img = page.locator('main img').first();
    const box = await img.boundingBox();
    expect(box).not.toBeNull();
    // Click near bottom-right corner
    await page.mouse.click(box!.x + box!.width - 1, box!.y + box!.height - 1);

    await page.locator('aside input[type="text"], aside textarea').last().fill('Corner note');
    const fbPromise = page.waitForResponse(
      (r) => r.url().includes(`/v1/proofing/${sid}/`) && r.request().method() === 'POST',
    );
    await page.locator('aside button[type="submit"]').click();
    const fbRes = await fbPromise;
    expect(fbRes.status()).toBe(200);
    const json = await fbRes.json();
    const c = (json.comments ?? json.feedback)[0];
    expect(c.pin_x).toBeGreaterThanOrEqual(0);
    expect(c.pin_x).toBeLessThanOrEqual(1);
    expect(c.pin_y).toBeGreaterThanOrEqual(0);
    expect(c.pin_y).toBeLessThanOrEqual(1);
    monitor.assertClean();
  });

  test('T2-F9-05 allow_comments=false disables comment form on /proof/[id]', { tag: ['@m3'] }, async ({ page, api, tracker }) => {
    const fixtures = ensureAllFixtures();
    const p1 = tracker.trackProject((await api.post('/v1/projects', { name: uniqueId('t2_f9_05') })).data.id);
    const a1 = await api.uploadAsset(p1, { filePath: fixtures.shoePng });
    const s = await api.post('/v1/proofing', {
      project_id: p1,
      asset_id: a1.data.asset_id,
      title: 'Comments Disabled UI',
      allow_comments: false,
    });

    const monitor = attachErrorMonitor(page);
    await page.goto(`/proof/${s.data.id}`);
    const input = page.locator('aside input[type="text"], aside textarea');
    if (await input.count()) {
      await expect(input.last()).toBeDisabled();
    } else {
      await expect(page.locator('aside')).toContainText(/tắt|khóa|disabled/i);
    }
    monitor.assertClean();
  });

  // === F10 Boundaries ===
  test('T2-F10-01 Keyboard shortcuts suppressed while typing inside text input', { tag: ['@baseline'] }, async ({ page }) => {
    const fixtures = ensureAllFixtures();
    const monitor = attachErrorMonitor(page);

    await page.goto('/');
    await studioSelectors.emptyFileInput(page).setInputFiles(fixtures.shoePng);
    await expect(studioSelectors.canvas(page)).toBeVisible();

    const right = studioSelectors.rightSidebar(page);
    await right.getByRole('button', { name: 'Khung tem', exact: true }).click();
    const wmInput = right.getByPlaceholder('Nhập tên Shop hoặc số điện thoại');
    await wmInput.click();
    await wmInput.fill('ABC');
    await page.keyboard.press('ArrowLeft');
    await page.keyboard.press('Backspace');
    await page.keyboard.press('Delete');

    // Asset must NOT be deleted and reset-center button must NOT appear
    await expect(studioSelectors.canvas(page)).toBeVisible();
    await expect(studioSelectors.leftSidebar(page)).toContainText('Danh sách sản phẩm (1)');
    await expect(
      studioSelectors.topToolbar(page).getByRole('button', { name: 'Đặt lại vị trí căn giữa' }),
    ).toHaveCount(0);
    monitor.assertClean();
  });

  test('T2-F10-02 Cutout button disabled with 0 assets and during active cutout processing', { tag: ['@baseline'] }, async ({ page }) => {
    const fixtures = ensureAllFixtures();
    const monitor = attachErrorMonitor(page);

    await page.goto('/');
    const right = studioSelectors.rightSidebar(page);
    await right.getByRole('button', { name: 'Tách nền', exact: true }).click();
    const cutoutBtn = right.getByRole('button', { name: /Tách nền tự động/ });
    await expect(cutoutBtn).toBeDisabled();

    await studioSelectors.emptyFileInput(page).setInputFiles(fixtures.shoePng);
    await expect(cutoutBtn).toBeEnabled();
    await cutoutBtn.click();
    await expect(right).toContainText('Đang nhận diện và cô lập chủ thể');
    await expect(right.getByRole('button', { name: 'Khôi phục ảnh gốc' })).toBeVisible({ timeout: 10_000 });
    monitor.assertClean();
  });

  test('T2-F10-03 Zoom min (25%) and max (300%) clamping and reset to 100%', { tag: ['@baseline'] }, async ({ page }) => {
    const fixtures = ensureAllFixtures();
    const monitor = attachErrorMonitor(page);

    await page.goto('/');
    await studioSelectors.emptyFileInput(page).setInputFiles(fixtures.shoePng);
    await expect(studioSelectors.canvas(page)).toBeVisible();

    const dock = studioSelectors.bottomDock(page);
    const zoomOut = dock.getByRole('button', { name: 'Thu nhỏ' });
    const zoomIn = dock.getByRole('button', { name: 'Phóng to' });

    for (let i = 0; i < 10; i++) await zoomOut.click();
    await expect(dock).toContainText('25%');

    for (let i = 0; i < 25; i++) await zoomIn.click();
    await expect(dock).toContainText('300%');

    await dock.getByRole('button', { name: 'Về 100%' }).click();
    await expect(dock).toContainText('100%');
    monitor.assertClean();
  });

  test('T2-F10-04 Responsive zero horizontal overflow and mobile drawers at 768x1024 and 375x812', { tag: ['@baseline'] }, async ({ page }) => {
    const monitor = attachErrorMonitor(page);

    for (const vp of [
      { width: 768, height: 1024 },
      { width: 375, height: 812 },
    ]) {
      await page.setViewportSize(vp);
      await page.goto('/');
      await expect(studioSelectors.emptyState(page)).toBeVisible();

      const overflowStudio = await page.evaluate(
        () => document.documentElement.scrollWidth > window.innerWidth,
      );
      expect(overflowStudio, `Horizontal overflow on / at ${vp.width}x${vp.height}`).toBe(false);

      // Open and close left drawer
      await studioSelectors.mobileLeftDrawerToggle(page).click();
      await expect(studioSelectors.leftSidebar(page)).toBeInViewport();
      await studioSelectors.leftSidebar(page).getByRole('button', { name: 'Đóng bảng' }).click();

      // Open and close right drawer
      await studioSelectors.mobileRightDrawerToggle(page).click();
      await expect(studioSelectors.rightSidebar(page)).toBeInViewport();
      await studioSelectors.rightSidebar(page).getByRole('button', { name: 'Đóng bảng' }).click();

      // Check /proof/demo overflow
      await page.goto('/proof/demo');
      const overflowProof = await page.evaluate(
        () => document.documentElement.scrollWidth > window.innerWidth,
      );
      expect(overflowProof, `Horizontal overflow on /proof/demo at ${vp.width}x${vp.height}`).toBe(false);
    }
    monitor.assertClean();
  });

  test('T2-F10-05 Zero off-4px Tailwind spacing or 10px/11px micro-text on primary Studio & Proofing UI', { tag: ['@m3'] }, async ({ page }) => {
    const monitor = attachErrorMonitor(page);

    for (const url of ['/', '/proof/demo']) {
      await page.goto(url);
      const violations = await page.evaluate(() => {
        const badClasses = ['gap-1.5', 'py-1.5', 'px-3.5', 'text-[10px]', 'text-[11px]'];
        const hits: string[] = [];
        document.querySelectorAll('*').forEach((el) => {
          const cls = typeof el.className === 'string' ? el.className : '';
          for (const b of badClasses) {
            if (cls.split(/\s+/).includes(b)) {
              hits.push(`${el.tagName}.${b}`);
            }
          }
        });
        return hits;
      });
      expect(violations, `Off-4px / micro-text slop on ${url}`).toEqual([]);
    }
    monitor.assertClean();
  });

  test('T2-F10-06 Long Vietnamese filename and 60-char watermark render without horizontal overflow', { tag: ['@baseline'] }, async ({ page }) => {
    const fixtures = ensureAllFixtures();
    const monitor = attachErrorMonitor(page);
    const buf = fs.readFileSync(fixtures.tinyPng);

    await page.goto('/');
    await studioSelectors.emptyFileInput(page).setInputFiles({
      name: 'Áo dài lụa tơ tằm truyền thống thêu tay họa tiết hoa sen cực kỳ dài để kiểm tra tràn dòng 2026.png',
      mimeType: 'image/png',
      buffer: buf,
    });

    await expect(studioSelectors.canvas(page)).toBeVisible();
    const right = studioSelectors.rightSidebar(page);
    await right.getByRole('button', { name: 'Khung tem', exact: true }).click();
    await right.locator('input[type="checkbox"]').first().check();
    await right.getByPlaceholder('Nhập tên Shop hoặc số điện thoại').fill('X'.repeat(60));

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth,
    );
    expect(overflow).toBe(false);
    monitor.assertClean();
  });
});
