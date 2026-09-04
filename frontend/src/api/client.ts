import type {
  ReconciliationSummaryResponse,
  ReconciliationRecordItem,
  ExceptionListItem,
  ExceptionDetailResponse,
  ExceptionClusterResponse,
  AuditLogEntryResponse,
  ExplanationResponse,
  ClusterSummaryResponse,
  ActionResponse,
} from './types';

const BASE_URL = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  if (!resp.ok) {
    const errText = await resp.text();
    let msg = `HTTP ${resp.status}: ${resp.statusText}`;
    try {
      const errJson = JSON.parse(errText);
      msg = errJson.detail || msg;
    } catch {
      if (errText) msg = errText;
    }
    throw new Error(msg);
  }

  return resp.json();
}

export const api = {
  // Reconciliation endpoints
  runReconciliation: () =>
    request<ReconciliationSummaryResponse>('/reconciliation/run', { method: 'POST' }),

  getSummary: () =>
    request<ReconciliationSummaryResponse>('/reconciliation/summary'),

  getRecords: (params?: {
    classification?: string;
    source?: string;
    limit?: number;
    offset?: number;
  }) => {
    const query = new URLSearchParams();
    if (params?.classification) query.set('classification', params.classification);
    if (params?.source) query.set('source', params.source);
    if (params?.limit) query.set('limit', params.limit.toString());
    if (params?.offset) query.set('offset', params.offset.toString());
    const qs = query.toString();
    return request<ReconciliationRecordItem[]>(`/reconciliation/records${qs ? `?${qs}` : ''}`);
  },

  // Exceptions endpoints
  getExceptions: (params?: {
    exception_type?: string;
    resolution_status?: string;
    min_impact?: number;
    limit?: number;
    offset?: number;
  }) => {
    const query = new URLSearchParams();
    if (params?.exception_type) query.set('exception_type', params.exception_type);
    if (params?.resolution_status) query.set('resolution_status', params.resolution_status);
    if (params?.min_impact !== undefined) query.set('min_impact', params.min_impact.toString());
    if (params?.limit) query.set('limit', params.limit.toString());
    if (params?.offset) query.set('offset', params.offset.toString());
    const qs = query.toString();
    return request<ExceptionListItem[]>(`/exceptions${qs ? `?${qs}` : ''}`);
  },

  getExceptionDetail: (id: string) =>
    request<ExceptionDetailResponse>(`/exceptions/${encodeURIComponent(id)}`),

  approveException: (id: string, notes?: string, actor?: string) =>
    request<ActionResponse>(`/exceptions/${encodeURIComponent(id)}/approve`, {
      method: 'POST',
      body: JSON.stringify({ actor: actor || 'OPERATOR', notes }),
    }),

  rejectException: (id: string, notes?: string, actor?: string) =>
    request<ActionResponse>(`/exceptions/${encodeURIComponent(id)}/reject`, {
      method: 'POST',
      body: JSON.stringify({ actor: actor || 'OPERATOR', notes }),
    }),

  unresolveException: (id: string, notes?: string, actor?: string) =>
    request<ActionResponse>(`/exceptions/${encodeURIComponent(id)}/unresolve`, {
      method: 'POST',
      body: JSON.stringify({ actor: actor || 'OPERATOR', notes }),
    }),

  explainException: (id: string) =>
    request<ExplanationResponse>(`/exceptions/${encodeURIComponent(id)}/explain`),

  // Clusters
  getClusters: () =>
    request<ExceptionClusterResponse[]>('/exception-clusters'),

  getClusterSummary: (clusterId: string) =>
    request<ClusterSummaryResponse>(`/exception-clusters/${encodeURIComponent(clusterId)}/summary`),

  // Audit Log
  getAuditLog: (params?: {
    transaction_id?: string;
    exception_id?: string;
    event_type?: string;
    order?: 'asc' | 'desc';
    limit?: number;
    offset?: number;
  }) => {
    const query = new URLSearchParams();
    if (params?.transaction_id) query.set('transaction_id', params.transaction_id);
    if (params?.exception_id) query.set('exception_id', params.exception_id);
    if (params?.event_type) query.set('event_type', params.event_type);
    if (params?.order) query.set('order', params.order);
    if (params?.limit) query.set('limit', params.limit.toString());
    if (params?.offset) query.set('offset', params.offset.toString());
    const qs = query.toString();
    return request<AuditLogEntryResponse[]>(`/audit-log${qs ? `?${qs}` : ''}`);
  },

  // Data Quality
  getDataQuality: () =>
    request<import('./types').DataQualityResponse>('/data-quality'),
};
