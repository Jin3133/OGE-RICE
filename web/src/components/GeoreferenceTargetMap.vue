<script setup lang="ts">
import 'ol/ol.css'

import Feature from 'ol/Feature'
import GeoJSON from 'ol/format/GeoJSON'
import Point from 'ol/geom/Point'
import TileLayer from 'ol/layer/Tile'
import VectorLayer from 'ol/layer/Vector'
import Map from 'ol/Map'
import { fromLonLat } from 'ol/proj'
import OSM from 'ol/source/OSM'
import VectorSource from 'ol/source/Vector'
import XYZ from 'ol/source/XYZ'
import { Circle, Fill, Stroke, Style, Text } from 'ol/style'
import View from 'ol/View'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

import type { GeoreferencingControlPoint, PixelBoundaryGeometry } from '@/types/api'

const props = defineProps<{
  points: GeoreferencingControlPoint[]
  boundary: PixelBoundaryGeometry | null
  awaitingTarget: boolean
}>()
const emit = defineEmits<{ target: [value: { longitude: number; latitude: number }] }>()

const element = ref<HTMLDivElement | null>(null)
const satelliteVisible = ref(true)
let map: Map | undefined
const pointSource = new VectorSource()
const boundarySource = new VectorSource()
const streetLayer = new TileLayer({ source: new OSM(), visible: false })
const satelliteLayer = new TileLayer({
  source: new XYZ({
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attributions: 'Tiles © Esri',
    crossOrigin: 'anonymous',
  }),
})
const boundaryLayer = new VectorLayer({
  source: boundarySource,
  style: new Style({ fill: new Fill({ color: 'rgba(214,168,79,.14)' }), stroke: new Stroke({ color: '#f1c45f', width: 3 }) }),
})
const pointLayer = new VectorLayer({
  source: pointSource,
  style: (feature) => new Style({
    image: new Circle({ radius: 9, fill: new Fill({ color: '#267ca8' }), stroke: new Stroke({ color: '#fff', width: 2 }) }),
    text: new Text({ text: String(feature.get('label')), fill: new Fill({ color: '#fff' }), font: '700 10px sans-serif' }),
  }),
})

function renderPoints() {
  pointSource.clear()
  props.points.forEach((point, index) => {
    const feature = new Feature(new Point(fromLonLat([point.longitude, point.latitude])))
    feature.set('label', index + 1)
    pointSource.addFeature(feature)
  })
}

function renderBoundary() {
  boundarySource.clear()
  if (!props.boundary) return
  const feature = new GeoJSON().readFeature(
    { type: 'Feature', geometry: props.boundary, properties: {} },
    { dataProjection: 'EPSG:4326', featureProjection: 'EPSG:3857' },
  ) as Feature
  boundarySource.addFeature(feature)
  map?.getView().fit(feature.getGeometry()!.getExtent(), { padding: [40, 40, 40, 40], maxZoom: 15, duration: 350 })
}

function toggleBasemap() {
  satelliteVisible.value = !satelliteVisible.value
  satelliteLayer.setVisible(satelliteVisible.value)
  streetLayer.setVisible(!satelliteVisible.value)
}

onMounted(() => {
  map = new Map({
    target: element.value!,
    layers: [streetLayer, satelliteLayer, boundaryLayer, pointLayer],
    view: new View({ center: fromLonLat([121.431389, 31.937222]), zoom: 13 }),
  })
  map.on('singleclick', (event) => {
    if (!props.awaitingTarget) return
    const [longitude, latitude] = event.coordinate
    const coordinate = new Point([longitude, latitude]).transform('EPSG:3857', 'EPSG:4326').getCoordinates()
    emit('target', { longitude: coordinate[0], latitude: coordinate[1] })
  })
  renderPoints()
  renderBoundary()
})

watch(() => props.points, renderPoints, { deep: true })
watch(() => props.boundary, renderBoundary, { deep: true })
onBeforeUnmount(() => map?.setTarget(undefined))
</script>

<template>
  <div ref="element" class="georef-map georef-target-map" :class="{ 'is-awaiting': awaitingTarget }" aria-label="控制点目标地图">
    <div class="georef-map-label">目标地图 · WGS 84</div>
    <button class="georef-basemap-toggle" type="button" @click="toggleBasemap">{{ satelliteVisible ? '切换街道图' : '切换卫星图' }}</button>
    <div class="georef-map-help">{{ awaitingTarget ? '请点击与源影像相同的地物位置' : '先在左侧源影像选择控制点' }}</div>
  </div>
</template>
