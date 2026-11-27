import { Locator, Page, Response } from '@playwright/test';

export interface ErrorMonitor {
  consoleErrors: string[];
  pageErrors: string[];
  failedRequests: string[];
  httpErrors: Array<{ status: number; url: string; method: string }>;
  assertClean: (opts?: { allowHttpStatuses?: Array<{ status: number; urlPattern?: RegExp }> }) => void;
}

export function attachErrorMonitor(page: Page): ErrorMonitor {
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  const failedRequests: string[] = [];
  const httpErrors: Array<{ status: number; url: string; method: string }> = [];

  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
    }
  });
  page.on('pageerror', (err) => {
    pageErrors.push(String(err));
  });
  page.on('requestfailed', (req) => {
    // Ignore aborted requests caused by immediate navigation/reload
    const failure = req.failure()?.errorText ?? 'unknown';
    if (!failure.includes('ERR_ABORTED')) {
      failedRequests.push(`${req.method()} ${req.url()} -> ${failure}`);
    }
  });
  page.on('response', (res: Response) => {
    if (res.status() >= 400) {
      httpErrors.push({
        status: res.status(),
        url: res.url(),
        method: res.request().method(),
      });
    }
  });

  return {
    consoleErrors,
    pageErrors,
    failedRequests,
    httpErrors,
    assertClean(opts) {
      const allow = opts?.allowHttpStatuses ?? [];
      const unexpectedHttp = httpErrors.filter(
        (e) =>
          !allow.some(
            (rule) =>
              rule.status === e.status && (!rule.urlPattern || rule.urlPattern.test(e.url)),
          ),
      );
      if (consoleErrors.length > 0) {
        throw new Error(`Console errors detected:\n${consoleErrors.join('\n')}`);
      }
      if (pageErrors.length > 0) {
        throw new Error(`Uncaught pageerrors detected:\n${pageErrors.join('\n')}`);
      }
      if (failedRequests.length > 0) {
        throw new Error(`Failed network requests detected:\n${failedRequests.join('\n')}`);
      }
      if (unexpectedHttp.length > 0) {
        throw new Error(
          `Unexpected HTTP >=400 responses:\n${unexpectedHttp.map((e) => `${e.status} ${e.method} ${e.url}`).join('\n')}`,
        );
      }
    },
  };
}

export const studioSelectors = {
  emptyState: (page: Page): Locator => page.getByTestId('empty-canvas-state'),
  emptyFileInput: (page: Page): Locator =>
    page.locator('[data-testid="empty-canvas-state"] input[type="file"]'),
  leftSidebar: (page: Page): Locator =>
    page.locator('aside[aria-label="Danh sách sản phẩm"], aside[aria-label="Product queue"]'),
  leftSidebarFileInput: (page: Page): Locator =>
    page.locator(
      'aside[aria-label="Danh sách sản phẩm"] input[type="file"], aside[aria-label="Product queue"] input[type="file"]',
    ),
  rightSidebar: (page: Page): Locator =>
    page.locator('aside[aria-label="Mở bảng công cụ"], aside[aria-label="Toggle tools panel"]'),
  topToolbar: (page: Page): Locator => page.getByTestId('canvas-top-toolbar'),
  toolbarPresetInfo: (page: Page): Locator => page.getByTestId('toolbar-preset-info'),
  bottomDock: (page: Page): Locator => page.getByTestId('canvas-bottom-dock'),
  canvas: (page: Page): Locator => page.locator('main canvas'),
  langViButton: (page: Page): Locator => page.getByRole('button', { name: 'VI', exact: true }),
  langEnButton: (page: Page): Locator => page.getByRole('button', { name: 'EN', exact: true }),
  exportButton: (page: Page): Locator =>
    page.locator('header button').filter({ hasText: /Xuất ZIP|Export ZIP/i }),
  proofingShareButton: (page: Page): Locator =>
    page.locator('header button[title="Tạo link duyệt khách"], header button[title="Share proofing link"]'),
  mobileLeftDrawerToggle: (page: Page): Locator =>
    page.getByRole('button', { name: /Mở danh sách sản phẩm|Toggle product queue/i }),
  mobileRightDrawerToggle: (page: Page): Locator =>
    page.getByRole('button', { name: /Mở bảng công cụ|Toggle tools panel/i }),
};

export async function pasteImageFile(
  page: Page,
  pngBase64: string,
  filename = 'pasted.png',
): Promise<void> {
  // Ensure React hydration + useEffect(window.addEventListener('paste', ...)) is complete
  const isCurrentlyVi = await page
    .locator('header button[title="Tạo link duyệt khách"]')
    .isVisible()
    .catch(() => false);
  if (isCurrentlyVi) {
    await studioSelectors.langEnButton(page).click();
    await page.locator('header button[title="Share proofing link"]').waitFor();
    await studioSelectors.langViButton(page).click();
    await page.locator('header button[title="Tạo link duyệt khách"]').waitFor();
  } else {
    await studioSelectors.langViButton(page).click();
    await page.locator('header button[title="Tạo link duyệt khách"]').waitFor();
    await studioSelectors.langEnButton(page).click();
    await page.locator('header button[title="Share proofing link"]').waitFor();
  }

  await page.evaluate(
    ({ b64, fname }) => {
      const bin = atob(b64);
      const bytes = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      const file = new File([bytes], fname, { type: 'image/png' });
      const dt = new DataTransfer();
      dt.items.add(file);
      const ev = new ClipboardEvent('paste', {
        bubbles: true,
        cancelable: true,
      });
      Object.defineProperty(ev, 'clipboardData', {
        configurable: true,
        value: dt,
      });
      window.dispatchEvent(ev);
    },
    { b64: pngBase64, fname: filename },
  );
}
