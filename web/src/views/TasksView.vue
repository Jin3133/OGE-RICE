<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'

import ReferenceAreaMap from '@/components/ReferenceAreaMap.vue'
import { ApiRequestError, api } from '@/services/api'
import { useTaskDraftStore, type TaskConfiguration } from '@/stores/taskDraft'
import type { ReferenceAreaFeatureCollection } from '@/types/api'
import type { AnalysisTaskDraftResponse } from '@/types/api'
import type { AnalysisAreaSelection } from '@/types/map'

const taskDraft = useTaskDraftStore()
const collection = ref<ReferenceAreaFeatureCollection | null>(null)
const loadError = ref('')
const historyError = ref('')
const backendDrafts = ref<AnalysisTaskDraftResponse[]>([])
const savedMessage = ref('')
const submitError = ref('')
const submitting = ref(false)
const form = reactive<TaskConfiguration>({ ...taskDraft.configuration })

const stages = [
  ['reviving', '返青期'],
  ['tillering', '分蘖期'],
  ['jointing_booting', '拔节孕穗期'],
  ['heading_flowering', '抽穗开花期'],
  ['filling_maturity', '灌浆成熟期'],
] as const

const validation = computed(() => ({
  area: taskDraft.area !== null,
  name: form.name.trim().length >= 2 && form.name.trim().length <= 80,
  year: form.analysisYear >= 2020 && form.analysisYear <= 2030,
  period: Boolean(form.periodStart && form.periodEnd && form.periodStart <= form.periodEnd),
  quota: form.quotaM3PerMu !== null && form.quotaM3PerMu > 0,
  source: form.quotaSource.trim().length >= 2,
}))
const valid = computed(() => Object.values(validation.value).every(Boolean))
const areaLabel = computed(() => taskDraft.area ? `${(taskDraft.area.area_square_metres / 1_000_000).toFixed(2)} km²` : '未选择')
const demandLabel = computed(() => {
  if (!taskDraft.area || form.quotaM3PerMu === null || form.quotaM3PerMu <= 0) return '待填写定额'
  const areaMu = taskDraft.area.area_square_metres * 0.0015
  return `${Math.round(areaMu * form.quotaM3PerMu).toLocaleString()} m³`
})

function updateArea(value: AnalysisAreaSelection | null) {
  taskDraft.setArea(value)
}

function saveDraft() {
  if (!valid.value) return
  taskDraft.saveConfiguration({ ...form })
  savedMessage.value = '任务草稿已保存在当前浏览器会话中，尚未提交运行。'
}

function restoreDraft(value: AnalysisTaskDraftResponse) {
  taskDraft.restoreFromBackend(value)
  Object.assign(form, taskDraft.configuration)
  savedMessage.value = `已恢复后台草稿 ${value.draft_id}`
}

async function registerDraft() {
  if (!valid.value || !taskDraft.area || form.quotaM3PerMu === null) return
  submitting.value = true
  submitError.value = ''
  if (JSON.stringify(form) !== JSON.stringify(taskDraft.configuration)) {
    taskDraft.saveConfiguration({ ...form })
  }
  const stageName = stages.find((stage) => stage[0] === form.growthStage)?.[1] ?? form.growthStage
  try {
    const result = await api.createTaskDraft({
      name: form.name,
      result_mode: 'illustrative',
      crop_code: 'rice',
      analysis_year: form.analysisYear,
      season: form.season,
      growth_stage_code: form.growthStage,
      growth_stage_name: stageName,
      analysis_start: form.periodStart,
      analysis_end: form.periodEnd,
      quota_value_m3_per_mu: form.quotaM3PerMu,
      quota_source: form.quotaSource,
      area: {
        method: taskDraft.area.method,
        source_area_id: taskDraft.area.source_area_id,
        geometry: taskDraft.area.geometry,
      },
      created_by: 'local.operator',
    }, taskDraft.submissionKey)
    taskDraft.markRegistered(result.draft_id, result.revision)
  } catch (reason) {
    submitError.value = reason instanceof Error ? reason.message : '草稿登记失败'
  } finally {
    submitting.value = false
  }
}

watch(form, () => taskDraft.invalidateRegistration(), { deep: true })

onMounted(async () => {
  try {
    const [areas, drafts] = await Promise.all([api.referenceAreas(), api.taskDrafts()])
    collection.value = areas
    backendDrafts.value = drafts.items
  } catch (reason) {
    const message = reason instanceof ApiRequestError ? reason.message : '任务数据加载失败'
    loadError.value = message
    historyError.value = message
  }
})
</script>

<template>
  <section class="task-page">
    <div class="task-heading">
      <div>
        <span class="section-tag">ANALYSIS TASK DRAFT</span>
        <h2>配置分析任务</h2>
        <p>先冻结任务范围和阶段参数。当前结果模式固定为演示性耕地候选区情景，不代表已独立识别水稻。</p>
      </div>
      <span class="draft-badge">草稿 · 尚未提交</span>
    </div>

    <div class="draft-history">
      <div class="history-heading">
        <div><strong>后台任务草稿</strong><span>进入页面自动读取数据库中的最新版本</span></div>
        <em>{{ backendDrafts.length }} 条记录</em>
      </div>
      <p v-if="historyError" class="submit-error">{{ historyError }}</p>
      <div v-else-if="backendDrafts.length" class="history-list">
        <article v-for="draft in backendDrafts" :key="`${draft.draft_id}@${draft.revision}`" :class="{ active: taskDraft.registered?.draftId === draft.draft_id }">
          <div><strong>{{ draft.name }}</strong><span>{{ draft.growth_stage_name }} · {{ draft.analysis_start }} 至 {{ draft.analysis_end }}</span></div>
          <div class="history-meta"><span>{{ (draft.area_square_metres / 1_000_000).toFixed(2) }} km²</span><code>{{ draft.draft_id.slice(0, 18) }}…</code></div>
          <button type="button" @click="restoreDraft(draft)">恢复编辑</button>
        </article>
      </div>
      <p v-else class="history-empty">暂无后台草稿。地图选区和本机草稿仍会自动恢复。</p>
    </div>

    <div class="task-workbench">
      <div class="task-map-panel">
        <ReferenceAreaMap v-if="!loadError" :collection="collection" :initial-selection="taskDraft.area" @selection="updateArea" />
        <div v-else class="map-state is-error">{{ loadError }}</div>
      </div>

      <form class="task-form" @submit.prevent="saveDraft">
        <div class="form-section-title"><span>01</span><div><strong>基本信息</strong><small>用于识别和追溯任务</small></div></div>
        <label class="field-row">
          <span>任务名称</span>
          <input v-model.trim="form.name" maxlength="80" placeholder="例如：江夏区2025年分蘖期分析" />
          <small v-if="form.name && !validation.name">名称需为2—80个字符</small>
        </label>
        <div class="form-grid">
          <label><span>分析年度</span><input v-model.number="form.analysisYear" type="number" min="2020" max="2030" /></label>
          <label><span>种植季</span><select v-model="form.season"><option value="single_season_rice">单季稻</option><option value="early_rice">早稻</option><option value="late_rice">晚稻</option></select></label>
        </div>

        <div class="form-section-title"><span>02</span><div><strong>生育阶段</strong><small>系统推荐后由管理人员确认</small></div></div>
        <label class="field-row"><span>当前阶段</span><select v-model="form.growthStage"><option v-for="stage in stages" :key="stage[0]" :value="stage[0]">{{ stage[1] }}</option></select></label>
        <div class="form-grid">
          <label><span>开始日期</span><input v-model="form.periodStart" type="date" /></label>
          <label><span>结束日期</span><input v-model="form.periodEnd" type="date" /></label>
        </div>

        <div class="form-section-title"><span>03</span><div><strong>阶段灌溉定额</strong><small>必须注明来源，不自动填入建议值</small></div></div>
        <label class="field-row"><span>定额（m³/亩）</span><input v-model.number="form.quotaM3PerMu" type="number" min="0.01" step="0.01" placeholder="请输入经确认的阶段定额" /></label>
        <label class="field-row"><span>定额来源</span><input v-model.trim="form.quotaSource" placeholder="地方标准、已有项目成果或用户确认依据" /></label>

        <div class="task-calculation">
          <div><span>分析范围</span><strong>{{ areaLabel }}</strong></div>
          <div><span>参考需水</span><strong>{{ demandLabel }}</strong></div>
          <p>计算采用 W = A × M；面积按 1亩 = 2000/3平方米换算。保存草稿不会创建正式任务或触发遥感计算。</p>
        </div>
        <div class="task-actions">
          <button class="save-local" type="submit" :disabled="!valid">保存本机草稿</button>
          <button class="save-draft" type="button" :disabled="!valid || submitting || Boolean(taskDraft.registered)" @click="registerDraft">
            {{ submitting ? '正在登记…' : taskDraft.registered ? '已登记后台' : '登记业务后台' }}
          </button>
        </div>
        <p v-if="savedMessage" class="saved-message">{{ savedMessage }}</p>
        <div v-if="taskDraft.registered" class="registered-draft">
          <strong>后台草稿登记成功</strong>
          <span>{{ taskDraft.registered.draftId }} · 第 {{ taskDraft.registered.revision }} 版</span>
          <p>已持久化并写入审计记录；尚未提升为正式分析任务，也未触发OGE计算。</p>
        </div>
        <p v-if="submitError" class="submit-error">{{ submitError }}</p>
      </form>
    </div>
  </section>
</template>
