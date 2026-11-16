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

export interface ReferenceAreaProperties {
  area_id: string
  revision: number
  name: string
  area_type: 'administrative_district' | 'technical_study_area'
  administrative_code: string | null
  area_square_metres: number
  quality_status: 'illustrative' | 'unverified' | 'verified'
  quality_statement: string
  source_title: string
  source_url: string | null
  boundary_role: 'reference_only'
}

export interface ReferenceAreaFeature {
  type: 'Feature'
  id: string
  geometry: {
    type: 'MultiPolygon'
    coordinates: number[][][][]
  }
  properties: ReferenceAreaProperties
}

export interface ReferenceAreaFeatureCollection {
  type: 'FeatureCollection'
  features: ReferenceAreaFeature[]
}
