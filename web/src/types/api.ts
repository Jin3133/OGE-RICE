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

export interface AnalysisTaskDraftCreate {
  name: string
  result_mode: 'illustrative'
  crop_code: 'rice'
  analysis_year: number
  season: 'single_season_rice' | 'early_rice' | 'late_rice'
  growth_stage_code: string
  growth_stage_name: string
  analysis_start: string
  analysis_end: string
  quota_value_m3_per_mu: number
  quota_source: string
  area: {
    method: 'reference_area' | 'rectangle' | 'polygon'
    source_area_id: string | null
    geometry: {
      type: 'Polygon' | 'MultiPolygon'
      coordinates: number[][][] | number[][][][]
    }
  }
  created_by: string
}

export interface AnalysisTaskDraftResponse extends AnalysisTaskDraftCreate {
  draft_id: string
  revision: number
  status: 'draft' | 'promoted' | 'withdrawn'
  area_square_metres: number
  created_at: string
  changed_at: string
  change_reason: string
}

export interface AnalysisTaskDraftCollection {
  items: AnalysisTaskDraftResponse[]
  total: number
}
