import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import type { AnalysisAreaSelection } from '@/types/map'

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
    const value = sessionStorage.getItem(storageKey)
    return value ? (JSON.parse(value) as StoredTaskDraft) : { area: null, configuration: defaultConfiguration() }
  } catch {
    return { area: null, configuration: defaultConfiguration() }
  }
}

export const useTaskDraftStore = defineStore('taskDraft', () => {
  const stored = loadDraft()
  const area = ref<AnalysisAreaSelection | null>(stored.area)
  const configuration = ref<TaskConfiguration>(stored.configuration)
  const savedAt = ref<Date | null>(null)

  const areaMu = computed(() => (area.value ? area.value.area_square_metres * 0.0015 : null))
  const estimatedDemandM3 = computed(() => {
    if (areaMu.value === null || configuration.value.quotaM3PerMu === null) return null
    return areaMu.value * configuration.value.quotaM3PerMu
  })

  function persist() {
    sessionStorage.setItem(storageKey, JSON.stringify({ area: area.value, configuration: configuration.value }))
    savedAt.value = new Date()
  }

  function setArea(value: AnalysisAreaSelection | null) {
    area.value = value
    persist()
  }

  function saveConfiguration(value: TaskConfiguration) {
    configuration.value = { ...value }
    persist()
  }

  return { area, areaMu, configuration, estimatedDemandM3, savedAt, setArea, saveConfiguration }
})
