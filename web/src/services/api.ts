import type {
  ApiErrorResponse,
  AnalysisTaskDraftCreate,
  AnalysisTaskDraftCollection,
  AnalysisTaskDraftResponse,
  AnalysisTaskDraftRevisionCreate,
  HealthResponse,
  GeoreferencingFitRequest,
  GeoreferencingFitResponse,
  ManagementUnitCreate,
  ManagementUnitFeature,
  ManagementUnitFeatureCollection,
  ReferenceAreaFeatureCollection,
} from '@/types/api'

export class ApiRequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly requestId?: string,
  ) {
    super(message)
    this.name = 'ApiRequestError'
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...init?.headers,
    },
  })
  if (!response.ok) {
    let message = `请求失败（${response.status}）`
    let requestId: string | undefined
    try {
      const payload = (await response.json()) as ApiErrorResponse
      message = payload.error.message
      requestId = payload.error.request_id
    } catch {
      // Non-JSON upstream failures retain the stable fallback message.
    }
    throw new ApiRequestError(message, response.status, requestId)
  }
  return (await response.json()) as T
}

export const api = {
  health: () => request<HealthResponse>('/api/v1/health/ready'),
  referenceAreas: () =>
    request<ReferenceAreaFeatureCollection>('/api/v1/reference-areas'),
  createTaskDraft: (payload: AnalysisTaskDraftCreate, idempotencyKey: string) =>
    request<AnalysisTaskDraftResponse>('/api/v1/analysis-task-drafts', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Idempotency-Key': idempotencyKey,
      },
      body: JSON.stringify(payload),
    }),
  taskDrafts: () => request<AnalysisTaskDraftCollection>('/api/v1/analysis-task-drafts'),
  managementUnits: () => request<ManagementUnitFeatureCollection>('/api/v1/management-units'),
  createManagementUnit: (payload: ManagementUnitCreate, idempotencyKey: string) =>
    request<ManagementUnitFeature>('/api/v1/management-units', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Idempotency-Key': idempotencyKey,
      },
      body: JSON.stringify(payload),
    }),
  createTaskDraftRevision: (
    draftId: string,
    payload: AnalysisTaskDraftRevisionCreate,
    idempotencyKey: string,
  ) => request<AnalysisTaskDraftResponse>(`/api/v1/analysis-task-drafts/${draftId}/versions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Idempotency-Key': idempotencyKey,
    },
    body: JSON.stringify(payload),
  }),
  fitGeoreferencing: (payload: GeoreferencingFitRequest) =>
    request<GeoreferencingFitResponse>('/api/v1/georeferencing/fit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
}
