<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import BusinessResultMap from '@/components/BusinessResultMap.vue'
import { api } from '@/services/api'
import type { BusinessResultResponse, ManagementUnitFeature } from '@/types/api'

const result = ref<BusinessResultResponse | null>(null)
const unit = ref<ManagementUnitFeature | null>(null)
const loading = ref(true)
const error = ref('')

const firstUnit = computed(() => result.value?.units[0] ?? null)
const isModelCandidate = computed(() => firstUnit.value?.area_source === 'model_candidate_mask')
const areaLabel = computed(() => isModelCandidate.value ? '模型候选面积' : '人工标注面积')
const areaSourceLabel = computed(() => isModelCandidate.value ? '模型候选掩膜' : '已有人工标注')
const modelEvidence = computed(() => firstUnit.value?.remote_sensing_evidence ?? {})
const stageLabel = computed(() => ({
  reviving: '返青期',
  tillering: '分蘖期',
  jointing_booting: '拔节孕穗期',
  heading_flowering: '抽穗开花期',
  filling_maturity: '灌浆成熟期',
}[result.value?.growth_stage ?? ''] ?? result.value?.growth_stage ?? '—'))

onMounted(async () => {
  try {
    const [results, units] = await Promise.all([api.businessResults(), api.managementUnits()])
    result.value = results.items[0] ?? null
    const unitId = result.value?.units[0]?.unit_id
    unit.value = units.features.find((item) => item.properties.unit_id === unitId) ?? null
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '成果数据读取失败'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <section class="result-page">
    <div class="map-intro">
      <div><span class="section-tag">VERSIONED BUSINESS RESULT</span><h2>成果研判</h2><p>展示已经完成的面积统计与分阶段参考灌溉需水结果，并保留管理单元、参数和质量说明。</p></div>
      <span v-if="result" class="reference-badge">第 {{ result.result_version }} 版 · {{ result.status === 'completed' ? '计算完成' : '阶段参数待确认' }}</span>
    </div>
    <div v-if="loading" class="map-state">正在读取业务成果…</div>
    <div v-else-if="error" class="map-state is-error">{{ error }}</div>
    <div v-else-if="!result" class="map-state">尚无已完成的业务成果。</div>
    <template v-else>
      <div class="result-metrics">
        <article><span>{{ areaLabel }}</span><strong>{{ result.total_candidate_area_mu.toLocaleString() }}</strong><small>亩 · {{ isModelCandidate ? '待复核' : '参考成果' }}</small></article>
        <article><span>当前生育阶段</span><strong>{{ stageLabel }}</strong><small>区域作物历建议，待确认</small></article>
        <article><span>阶段灌溉定额</span><strong>{{ firstUnit?.irrigation_quota_m3_per_mu?.toLocaleString() ?? '待确认' }}</strong><small>{{ firstUnit?.irrigation_quota_m3_per_mu ? 'm³/亩' : '尚无正式来源' }}</small></article>
        <article class="is-primary"><span>阶段参考需水量</span><strong>{{ result.total_reference_irrigation_demand_m3?.toLocaleString() ?? '暂不计算' }}</strong><small>{{ result.total_reference_irrigation_demand_m3 !== null ? 'm³' : '避免使用演示参数' }}</small></article>
      </div>
      <div class="result-layout">
        <BusinessResultMap v-if="unit" :unit="unit" />
        <div v-else class="map-state">结果关联的管理单元尚未找到。</div>
        <aside class="result-detail">
          <span class="detail-kicker">计算对象</span><h3>{{ firstUnit?.unit_name }}</h3>
          <dl><div><dt>任务编号</dt><dd>{{ result.task_id }}</dd></div><div><dt>面积来源</dt><dd>{{ areaSourceLabel }}</dd></div><div><dt>计算公式</dt><dd>W = A × M</dd></div><div><dt>质量状态</dt><dd>{{ isModelCandidate ? '模型候选待复核' : (result.status === 'completed' ? '计算完成' : '阶段参数待确认') }}</dd></div><div v-if="isModelCandidate"><dt>模型阈值</dt><dd>{{ modelEvidence.threshold ?? '—' }}</dd></div><div v-if="isModelCandidate"><dt>成果版本</dt><dd>{{ modelEvidence.area_statistic_revision ?? result.result_version }}</dd></div></dl>
          <div v-if="result.parameter_basis?.seasonal_quota_source && result.parameter_basis.seasonal_quota_m3_per_mu && result.parameter_basis.seasonal_reference_demand_m3" class="quality-note official-basis"><strong>官方全季基准（不代替阶段定额）</strong><p>{{ result.parameter_basis.seasonal_quota_source }}：P=50%通用值 {{ result.parameter_basis.seasonal_quota_m3_per_mu }} m³/亩，对应当前候选面积的全季参考量 {{ result.parameter_basis.seasonal_reference_demand_m3.toLocaleString() }} m³。</p></div>
          <div v-else-if="result.parameter_basis" class="quality-note official-basis"><strong>参数状态</strong><p>{{ result.parameter_basis.statement }}</p></div>
          <div class="quality-note"><strong>质量说明</strong><p>{{ firstUnit?.quality_statement }}</p></div>
          <div class="result-links"><RouterLink to="/resources">查看空间数据</RouterLink><RouterLink to="/tasks">返回分析任务</RouterLink></div>
        </aside>
      </div>
    </template>
  </section>
</template>
