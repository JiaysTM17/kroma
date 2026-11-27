import { test as base, expect } from '@playwright/test';
import { apiClient, KromaApiClient } from '../helpers/apiClient';

export class TestTracker {
  private readonly projectIds = new Set<string>();
  private readonly customPresetIds = new Set<string>();
  private readonly systemPresetIds = new Set<string>();
  private readonly activeBatchIds = new Set<string>();

  constructor(private readonly client: KromaApiClient) {}

  trackProject(id: string | null | undefined): string {
    if (id && id.trim()) {
      this.projectIds.add(id.trim());
    }
    return id ?? '';
  }

  trackCustomPreset(id: string | null | undefined): string {
    if (id && id.trim()) {
      this.customPresetIds.add(id.trim());
    }
    return id ?? '';
  }

  trackSystemPreset(id: string | null | undefined): string {
    if (id && id.trim()) {
      this.systemPresetIds.add(id.trim());
    }
    return id ?? '';
  }

  trackBatch(id: string | null | undefined): string {
    if (id && id.trim()) {
      this.activeBatchIds.add(id.trim());
    }
    return id ?? '';
  }

  async cleanupAll(): Promise<void> {
    // 1. Cancel any active batch jobs
    for (const batchId of this.activeBatchIds) {
      try {
        await this.client.post(`/v1/batches/${encodeURIComponent(batchId)}/cancel`);
      } catch {
        // best-effort cleanup
      }
    }
    this.activeBatchIds.clear();

    // 2. Delete created projects (with legacy fallback on baseline)
    for (const projectId of this.projectIds) {
      try {
        const res = await this.client.delete(`/v1/projects/${encodeURIComponent(projectId)}`);
        if (res.status === 404 || res.status === 405) {
          await this.client.delete(`/api/v1/projects/${encodeURIComponent(projectId)}`);
        }
      } catch {
        // best-effort cleanup
      }
    }
    this.projectIds.clear();

    // 3. Delete created custom presets
    for (const presetId of this.customPresetIds) {
      try {
        await this.client.delete(`/v1/presets/${encodeURIComponent(presetId)}`);
      } catch {
        // best-effort cleanup
      }
    }
    this.customPresetIds.clear();

    // 4. Reset mutated system presets
    for (const presetId of this.systemPresetIds) {
      try {
        await this.client.post(`/v1/presets/${encodeURIComponent(presetId)}/reset`);
      } catch {
        // best-effort cleanup
      }
    }
    this.systemPresetIds.clear();
  }
}

export const test = base.extend<{
  tracker: TestTracker;
  api: KromaApiClient;
}>({
  api: async ({}, use) => {
    await use(apiClient);
  },
  tracker: async ({}, use) => {
    const tracker = new TestTracker(apiClient);
    try {
      await use(tracker);
    } finally {
      await tracker.cleanupAll();
    }
  },
});

export { expect };
