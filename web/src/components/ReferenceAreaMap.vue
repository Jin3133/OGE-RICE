<script setup lang="ts">
import 'ol/ol.css'

import { defaults as defaultControls, FullScreen, MousePosition, ScaleLine, ZoomSlider } from 'ol/control'
import { createStringXY } from 'ol/coordinate'
import GeoJSON from 'ol/format/GeoJSON'
import Map from 'ol/Map'
import View from 'ol/View'
import TileLayer from 'ol/layer/Tile'
import VectorLayer from 'ol/layer/Vector'
import OSM from 'ol/source/OSM'
import VectorSource from 'ol/source/Vector'
import { Fill, Stroke, Style } from 'ol/style'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

import type { ReferenceAreaFeatureCollection } from '@/types/api'

const props = defineProps<{ collection: ReferenceAreaFeatureCollection | null }>()

const mapElement = ref<HTMLDivElement | null>(null)
const coordinateElement = ref<HTMLDivElement | null>(null)
const boundaryVisible = ref(true)
const basemapVisible = ref(true)
let map: Map | undefined
const areaSource = new VectorSource()
const basemapLayer = new TileLayer({ source: new OSM() })
const boundaryLayer = new VectorLayer({
  source: areaSource,
  style: new Style({
    fill: new Fill({ color: 'rgba(214, 168, 79, 0.18)' }),
    stroke: new Stroke({ color: '#d09b35', width: 3 }),
  }),
})

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

onMounted(() => {
  map = new Map({
    target: mapElement.value!,
    layers: [basemapLayer, boundaryLayer],
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
    <div ref="coordinateElement" class="map-coordinate" />
    <div class="map-help">滚轮缩放 · 拖拽平移 · 双击放大</div>
  </div>
</template>
