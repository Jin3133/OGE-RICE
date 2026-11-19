<script setup lang="ts">
import 'ol/ol.css'

import Feature from 'ol/Feature'
import Map from 'ol/Map'
import Point from 'ol/geom/Point'
import ImageLayer from 'ol/layer/Image'
import VectorLayer from 'ol/layer/Vector'
import Projection from 'ol/proj/Projection'
import ImageStatic from 'ol/source/ImageStatic'
import VectorSource from 'ol/source/Vector'
import { Circle, Fill, Stroke, Style, Text } from 'ol/style'
import View from 'ol/View'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

import type { GeoreferencingControlPoint } from '@/types/api'

const props = defineProps<{
  imageUrl: string
  width: number
  height: number
  points: GeoreferencingControlPoint[]
  pendingPixel: { x: number; y: number } | null
}>()
const emit = defineEmits<{ pixel: [value: { x: number; y: number }] }>()

const element = ref<HTMLDivElement | null>(null)
let map: Map | undefined
let imageLayer: ImageLayer<ImageStatic> | undefined
const pointSource = new VectorSource()
const pointLayer = new VectorLayer({
  source: pointSource,
  style: (feature) => new Style({
    image: new Circle({ radius: 9, fill: new Fill({ color: '#d6a84f' }), stroke: new Stroke({ color: '#fff', width: 2 }) }),
    text: new Text({
      text: String(feature.get('label')),
      fill: new Fill({ color: '#10281f' }),
      font: '700 10px sans-serif',
    }),
  }),
})

function extent() {
  return [0, -props.height, props.width, 0]
}

function projection() {
  return new Projection({ code: `PIXELS:${props.width}x${props.height}`, units: 'pixels', extent: extent() })
}

function renderImage() {
  if (!map || !props.imageUrl || !props.width || !props.height) return
  if (imageLayer) map.removeLayer(imageLayer)
  const pixelProjection = projection()
  imageLayer = new ImageLayer({
    source: new ImageStatic({ url: props.imageUrl, projection: pixelProjection, imageExtent: extent() }),
  })
  map.getLayers().insertAt(0, imageLayer)
  map.setView(new View({ projection: pixelProjection, center: [props.width / 2, -props.height / 2], zoom: 1, maxZoom: 8 }))
  map.getView().fit(extent(), { padding: [24, 24, 24, 24] })
}

function renderPoints() {
  pointSource.clear()
  props.points.forEach((point, index) => {
    const feature = new Feature(new Point([point.pixel_x, -point.pixel_y]))
    feature.set('label', index + 1)
    pointSource.addFeature(feature)
  })
  if (props.pendingPixel) {
    const feature = new Feature(new Point([props.pendingPixel.x, -props.pendingPixel.y]))
    feature.set('label', '+')
    pointSource.addFeature(feature)
  }
}

onMounted(() => {
  map = new Map({
    target: element.value!,
    layers: [pointLayer],
    view: new View({ center: [0, 0], zoom: 1 }),
  })
  map.on('singleclick', (event) => {
    const x = Math.max(0, Math.min(props.width, event.coordinate[0]))
    const y = Math.max(0, Math.min(props.height, -event.coordinate[1]))
    emit('pixel', { x: Math.round(x * 100) / 100, y: Math.round(y * 100) / 100 })
  })
  renderImage()
  renderPoints()
})

watch(() => [props.imageUrl, props.width, props.height], renderImage)
watch(() => [props.points, props.pendingPixel], renderPoints, { deep: true })
onBeforeUnmount(() => map?.setTarget(undefined))
</script>

<template>
  <div ref="element" class="georef-map georef-source-map" aria-label="待配准源影像">
    <div class="georef-map-label">源影像 · 像素坐标</div>
    <div class="georef-map-help">滚轮缩放 · 拖拽平移 · 点击选择控制点</div>
  </div>
</template>
