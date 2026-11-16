<script setup lang="ts">
import 'ol/ol.css'

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
let map: Map | undefined
const areaSource = new VectorSource()

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

onMounted(() => {
  map = new Map({
    target: mapElement.value!,
    layers: [
      new TileLayer({ source: new OSM() }),
      new VectorLayer({
        source: areaSource,
        style: new Style({
          fill: new Fill({ color: 'rgba(214, 168, 79, 0.18)' }),
          stroke: new Stroke({ color: '#d09b35', width: 3 }),
        }),
      }),
    ],
    view: new View({ center: [0, 0], zoom: 2 }),
    controls: [],
  })
  renderAreas(props.collection)
})

watch(() => props.collection, renderAreas, { deep: true })
onBeforeUnmount(() => map?.setTarget(undefined))
</script>

<template>
  <div ref="mapElement" class="reference-map" aria-label="江夏区真实地图参考范围" />
</template>
