export type AnalysisAreaMethod = 'reference_area' | 'rectangle' | 'polygon'

export interface AnalysisAreaSelection {
  method: AnalysisAreaMethod
  geometry: {
    type: 'Polygon' | 'MultiPolygon'
    coordinates: number[][][] | number[][][][]
  }
  area_square_metres: number
  source_area_id: string | null
  management_unit_id?: string | null
  management_unit_revision?: number | null
  candidate_area_square_metres?: number | null
}
