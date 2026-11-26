import { MarketplacePreset, ProofingSession } from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export async function fetchPresets(): Promise<MarketplacePreset[]> {
  try {
    const res = await fetch(`${API_BASE}/v1/presets`, { cache: 'no-store' });
    if (res.ok) {
      const data = await res.json();
      if (data && data.items) {
        return data.items;
      }
    }
  } catch (err) {
    console.warn('Backend presets not available, using local presets fallbacks.', err);
  }
  const { MARKETPLACE_PRESETS } = await import('./presets');
  return MARKETPLACE_PRESETS;
}

export async function createProofingSession(
  projectId: string,
  title: string,
  clientName: string,
  allowComments: boolean = true
): Promise<ProofingSession | null> {
  try {
    const res = await fetch(`${API_BASE}/v1/proofing`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_id: projectId,
        title,
        client_name: clientName,
        allow_comments: allowComments,
      }),
    });
    if (res.ok) {
      const data = await res.json();
      return {
        id: data.id,
        projectId: data.project_id,
        title: data.title,
        clientName: data.client_name,
        status: data.status,
        createdAt: data.created_at,
        allowComments: data.allow_comments,
        comments: data.comments || [],
      };
    }
  } catch (err) {
    console.error('Failed to create proofing session on backend:', err);
  }
  // Fallback local session if offline
  return {
    id: `proof_${Math.random().toString(36).substring(2, 9)}`,
    projectId,
    title,
    clientName,
    status: 'pending',
    createdAt: new Date().toISOString(),
    allowComments,
    comments: [],
  };
}
