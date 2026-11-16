<script setup lang="ts">
import 'ol/ol.css'

import { defaults as defaultControls, FullScreen, MousePosition, ScaleLine, ZoomSlider } from 'ol/control'
import { createStringXY } from 'ol/coordinate'
import GeoJSON from 'ol/format/GeoJSON'
import Draw, { createBox } from 'ol/interaction/Draw'
import Map from 'ol/Map'
import { getArea } from 'ol/sphere'
import View from 'ol/View'
import TileLayer from 'ol/layer/Tile'
import VectorLayer from 'ol/layer/Vector'
import OSM from 'ol/source/OSM'
import VectorSource from 'ol/source/Vector'
import { Fill, Stroke, Style } from 'ol/style'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

import type { ReferenceAreaFeatureCollection } from '@/types/api'
import type { AnalysisAreaMethod, AnalysisAreaSelection } from '@/types/map'

const props = defineProps<{ collection: ReferenceAreaFeatureCollection | null }>()
const emit = defineEmits<{ selection: [value: AnalysisAreaSelection | null] }>()

const mapElement = ref<HTMLDivElement | null>(null)
const coordinateElement = ref<HTMLDivElement | null>(null)
const boundaryVisible = ref(true)
const basemapVisible = ref(true)
const activeDrawing = ref<AnalysisAreaMethod | null>(null)
let map: Map | undefined
let drawInteraction: Draw | undefined
const areaSource = new VectorSource()
const selectionSource = new VectorSource()
const basemapLayer = new TileLayer({ source: new OSM() })
const boundaryLayer = new VectorLayer({
  source: areaSource,
  style: new Style({
    fill: new Fill({ color: 'rgba(214, 168, 79, 0.18)' }),
    stroke: new Stroke({ color: '#d09b35', width: 3 }),
  }),
})
const selectionLayer = new VectorLayer({
  source: selectionSource,
  style: new Style({
    fill: new Fill({ color: 'rgba(47, 123, 173, 0.20)' }),
    stroke: new Stroke({ color: '#267ca8', width: 3, lineDash: [8, 5] }),
  }),
})

function publishSelection(method: AnalysisAreaMethod, feature: import('ol/Feature').default) {
  const geometry = feature.getGeometry()
  if (!geometry) return
  const wgs84Geometry = geometry.clone().transform('EPSG:3857', 'EPSG:4326')
  const geojson = new GeoJSON().writeGeometryObject(wgs84Geometry) as AnalysisAreaSelection['geometry']
  emit('selection', {
    method,
    geometry: geojson,
    area_square_metres:
      method === 'reference_area' && props.collection?.features[0]
        ? props.collection.features[0].properties.area_square_metres
        : Math.round(getArea(geometry, { projection: 'EPSG:3857' })),
    source_area_id: method === 'reference_area' ? (props.collection?.features[0]?.properties.area_id ?? null) : null,
  })
}

function renderAreas(collection: ReferenceAreaFeatureCollection | null) {
  areaSource.clear()
  if (!collection?.features.length) return
  const features = new GeoJSON().readFeatures(collection, {
    dataProjection: 'EPSG:4326',
    featureProjection: 'EPSG:3857',
  })
  areaSource.addFeatures(features)
  map?.getView().fit(areaSource.getExtent()!, {
    padding: [54, 54, 54, 54],
    duration: 450,
    maxZoom: 11,
  })
}

function fitReferenceArea() {
  if (!map || areaSource.isEmpty()) return
  map.getView().fit(areaSource.getExtent()!, {
    padding: [54, 54, 54, 54],
    duration: 350,
    maxZoom: 11,
  })
}

function toggleBoundary() {
  boundaryVisible.value = !boundaryVisible.value
  boundaryLayer.setVisible(boundaryVisible.value)
}

function toggleBasemap() {
  basemapVisible.value = !basemapVisible.value
  basemapLayer.setVisible(basemapVisible.value)
}

function stopDrawing() {
  if (map && drawInteraction) map.removeInteraction(drawInteraction)
  drawInteraction = undefined
  activeDrawing.value = null
}

function selectReferenceArea() {
  stopDrawing()
  const reference = areaSource.getFeatures()[0]
  if (!reference) return
  const selected = reference.clone()
  selectionSource.clear()
  selectionSource.addFeature(selected)
  publishSelection('reference_area', selected)
  fitReferenceArea()
}

function startDrawing(method: 'rectangle' | 'polygon') {
  if (!map) return
  stopDrawing()
  selectionSource.clear()
  emit('selection', null)
  activeDrawing.value = method
  drawInteraction = new Draw({
    source: selectionSource,
    type: 'Polygon',
    geometryFunction: method === 'rectangle' ? createBox() : undefined,
  })
  drawInteraction.on('drawend', (event) => {
    publishSelection(method, event.feature)
    stopDrawing()
  })
  map.addInteraction(drawInteraction)
}

function clearSelection() {
  stopDrawing()
  selectionSource.clear()
  emit('selection', null)
}

onMounted(() => {
  map = new Map({
    target: mapElement.value!,
    layers: [basemapLayer, boundaryLayer, selectionLayer],
    view: new View({ center: [0, 0], zoom: 2 }),
    controls: defaultControls({ rotate: false }).extend([
      new ZoomSlider(),
      new ScaleLine({ units: 'metric', bar: true, steps: 4, text: true }),
      new FullScreen(),
      new MousePosition({
        coordinateFormat: createStringXY(5),
        projection: 'EPSG:4326',
        target: coordinateElement.value!,
        placeholder: '经纬度 —',
      }),
    ]),
  })
  renderAreas(props.collection)
})

watch(() => props.collection, renderAreas, { deep: true })
onBeforeUnmount(() => map?.setTarget(undefined))
</script>

<template>
  <div ref="mapElement" class="reference-map" aria-label="江夏区真实地图参考范围">
    <div class="map-toolbar" aria-label="地图工具">
      <button type="button" title="缩放至参考区域" @click="fitReferenceArea">⌖<span>适配范围</span></button>
      <button type="button" :class="{ 'is-muted': !basemapVisible }" @click="toggleBasemap">▦<span>街道底图</span></button>
      <button type="button" :class="{ 'is-muted': !boundaryVisible }" @click="toggleBoundary">◇<span>参考边界</span></button>
    </div>
    <div class="analysis-toolbar" aria-label="分析范围工具">
      <span>分析范围</span>
      <button type="button" @click="selectReferenceArea">采用江夏区</button>
      <button type="button" :class="{ 'is-active': activeDrawing === 'rectangle' }" @click="startDrawing('rectangle')">矩形框选</button>
      <button type="button" :class="{ 'is-active': activeDrawing === 'polygon' }" @click="startDrawing('polygon')">多边形</button>
      <button type="button" class="is-light" @click="clearSelection">清除</button>
    </div>
    <div ref="coordinateElement" class="map-coordinate" />
    <div class="map-help">滚轮缩放 · 拖拽平移 · 双击放大<span v-if="activeDrawing"> · 正在绘制，双击结束</span></div>
  </div>
</template>
