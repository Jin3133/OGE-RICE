<script setup lang="ts">
import 'ol/ol.css'

import Feature from 'ol/Feature'
import GeoJSON from 'ol/format/GeoJSON'
import TileLayer from 'ol/layer/Tile'
import VectorLayer from 'ol/layer/Vector'
import Map from 'ol/Map'
import OSM from 'ol/source/OSM'
import VectorSource from 'ol/source/Vector'
import { Fill, Stroke, Style } from 'ol/style'
import View from 'ol/View'
import { onBeforeUnmount, onMounted, ref } from 'vue'

import type { ManagementUnitFeature } from '@/types/api'

const props = defineProps<{ unit: ManagementUnitFeature }>()
const element = ref<HTMLDivElement | null>(null)
let map: Map | undefined

onMounted(() => {
  const feature = new GeoJSON().readFeature(props.unit, {
    dataProjection: 'EPSG:4326',
    featureProjection: 'EPSG:3857',
  }) as Feature
  const source = new VectorSource({ features: [feature] })
  map = new Map({
    target: element.value!,
    layers: [
      new TileLayer({ source: new OSM() }),
      new VectorLayer({
        source,
        style: new Style({
          fill: new Fill({ color: 'rgba(55, 119, 82, .20)' }),
          stroke: new Stroke({ color: '#2f7654', width: 3 }),
        }),
      }),
    ],
    view: new View({ center: [0, 0], zoom: 2 }),
  })
  const geometry = feature.getGeometry()
  if (geometry) {
    map.getView().fit(geometry.getExtent(), { padding: [42, 42, 42, 42], maxZoom: 13 })
  }
})

onBeforeUnmount(() => map?.setTarget(undefined))
</script>

<template>
  <div ref="element" class="business-result-map" aria-label="业务成果空间范围">
    <div class="map-caption">{{ unit.properties.name }} · 第 {{ unit.properties.revision }} 版边界</div>
  </div>
</template>
