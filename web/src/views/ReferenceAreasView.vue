<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import ReferenceAreaMap from '@/components/ReferenceAreaMap.vue'
import { ApiRequestError, api } from '@/services/api'
import { useTaskDraftStore } from '@/stores/taskDraft'
import type { BusinessResultResponse, ManagementUnitFeature, ManagementUnitType, ReferenceAreaFeatureCollection } from '@/types/api'
import type { AnalysisAreaSelection } from '@/types/map'

const collection = ref<ReferenceAreaFeatureCollection | null>(null)
const router = useRouter()
const taskDraft = useTaskDraftStore()
const loading = ref(true)
const error = ref('')
const selection = ref<AnalysisAreaSelection | null>(null)
const units = ref<ManagementUnitFeature[]>([])
const businessResults = ref<BusinessResultResponse[]>([])
const importing = ref(false)
const importError = ref('')
const importMessage = ref('')
const geometry = ref<ManagementUnitFeature['geometry'] | null>(null)
const geometryFileName = ref('')
const unitForm = reactive({
  name: '',
  unitType: 'irrigation_district' as ManagementUnitType,
  parentKey: '',
  validStart: '2025-01-01',
  validEnd: '2025-12-31',
  sourceTitle: '',
  sourceUrl: '',
  qualityStatement: '',
  status: 'draft' as 'draft' | 'active',
})
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
const availableParents = computed(() => units.value.filter((unit) => {
  if (unitForm.unitType === 'management_zone') return unit.properties.unit_type === 'irrigation_district'
  if (unitForm.unitType === 'custom') return ['irrigation_district', 'management_zone'].includes(unit.properties.unit_type)
  return false
}))
const canImport = computed(() => Boolean(
  unitForm.name.trim().length >= 2
  && geometry.value
  && unitForm.sourceTitle.trim().length >= 2
  && unitForm.qualityStatement.trim().length >= 2
  && unitForm.validStart
  && unitForm.validEnd
  && unitForm.validStart <= unitForm.validEnd
  && (unitForm.unitType === 'irrigation_district' || unitForm.parentKey),
))

function unitTypeLabel(value: ManagementUnitType) {
  return { irrigation_district: '灌区', management_zone: '灌片', custom: '自定义单元' }[value]
}

function readGeometry(event: Event) {
  importError.value = ''
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    try {
      const value = JSON.parse(String(reader.result)) as { type?: string; geometry?: ManagementUnitFeature['geometry']; features?: Array<{ geometry: ManagementUnitFeature['geometry'] }> }
      const candidate = value.type === 'FeatureCollection' ? value.features?.[0]?.geometry : value.type === 'Feature' ? value.geometry : value as ManagementUnitFeature['geometry']
      if (!candidate || !['Polygon', 'MultiPolygon'].includes(candidate.type)) throw new Error('仅支持Polygon或MultiPolygon')
      geometry.value = candidate
      geometryFileName.value = file.name
    } catch (reason) {
      geometry.value = null
      geometryFileName.value = ''
      importError.value = reason instanceof Error ? `GeoJSON无法读取：${reason.message}` : 'GeoJSON无法读取'
    }
  }
  reader.readAsText(file)
}

async function importUnit() {
  if (!canImport.value || !geometry.value) return
  importing.value = true
  importError.value = ''
  importMessage.value = ''
  const parent = units.value.find((unit) => `${unit.properties.unit_id}@${unit.properties.revision}` === unitForm.parentKey)
  try {
    const created = await api.createManagementUnit({
      name: unitForm.name.trim(),
      unit_type: unitForm.unitType,
      valid_start: unitForm.validStart,
      valid_end: unitForm.validEnd,
      parent: parent ? { unit_id: parent.properties.unit_id, revision: parent.properties.revision } : null,
      geometry: geometry.value,
      source_title: unitForm.sourceTitle.trim(),
      source_url: unitForm.sourceUrl.trim() || null,
      quality_status: 'unverified',
      quality_statement: unitForm.qualityStatement.trim(),
      status: unitForm.status,
      changed_by: 'local.operator',
    }, crypto.randomUUID())
    units.value = [created, ...units.value]
    importMessage.value = `${created.properties.name}已保存为第1版`
    unitForm.name = ''
    unitForm.parentKey = ''
    unitForm.sourceTitle = ''
    unitForm.sourceUrl = ''
    unitForm.qualityStatement = ''
    geometry.value = null
    geometryFileName.value = ''
  } catch (reason) {
    importError.value = reason instanceof Error ? reason.message : '管理单元导入失败'
  } finally {
    importing.value = false
  }
}

function configureTask() {
  if (!selection.value) return
  taskDraft.setArea(selection.value)
  router.push('/tasks')
}

function configureUnitTask(unit: ManagementUnitFeature) {
  const unitResult = businessResults.value
    .flatMap((result) => result.units)
    .find((item) => item.unit_id === unit.properties.unit_id)
  taskDraft.setArea({
    method: 'polygon',
    geometry: unit.geometry,
    area_square_metres: unit.properties.area_square_metres,
    source_area_id: null,
    management_unit_id: unit.properties.unit_id,
    management_unit_revision: unit.properties.revision,
    candidate_area_square_metres: unitResult?.candidate_area_m2 ?? null,
  })
  router.push('/tasks')
}

onMounted(async () => {
  try {
    const [areas, managementUnits, results] = await Promise.all([api.referenceAreas(), api.managementUnits(), api.businessResults()])
    collection.value = areas
    units.value = managementUnits.features
    businessResults.value = results.items
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
          <button type="button" :disabled="!selection" @click="configureTask">配置分析任务</button>
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

  <section class="management-unit-panel">
    <div class="map-intro">
      <div>
        <span class="section-tag">VERSIONED BUSINESS DATA</span>
        <h2>管理单元</h2>
        <p>导入真实灌区、灌片或自定义管理边界。每次导入均形成不可变版本及审计记录。</p>
      </div>
      <span class="reference-badge">{{ units.length }} 个管理单元</span>
    </div>

    <div class="management-unit-grid">
      <div class="unit-list-card">
        <h3>已登记边界</h3>
        <p v-if="!units.length" class="history-empty">暂无正式管理单元。江夏区行政边界不会自动转换为灌区。</p>
        <article v-for="unit in units" :key="unit.id" class="unit-list-item">
          <div><strong>{{ unit.properties.name }}</strong><span>{{ unitTypeLabel(unit.properties.unit_type) }} · 第 {{ unit.properties.revision }} 版</span></div>
          <div><em>{{ unit.properties.status === 'active' ? '已启用' : '草稿' }}</em><span>{{ (unit.properties.area_square_metres / 1_000_000).toFixed(2) }} km²</span></div>
          <button type="button" @click="configureUnitTask(unit)">用于分析</button>
        </article>
      </div>

      <form class="unit-import-card" @submit.prevent="importUnit">
        <h3>导入 GeoJSON 边界</h3>
        <label><span>单元名称</span><input v-model.trim="unitForm.name" placeholder="例如：某灌区" /></label>
        <div class="form-grid">
          <label><span>单元类型</span><select v-model="unitForm.unitType" @change="unitForm.parentKey = ''"><option value="irrigation_district">灌区（根节点）</option><option value="management_zone">灌片</option><option value="custom">自定义单元</option></select></label>
          <label v-if="unitForm.unitType !== 'irrigation_district'"><span>父级单元</span><select v-model="unitForm.parentKey"><option value="">请选择</option><option v-for="parent in availableParents" :key="parent.id" :value="`${parent.properties.unit_id}@${parent.properties.revision}`">{{ parent.properties.name }} · v{{ parent.properties.revision }}</option></select></label>
        </div>
        <div class="form-grid"><label><span>有效期开始</span><input v-model="unitForm.validStart" type="date" /></label><label><span>有效期结束</span><input v-model="unitForm.validEnd" type="date" /></label></div>
        <label><span>数据来源</span><input v-model.trim="unitForm.sourceTitle" placeholder="提供单位、文件名或公开来源" /></label>
        <label><span>来源链接（可选）</span><input v-model.trim="unitForm.sourceUrl" placeholder="https://" /></label>
        <label><span>质量说明</span><textarea v-model.trim="unitForm.qualityStatement" rows="3" placeholder="边界年份、精度、是否核验及已知限制" /></label>
        <label class="file-picker"><span>边界文件</span><input type="file" accept=".json,.geojson,application/geo+json,application/json" @change="readGeometry" /><strong>{{ geometryFileName || '尚未选择 GeoJSON' }}</strong></label>
        <label><span>存储状态</span><select v-model="unitForm.status"><option value="draft">草稿（推荐）</option><option value="active">启用</option></select></label>
        <p class="scope-warning">灌片必须直接挂在灌区下；自定义单元可挂在灌区或灌片下，且子级边界不能超出父级范围。</p>
        <button type="submit" :disabled="!canImport || importing">{{ importing ? '正在校验并保存…' : '校验并保存第1版' }}</button>
        <p v-if="importMessage" class="saved-message">{{ importMessage }}</p>
        <p v-if="importError" class="submit-error">{{ importError }}</p>
      </form>
    </div>
  </section>
</template>
