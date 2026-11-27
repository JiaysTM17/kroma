import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

export const API_URL = (process.env.E2E_API_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');
export const BASE_URL = (process.env.E2E_BASE_URL || 'http://localhost:3005').replace(/\/+$/, '');

export interface ApiResponse<T = any> {
  status: number;
  ok: boolean;
  headers: Headers;
  data: T;
  text: string;
}

export interface BinaryApiResponse {
  status: number;
  ok: boolean;
  headers: Headers;
  buffer: Buffer;
}

export interface UnifiedErrorBody {
  code: string;
  message: string;
  correlation_id: string;
  retryable: boolean;
}

export interface SafeZone {
  top: number;
  right: number;
  bottom: number;
  left: number;
}

export interface MarketplacePresetDto {
  id: string;
  marketplace: string;
  name_en: string;
  name_vi: string;
  rule_description_en?: string;
  rule_description_vi?: string;
  version: string;
  aspect_ratio: string;
  width: number;
  height: number;
  formats: string[];
  background_rgb: number[] | null;
  subject_area_ratio: number | null;
  safe_zone: SafeZone | null;
  is_system?: boolean;
  editable: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface AssetDto {
  id?: string;
  asset_id: string;
  project_id: string;
  kind: string;
  parent_asset_id?: string | null;
  variant?: string;
  filename: string;
  mime_type: string;
  sha256: string;
  byte_size: number;
  width: number;
  height: number;
  exif_orientation: number;
  is_readonly: boolean;
  metadata?: Record<string, unknown>;
  file_url?: string;
  created_at: string;
  updated_at?: string;
}

export interface ProjectDto {
  id: string;
  name: string;
  description: string;
  active_variant: string;
  created_at: string;
  updated_at: string;
  state?: Record<string, unknown>;
  assets?: AssetDto[];
}

export interface ProjectStateDto {
  project_id: string;
  schema_version: number;
  revision_id: string;
  active_variant: string;
  state: Record<string, unknown>;
  updated_at: string;
}

export interface BatchJobItemDto {
  id?: string;
  item_id?: string;
  asset_id: string;
  preset_id: string;
  format?: string;
  status: string;
  output_filename?: string | null;
  error_message?: string | null;
}

export interface BatchJobDto {
  job_id: string;
  project_id: string;
  status: string;
  total_items: number;
  completed_items: number;
  failed_items: number;
  progress: number;
  download_url: string | null;
  error_message: string | null;
  items: BatchJobItemDto[];
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface ProofingCommentDto {
  id: string;
  author: string;
  action: string;
  comment?: string;
  body?: string;
  pin_x?: number | null;
  pin_y?: number | null;
  resolved?: boolean;
  resolved_by?: string | null;
  resolved_at?: string | null;
  created_at: string;
}

export interface ProofingSessionDto {
  id: string;
  project_id: string;
  asset_id?: string | null;
  asset_url?: string | null;
  project_revision_id?: string | null;
  revision_stale?: boolean;
  title: string;
  client_name: string;
  status: string;
  allow_comments: boolean;
  approved_by?: string | null;
  approved_at?: string | null;
  expires_at?: string | null;
  revoked_at?: string | null;
  comments?: ProofingCommentDto[];
  feedback?: ProofingCommentDto[];
  events?: Array<Record<string, unknown>>;
  created_at: string;
  updated_at?: string;
}

export function sha256Hex(buf: Buffer): string {
  return crypto.createHash('sha256').update(buf).digest('hex');
}

export function uniqueId(prefix: string): string {
  return `${prefix}_${Date.now()}_${crypto.randomBytes(3).toString('hex')}`;
}

export class KromaApiClient {
  readonly baseUrl: string;

  constructor(baseUrl: string = API_URL) {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
  }

  private buildUrl(urlPath: string): string {
    if (urlPath.startsWith('http://') || urlPath.startsWith('https://')) {
      return urlPath;
    }
    return `${this.baseUrl}${urlPath.startsWith('/') ? '' : '/'}${urlPath}`;
  }

  async request<T = any>(
    method: string,
    urlPath: string,
    options?: {
      json?: unknown;
      headers?: Record<string, string>;
      correlationId?: string;
    },
  ): Promise<ApiResponse<T>> {
    const headers: Record<string, string> = {
      ...(options?.headers ?? {}),
    };
    if (options?.correlationId !== undefined) {
      headers['x-correlation-id'] = options.correlationId;
    }
    let body: BodyInit | undefined;
    if (options?.json !== undefined) {
      headers['content-type'] = 'application/json';
      body = JSON.stringify(options.json);
    }

    const res = await fetch(this.buildUrl(urlPath), {
      method,
      headers,
      body,
    });
    const text = await res.text();
    let data: any = null;
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        data = text;
      }
    }
    return {
      status: res.status,
      ok: res.ok,
      headers: res.headers,
      data,
      text,
    };
  }

  async get<T = any>(urlPath: string, headers?: Record<string, string>): Promise<ApiResponse<T>> {
    return this.request<T>('GET', urlPath, { headers });
  }

  async post<T = any>(urlPath: string, json?: unknown, headers?: Record<string, string>): Promise<ApiResponse<T>> {
    return this.request<T>('POST', urlPath, { json, headers });
  }

  async put<T = any>(urlPath: string, json?: unknown, headers?: Record<string, string>): Promise<ApiResponse<T>> {
    return this.request<T>('PUT', urlPath, { json, headers });
  }

  async patch<T = any>(urlPath: string, json?: unknown, headers?: Record<string, string>): Promise<ApiResponse<T>> {
    return this.request<T>('PATCH', urlPath, { json, headers });
  }

  async delete<T = any>(urlPath: string, headers?: Record<string, string>): Promise<ApiResponse<T>> {
    return this.request<T>('DELETE', urlPath, { headers });
  }

  async getBinary(urlPath: string, headers?: Record<string, string>): Promise<BinaryApiResponse> {
    const res = await fetch(this.buildUrl(urlPath), {
      method: 'GET',
      headers,
    });
    const ab = await res.arrayBuffer();
    return {
      status: res.status,
      ok: res.ok,
      headers: res.headers,
      buffer: Buffer.from(ab),
    };
  }

  async uploadAsset<T = any>(
    projectId: string,
    opts: {
      filePath?: string;
      buffer?: Buffer;
      filename?: string;
      contentType?: string;
      kind?: string;
      parentAssetId?: string;
      variant?: string;
      metadataJson?: string;
    },
  ): Promise<ApiResponse<T>> {
    const buf = opts.buffer ?? (opts.filePath ? fs.readFileSync(opts.filePath) : Buffer.alloc(0));
    const filename = opts.filename ?? (opts.filePath ? path.basename(opts.filePath) : 'upload.png');
    const inferredMime =
      opts.contentType ??
      (filename.toLowerCase().endsWith('.jpg') || filename.toLowerCase().endsWith('.jpeg')
        ? 'image/jpeg'
        : filename.toLowerCase().endsWith('.webp')
          ? 'image/webp'
          : 'image/png');

    const form = new FormData();
    const blob = new Blob([new Uint8Array(buf)], { type: inferredMime });
    form.append('file', blob, filename);

    if (opts.kind !== undefined) form.append('kind', opts.kind);
    if (opts.parentAssetId !== undefined) form.append('parent_asset_id', opts.parentAssetId);
    if (opts.variant !== undefined) form.append('variant', opts.variant);
    if (opts.metadataJson !== undefined) form.append('metadata_json', opts.metadataJson);

    const res = await fetch(this.buildUrl(`/v1/projects/${encodeURIComponent(projectId)}/assets`), {
      method: 'POST',
      body: form,
    });
    const text = await res.text();
    let data: any = null;
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        data = text;
      }
    }
    return {
      status: res.status,
      ok: res.ok,
      headers: res.headers,
      data,
      text,
    };
  }

  async pollBatchUntilTerminal(jobId: string, timeoutMs = 30_000, intervalMs = 250): Promise<BatchJobDto> {
    const deadline = Date.now() + timeoutMs;
    const terminal = new Set(['completed', 'partial_failed', 'failed', 'cancelled']);
    let last: BatchJobDto | null = null;
    while (Date.now() < deadline) {
      const res = await this.get<BatchJobDto>(`/v1/batches/${encodeURIComponent(jobId)}`);
      if (res.status === 200 && res.data) {
        last = res.data;
        if (terminal.has(last.status)) {
          return last;
        }
      }
      await new Promise((r) => setTimeout(r, intervalMs));
    }
    throw new Error(`Batch job ${jobId} did not finish within ${timeoutMs}ms. Last status: ${last?.status}`);
  }
}

export const apiClient = new KromaApiClient();
