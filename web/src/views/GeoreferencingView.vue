<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import GeoreferenceSourceMap from '@/components/GeoreferenceSourceMap.vue'
import GeoreferenceTargetMap from '@/components/GeoreferenceTargetMap.vue'
import { api } from '@/services/api'
import { loadGeoreferencingImage, saveGeoreferencingImage } from '@/services/localImageCache'
import type {
  GeoreferencingControlPoint,
  GeoreferencingFitResponse,
  PixelBoundaryGeometry,
} from '@/types/api'

const STORAGE_KEY = 'oge-rice:georeferencing-session:v1'
const imageUrl = ref('')
const imageName = ref('')
const imageWidth = ref(0)
const imageHeight = ref(0)
const boundaryName = ref('')
const pixelBoundary = ref<PixelBoundaryGeometry | null>(null)
const points = ref<GeoreferencingControlPoint[]>([])
const pendingPixel = ref<{ x: number; y: number } | null>(null)
const result = ref<GeoreferencingFitResponse | null>(null)
const fitting = ref(false)
const error = ref('')
const sourceFile = ref<File | null>(null)
const targetExtent = ref<[number, number, number, number] | null>(null)
const candidatePointIds = ref<string[]>([])
const suggesting = ref(false)
const suggestionSummary = ref('')

const canFit = computed(() => points.value.length >= 3 && candidatePointIds.value.length === 0 && imageWidth.value > 0 && imageHeight.value > 0)
const statusText = computed(() => {
  if (!imageUrl.value) return '请先选择源影像'
  if (pendingPixel.value) return '源点已选，请在右侧地图选择同一位置'
  if (points.value.length < 3) return `还需至少 ${3 - points.value.length} 组控制点`
  return '已满足拟合条件，建议继续补充至 6–10 组'
})

function displayImage(file: File, preserveResult = false) {
  sourceFile.value = file
  if (imageUrl.value) URL.revokeObjectURL(imageUrl.value)
  const url = URL.createObjectURL(file)
  const image = new Image()
  image.onload = () => {
    imageUrl.value = url
    imageName.value = file.name
    imageWidth.value = image.naturalWidth
    imageHeight.value = image.naturalHeight
    pendingPixel.value = null
    if (!preserveResult) result.value = null
    if (points.value.some((point) => point.pixel_x > image.naturalWidth || point.pixel_y > image.naturalHeight)) {
      points.value = []
      result.value = null
    }
  }
  image.onerror = () => {
    URL.revokeObjectURL(url)
    error.value = '影像无法读取，请选择 PNG、JPG 或浏览器支持的图像。'
  }
  image.src = url
}

async function readImage(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  error.value = ''
  displayImage(file)
  try {
    await saveGeoreferencingImage(file)
  } catch {
    error.value = '影像已加载，但浏览器本地缓存写入失败；刷新后需要重新选择。'
  }
}

function readBoundary(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  error.value = ''
  const reader = new FileReader()
  reader.onload = () => {
    try {
      const document = JSON.parse(String(reader.result)) as {
        type?: string
        geometry?: PixelBoundaryGeometry
        features?: Array<{ geometry: PixelBoundaryGeometry }>
        coordinates?: PixelBoundaryGeometry['coordinates']
      }
      const geometry = document.type === 'FeatureCollection'
        ? document.features?.[0]?.geometry
        : document.type === 'Feature'
          ? document.geometry
          : document as PixelBoundaryGeometry
      if (!geometry || !['Polygon', 'MultiPolygon'].includes(geometry.type)) throw new Error('仅支持 Polygon 或 MultiPolygon')
      pixelBoundary.value = geometry
      boundaryName.value = file.name
      result.value = null
    } catch (reason) {
      error.value = reason instanceof Error ? `像素边界读取失败：${reason.message}` : '像素边界读取失败'
    }
  }
  reader.readAsText(file)
}

function readControlPoints(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  error.value = ''
  const reader = new FileReader()
  reader.onload = () => {
    try {
      const document = JSON.parse(String(reader.result)) as {
        points?: GeoreferencingControlPoint[]
        control_points?: GeoreferencingControlPoint[]
      }
      const imported = document.points ?? document.control_points
      if (!Array.isArray(imported) || imported.length < 3) throw new Error('至少需要 3 组控制点')
      const valid = imported.every((point) =>
        point.point_id
        && Number.isFinite(point.pixel_x)
        && Number.isFinite(point.pixel_y)
        && Number.isFinite(point.longitude)
        && Number.isFinite(point.latitude)
        && point.pixel_x >= 0
        && point.pixel_y >= 0
        && (!imageWidth.value || point.pixel_x <= imageWidth.value)
        && (!imageHeight.value || point.pixel_y <= imageHeight.value),
      )
      if (!valid) throw new Error('控制点字段不完整或超出当前影像范围')
      points.value = imported.map((point) => ({
        point_id: point.point_id,
        pixel_x: Number(point.pixel_x),
        pixel_y: Number(point.pixel_y),
        longitude: Number(point.longitude),
        latitude: Number(point.latitude),
      }))
      candidatePointIds.value = points.value.map((point) => point.point_id)
      pendingPixel.value = null
      result.value = null
    } catch (reason) {
      error.value = reason instanceof Error ? `控制点读取失败：${reason.message}` : '控制点读取失败'
    }
  }
  reader.readAsText(file)
}

function selectPixel(value: { x: number; y: number }) {
  pendingPixel.value = value
  result.value = null
}

function selectTarget(value: { longitude: number; latitude: number }) {
  if (!pendingPixel.value) return
  const duplicate = points.value.some((point) =>
    (Math.abs(point.pixel_x - pendingPixel.value!.x) < 0.01
      && Math.abs(point.pixel_y - pendingPixel.value!.y) < 0.01)
    || (Math.abs(point.longitude - value.longitude) < 1e-8
      && Math.abs(point.latitude - value.latitude) < 1e-8),
  )
  if (duplicate) {
    error.value = '该源点或目标点已存在，请选择新的控制点位置。'
    pendingPixel.value = null
    return
  }
  points.value.push({
    point_id: crypto.randomUUID(),
    pixel_x: pendingPixel.value.x,
    pixel_y: pendingPixel.value.y,
    longitude: value.longitude,
    latitude: value.latitude,
  })
  pendingPixel.value = null
  result.value = null
  error.value = ''
}

function removePoint(index: number) {
  candidatePointIds.value = candidatePointIds.value.filter((id) => id !== points.value[index]?.point_id)
  points.value.splice(index, 1)
  result.value = null
}

function clearPoints() {
  points.value = []
  pendingPixel.value = null
  result.value = null
  candidatePointIds.value = []
}

function confirmCandidate(pointId: string) {
  candidatePointIds.value = candidatePointIds.value.filter((id) => id !== pointId)
  result.value = null
}

function confirmAllCandidates() {
  candidatePointIds.value = []
  result.value = null
}

async function suggestPoints() {
  if (!sourceFile.value || !targetExtent.value) return
  if (points.value.length && !window.confirm('自动推荐将替换当前控制点，是否继续？')) return
  suggesting.value = true
  error.value = ''
  suggestionSummary.value = ''
  try {
    const response = await api.suggestGeoreferencing(sourceFile.value, targetExtent.value)
    points.value = response.points.map(({ match_distance: _distance, ...point }) => point)
    candidatePointIds.value = points.value.map((point) => point.point_id)
    pendingPixel.value = null
    result.value = null
    suggestionSummary.value = `检出 ${response.detected_matches} 组初始匹配，RANSAC 保留 ${response.ransac_inliers} 组，推荐 ${response.points.length} 个待确认点。`
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '自动推荐失败'
  } finally {
    suggesting.value = false
  }
}

async function fit() {
  if (!canFit.value) return
  fitting.value = true
  error.value = ''
  try {
    result.value = await api.fitGeoreferencing({
      image_id: imageName.value || 'local-image',
      image_width: imageWidth.value,
      image_height: imageHeight.value,
      projected_crs: 'EPSG:32651',
      control_points: points.value,
      pixel_boundary: pixelBoundary.value,
    })
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '配准计算失败'
  } finally {
    fitting.value = false
  }
}

function exportSession() {
  const payload = {
    format: 'oge-rice-georeferencing-session-v1',
    image: { name: imageName.value, width: imageWidth.value, height: imageHeight.value },
    boundary_name: boundaryName.value,
    pixel_boundary: pixelBoundary.value,
    control_points: points.value,
    result: result.value,
    saved_at: new Date().toISOString(),
  }
  const anchor = document.createElement('a')
  anchor.href = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' }))
  anchor.download = `${imageName.value || 'georeferencing'}.session.json`
  anchor.click()
  URL.revokeObjectURL(anchor.href)
}

watch([imageName, imageWidth, imageHeight, boundaryName, pixelBoundary, points, candidatePointIds, result], () => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({
    imageName: imageName.value,
    imageWidth: imageWidth.value,
    imageHeight: imageHeight.value,
    boundaryName: boundaryName.value,
    pixelBoundary: pixelBoundary.value,
    points: points.value,
    candidatePointIds: candidatePointIds.value,
    result: result.value,
  }))
}, { deep: true })

onMounted(async () => {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null')
    if (!saved) return
    imageName.value = saved.imageName || ''
    imageWidth.value = Number(saved.imageWidth) || 0
    imageHeight.value = Number(saved.imageHeight) || 0
    boundaryName.value = saved.boundaryName || ''
    pixelBoundary.value = saved.pixelBoundary || null
    points.value = Array.isArray(saved.points) ? saved.points : []
    candidatePointIds.value = Array.isArray(saved.candidatePointIds) ? saved.candidatePointIds : []
    result.value = saved.result || null
  } catch {
    localStorage.removeItem(STORAGE_KEY)
  }
  try {
    const cachedImage = await loadGeoreferencingImage()
    if (cachedImage) displayImage(cachedImage, true)
  } catch {
    // Metadata and control points remain usable even if IndexedDB is unavailable.
  }
})

onBeforeUnmount(() => {
  if (imageUrl.value) URL.revokeObjectURL(imageUrl.value)
})
</script>

<template>
  <section class="georef-page">
    <div class="map-intro">
      <div>
        <span class="section-tag">CONTROL POINT GEOREFERENCING</span>
        <h2>无坐标影像配准工作台</h2>
        <p>在源影像与卫星地图中依次选择同一稳定地物，使用投影坐标进行仿射最小二乘拟合。结果先作为未核验草稿，不直接写入正式管理单元。</p>
      </div>
      <span class="reference-badge">仿射模型 · EPSG:32651</span>
    </div>

    <div class="georef-asset-bar">
      <label class="georef-file"><span>① 选择源影像</span><input type="file" accept="image/png,image/jpeg,image/webp" @change="readImage" /><strong>{{ imageName || '尚未选择' }}</strong></label>
      <label class="georef-file"><span>② 选择像素边界（可选）</span><input type="file" accept=".json,.geojson,application/json" @change="readBoundary" /><strong>{{ boundaryName || '可稍后添加' }}</strong></label>
      <div class="georef-status"><span>当前状态</span><strong>{{ statusText }}</strong><small v-if="imageWidth">{{ imageWidth }} × {{ imageHeight }} px</small></div>
    </div>

    <div v-if="imageUrl" class="georef-dual-view">
      <GeoreferenceSourceMap
        :image-url="imageUrl"
        :width="imageWidth"
        :height="imageHeight"
        :points="points"
        :pending-pixel="pendingPixel"
        @pixel="selectPixel"
      />
      <GeoreferenceTargetMap
        :points="points"
        :boundary="result?.boundary?.geometry || null"
        :awaiting-target="Boolean(pendingPixel)"
        @target="selectTarget"
        @extent="targetExtent = $event"
      />
    </div>
    <div v-else class="georef-empty">选择源影像后将在此显示双视图。影像仅在本机浏览器中读取，不上传至后台。</div>

    <div class="georef-bottom-grid">
      <section class="gcp-panel">
        <div class="panel-heading"><div><span class="section-tag">GROUND CONTROL POINTS</span><h3>控制点对</h3></div><div class="gcp-heading-actions"><button type="button" :disabled="!sourceFile || !targetExtent || suggesting" @click="suggestPoints">{{ suggesting ? '正在匹配…' : '自动推荐' }}</button><button v-if="candidatePointIds.length" type="button" @click="confirmAllCandidates">全部确认</button><label>导入候选<input type="file" accept=".json,application/json" @change="readControlPoints" /></label><button type="button" :disabled="!points.length" @click="clearPoints">清空</button></div></div>
        <p v-if="suggestionSummary" class="gcp-suggestion-note">{{ suggestionSummary }} 候选点不会自动进入正式拟合，请逐点核对或点击“全部确认”。</p>
        <div v-if="!points.length" class="history-empty">尚无控制点。请先点击左侧源影像，再点击右侧地图中的同一地物。</div>
        <div v-else class="gcp-table-wrap">
          <table class="gcp-table"><thead><tr><th>#</th><th>像素 X / Y</th><th>经度 / 纬度</th><th>误差</th><th></th></tr></thead><tbody>
            <tr v-for="(point, index) in points" :key="point.point_id">
              <td><b>{{ index + 1 }}</b><small v-if="candidatePointIds.includes(point.point_id)" class="candidate-badge">候选</small></td>
              <td>{{ point.pixel_x.toFixed(1) }} / {{ point.pixel_y.toFixed(1) }}</td>
              <td>{{ point.longitude.toFixed(6) }} / {{ point.latitude.toFixed(6) }}</td>
              <td>{{ result ? `${result.report.residuals[index]?.error_metres.toFixed(2) ?? '—'} m` : '待计算' }}</td>
              <td><button v-if="candidatePointIds.includes(point.point_id)" type="button" @click="confirmCandidate(point.point_id)">确认</button><button type="button" @click="removePoint(index)">删除</button></td>
            </tr>
          </tbody></table>
        </div>
      </section>

      <aside class="georef-report">
        <span class="section-tag">QUALITY REPORT</span><h3>拟合与质量报告</h3>
        <template v-if="result">
          <div class="report-metrics"><div><span>RMSE</span><strong>{{ result.report.rmse_metres.toFixed(2) }} m</strong></div><div><span>最大误差</span><strong>{{ result.report.maximum_error_metres.toFixed(2) }} m</strong></div><div><span>有效点</span><strong>{{ result.report.control_point_count }}</strong></div><div><span>边界状态</span><strong>未核验</strong></div></div>
          <p>结果已转换为 WGS 84 草稿边界。仍需检查控制点分布和卫星图叠加效果，不能仅凭 RMSE 自动认定为正式灌区边界。</p>
        </template>
        <p v-else>至少录入 3 组不共线且已确认的控制点后可以计算；实际建议使用 6–10 组，覆盖图像四角、中心和明显转折区域。</p>
        <button type="button" :disabled="!canFit || fitting" @click="fit">{{ fitting ? '正在计算…' : '计算仿射配准' }}</button>
        <button class="is-secondary" type="button" :disabled="!points.length" @click="exportSession">导出配准会话</button>
        <p v-if="error" class="submit-error">{{ error }}</p>
      </aside>
    </div>
  </section>
</template>
