import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import type { AnalysisAreaSelection } from '@/types/map'
import type { AnalysisTaskDraftResponse } from '@/types/api'

export interface TaskConfiguration {
  name: string
  analysisYear: number
  season: 'single_season_rice' | 'early_rice' | 'late_rice'
  growthStage: string
  periodStart: string
  periodEnd: string
  quotaM3PerMu: number | null
  quotaSource: string
}

interface StoredTaskDraft {
  area: AnalysisAreaSelection | null
  configuration: TaskConfiguration
  submissionKey: string
  registered: { draftId: string; revision: number } | null
}

const storageKey = 'oge-rice.analysis-task-draft.v1'

function defaultConfiguration(): TaskConfiguration {
  return {
    name: '',
    analysisYear: 2025,
    season: 'single_season_rice',
    growthStage: 'tillering',
    periodStart: '',
    periodEnd: '',
    quotaM3PerMu: null,
    quotaSource: '',
  }
}

function loadDraft(): StoredTaskDraft {
  try {
    const value = localStorage.getItem(storageKey) ?? sessionStorage.getItem(storageKey)
    return value
      ? (JSON.parse(value) as StoredTaskDraft)
      : { area: null, configuration: defaultConfiguration(), submissionKey: crypto.randomUUID(), registered: null }
  } catch {
    return { area: null, configuration: defaultConfiguration(), submissionKey: crypto.randomUUID(), registered: null }
  }
}

export const useTaskDraftStore = defineStore('taskDraft', () => {
  const stored = loadDraft()
  const area = ref<AnalysisAreaSelection | null>(stored.area)
  const configuration = ref<TaskConfiguration>(stored.configuration)
  const savedAt = ref<Date | null>(null)
  const submissionKey = ref(stored.submissionKey || crypto.randomUUID())
  const registered = ref(stored.registered ?? null)

  const areaMu = computed(() => (area.value ? area.value.area_square_metres * 0.0015 : null))
  const estimatedDemandM3 = computed(() => {
    if (areaMu.value === null || configuration.value.quotaM3PerMu === null) return null
    return areaMu.value * configuration.value.quotaM3PerMu
  })

  function persist() {
    localStorage.setItem(storageKey, JSON.stringify({
      area: area.value,
      configuration: configuration.value,
      submissionKey: submissionKey.value,
      registered: registered.value,
    }))
    savedAt.value = new Date()
  }

  function setArea(value: AnalysisAreaSelection | null) {
    area.value = value
    registered.value = null
    submissionKey.value = crypto.randomUUID()
    persist()
  }

  function saveConfiguration(value: TaskConfiguration) {
    configuration.value = { ...value }
    registered.value = null
    submissionKey.value = crypto.randomUUID()
    persist()
  }

  function markRegistered(draftId: string, revision: number) {
    registered.value = { draftId, revision }
    persist()
  }

  function invalidateRegistration() {
    if (!registered.value) return
    registered.value = null
    submissionKey.value = crypto.randomUUID()
    persist()
  }

  function restoreFromBackend(value: AnalysisTaskDraftResponse) {
    area.value = {
      method: value.area.method,
      geometry: value.area.geometry,
      area_square_metres: value.area_square_metres,
      source_area_id: value.area.source_area_id,
    }
    configuration.value = {
      name: value.name,
      analysisYear: value.analysis_year,
      season: value.season,
      growthStage: value.growth_stage_code,
      periodStart: value.analysis_start,
      periodEnd: value.analysis_end,
      quotaM3PerMu: value.quota_value_m3_per_mu,
      quotaSource: value.quota_source,
    }
    registered.value = { draftId: value.draft_id, revision: value.revision }
    submissionKey.value = crypto.randomUUID()
    persist()
  }

  return {
    area, areaMu, configuration, estimatedDemandM3, savedAt, submissionKey, registered,
    setArea, saveConfiguration, markRegistered, invalidateRegistration, restoreFromBackend,
  }
})
