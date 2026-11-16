export type AnalysisAreaMethod = 'reference_area' | 'rectangle' | 'polygon'

export interface AnalysisAreaSelection {
  method: AnalysisAreaMethod
  geometry: {
    type: 'Polygon' | 'MultiPolygon'
    coordinates: number[][][] | number[][][][]
  }
  area_square_metres: number
  source_area_id: string | null
}
