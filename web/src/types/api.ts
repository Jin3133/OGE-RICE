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

export interface AnalysisTaskDraftRevisionCreate extends AnalysisTaskDraftCreate {
  expected_revision: number
  change_reason: string
}

export interface AnalysisTaskDraftCollection {
  items: AnalysisTaskDraftResponse[]
  total: number
}

export type ManagementUnitType = 'irrigation_district' | 'management_zone' | 'custom'

export interface ManagementUnitFeature {
  type: 'Feature'
  id: string
  geometry: {
    type: 'Polygon' | 'MultiPolygon'
    coordinates: number[][][] | number[][][][]
  }
  properties: {
    unit_id: string
    revision: number
    name: string
    unit_type: ManagementUnitType
    valid_start: string
    valid_end: string
    root_unit_id: string
    root_revision: number
    parent_unit_id: string | null
    parent_revision: number | null
    area_square_metres: number
    source_title: string
    source_url: string | null
    quality_status: 'illustrative' | 'unverified' | 'verified'
    quality_statement: string
    status: 'draft' | 'active' | 'superseded' | 'withdrawn'
    changed_by: string
    changed_at: string
  }
}

export interface ManagementUnitFeatureCollection {
  type: 'FeatureCollection'
  features: ManagementUnitFeature[]
}

export interface BusinessUnitResult {
  unit_id: string
  unit_name: string
  candidate_area_m2: number
  candidate_area_mu: number
  growth_stage: string
  irrigation_quota_m3_per_mu: number | null
  reference_irrigation_demand_m3: number | null
  area_source: string
  demand_share: number | null
  attention_level: string
  quality_statement: string
  remote_sensing_evidence: Record<string, unknown>
}

export interface BusinessResultResponse {
  task_id: string
  result_version: number
  generated_at: string
  status: 'completed' | 'parameter_pending'
  business_scope: string
  crop_type: 'rice'
  model_target: 'cultivated_land_candidate' | 'rice_field_candidate'
  growth_stage: string
  calculation_formula: string
  total_candidate_area_mu: number
  total_reference_irrigation_demand_m3: number | null
  parameter_basis: {
    region?: string
    irrigation_zone?: string
    seasonal_quota_m3_per_mu?: number
    seasonal_quota_assurance_probability?: string
    seasonal_quota_level?: string
    seasonal_quota_source?: string
    seasonal_reference_demand_m3?: number
    stage_quota_status: string
    statement: string
  } | null
  units: BusinessUnitResult[]
  limitations: string[]
}

export interface BusinessResultCollection {
  items: BusinessResultResponse[]
  total: number
}

export interface ModelPipelineUnitInput {
  unit_id: string
  unit_revision: number
  valid_observation_mask_path: string
}

export interface ModelPipelineCreate {
  scene_id: string
  result_id: string
  source_image_path: string
  fit_response_path: string
  checkpoint_path: string
  inference_valid_mask_path: string
  reference_mask_path: string | null
  target: 'cultivated_land_candidate' | 'rice_field_candidate'
  threshold: number
  observation_start: string
  observation_end: string
  growth_stage: string
  units: ModelPipelineUnitInput[]
  changed_by: string
  change_reason: string
}

export interface ModelPipelineOperationResponse {
  operation_id: string
  status: 'queued' | 'running' | 'succeeded' | 'failed'
  submitted_by: string
  submitted_at: string
  started_at: string | null
  finished_at: string | null
  result_id: string | null
  result_revision: number | null
  area_statistics: Array<Record<string, unknown>>
  business_result_task_id: string | null
  error_code: string | null
  error_message: string | null
}

export interface AgronomyRecommendationResponse {
  parameter_set_id: string
  region_name: string
  administrative_code: string
  irrigation_zone: string
  crop: 'rice'
  season: 'single_season_rice'
  analysis_date: string
  recommended_stage: {
    code: string
    name: string
    start: string
    end: string
    requires_user_confirmation: boolean
  } | null
  stage_evidence_note: string
  seasonal_quotas: Array<{
    assurance_probability: 'P50' | 'P90'
    level: 'general' | 'advanced'
    value_m3_per_mu: number
    value_m3_per_hm2: number
  }>
  stage_quota_status: 'missing'
  stage_quota_message: string
  sources: Array<{ title: string; publisher: string; url: string; applies_to: string }>
}

export interface ManagementUnitCreate {
  name: string
  unit_type: ManagementUnitType
  valid_start: string
  valid_end: string
  parent: { unit_id: string; revision: number } | null
  geometry: ManagementUnitFeature['geometry']
  source_title: string
  source_url: string | null
  quality_status: 'unverified' | 'verified'
  quality_statement: string
  status: 'draft' | 'active'
  changed_by: string
}

export interface GeoreferencingControlPoint {
  point_id: string
  pixel_x: number
  pixel_y: number
  longitude: number
  latitude: number
}

export interface GeoreferencingSuggestionResponse {
  method: 'sift_affine_ransac_v1'
  status: 'review_required'
  detected_matches: number
  ransac_inliers: number
  points: Array<GeoreferencingControlPoint & { match_distance: number }>
}

export interface PixelBoundaryGeometry {
  type: 'Polygon' | 'MultiPolygon'
  coordinates: number[][][] | number[][][][]
}

export interface GeoreferencingFitRequest {
  image_id: string
  image_width: number
  image_height: number
  projected_crs: string
  control_points: GeoreferencingControlPoint[]
  pixel_boundary: PixelBoundaryGeometry | null
}

export interface GeoreferencingResidual {
  point_id: string
  predicted_easting: number
  predicted_northing: number
  residual_easting: number
  residual_northing: number
  error_metres: number
}

export interface GeoreferencingFitResponse {
  image_id: string
  image_width: number
  image_height: number
  quality_status: 'unverified'
  report: {
    method: 'affine_least_squares'
    projected_crs: string
    coefficients_easting: number[]
    coefficients_northing: number[]
    control_point_count: number
    design_matrix_rank: number
    rmse_metres: number
    maximum_error_metres: number
    residuals: GeoreferencingResidual[]
  }
  boundary: {
    type: 'Feature'
    geometry: PixelBoundaryGeometry
    properties: Record<string, unknown>
  } | null
}
