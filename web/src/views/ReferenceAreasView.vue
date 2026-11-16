<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import ReferenceAreaMap from '@/components/ReferenceAreaMap.vue'
import { ApiRequestError, api } from '@/services/api'
import type { ReferenceAreaFeatureCollection } from '@/types/api'
import type { AnalysisAreaSelection } from '@/types/map'

const collection = ref<ReferenceAreaFeatureCollection | null>(null)
const loading = ref(true)
const error = ref('')
const selection = ref<AnalysisAreaSelection | null>(null)
const area = computed(() => collection.value?.features[0]?.properties)
const selectionMethod = computed(() => {
  const labels = { reference_area: '采用参考区域', rectangle: '矩形框选', polygon: '多边形绘制' }
  return selection.value ? labels[selection.value.method] : '尚未选择'
})
const selectionArea = computed(() => {
  if (!selection.value) return '—'
  const squareKilometres = selection.value.area_square_metres / 1_000_000
  const prefix = selection.value.method === 'reference_area' ? '' : '约 '
  return squareKilometres >= 1
    ? `${prefix}${squareKilometres.toFixed(2)} km²`
    : `${prefix}${(selection.value.area_square_metres / 10_000).toFixed(2)} 公顷`
})

onMounted(async () => {
  try {
    collection.value = await api.referenceAreas()
  } catch (reason) {
    error.value = reason instanceof ApiRequestError ? reason.message : '地图数据加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <section class="reference-area-page">
    <div class="map-intro">
      <div>
        <span class="section-tag">REAL GEOSPATIAL DATA</span>
        <h2>真实地图参考范围</h2>
        <p>底图来自 OpenStreetMap，边界由业务后台从 PostGIS 实时读取。当前用于建立第一条可复现的空间分析链路。</p>
      </div>
      <span class="reference-badge">参考范围 · 非灌区边界</span>
    </div>

    <div v-if="loading" class="map-state">正在读取空间数据…</div>
    <div v-else-if="error" class="map-state is-error">{{ error }}</div>
    <div v-else-if="!area" class="map-state">尚未配置参考区域</div>
    <div v-else class="map-layout">
      <div class="map-frame">
        <ReferenceAreaMap :collection="collection" @selection="selection = $event" />
        <div class="map-caption">真实底图 · WGS 84 边界 · PostGIS 数据源</div>
      </div>
      <aside class="area-detail">
        <span class="detail-kicker">当前参考区域</span>
        <h3>{{ area.name }}</h3>
        <dl>
          <div><dt>行政区代码</dt><dd>{{ area.administrative_code }}</dd></div>
          <div><dt>数据类型</dt><dd>行政区参考边界</dd></div>
          <div><dt>数据版本</dt><dd>第 {{ area.revision }} 版</dd></div>
          <div><dt>数据来源</dt><dd>{{ area.source_title }}</dd></div>
        </dl>
        <div class="selection-summary" :class="{ 'has-selection': selection }">
          <div>
            <span>任务分析范围</span>
            <strong>{{ selectionMethod }}</strong>
          </div>
          <div>
            <span>测算面积</span>
            <strong>{{ selectionArea }}</strong>
          </div>
          <p v-if="selection">已生成标准 WGS 84 GeoJSON，确认任务参数后方可提交保存。</p>
          <p v-else>请在地图工具中采用江夏区，或绘制一个自定义分析范围。</p>
        </div>
        <div class="scope-warning">
          <strong>使用边界</strong>
          <p>该边界仅用于试验范围定位和地图展示，不代表灌区边界、灌片边界或实际供水服务范围。</p>
        </div>
        <div class="quality-note">
          <strong>质量记录</strong>
          <p>{{ area.quality_statement }}</p>
        </div>
        <a v-if="area.source_url" :href="area.source_url" target="_blank" rel="noreferrer">查看公开数据来源 ↗</a>
      </aside>
    </div>
  </section>
</template>
