export interface HealthResponse {
  status: 'ok'
  service: 'oge-rice-api'
}

export interface ApiErrorDetail {
  code: string
  message: string
  field: string | null
  details: Record<string, unknown>
  request_id: string
}

export interface ApiErrorResponse {
  error: ApiErrorDetail
}
