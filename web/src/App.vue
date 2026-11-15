<script setup lang="ts">
import AppSidebar from '@/components/AppSidebar.vue'
import { useSystemStore } from '@/stores/system'

const system = useSystemStore()
system.checkApi()
</script>

<template>
  <div class="app-shell">
    <AppSidebar />
    <main class="workspace">
      <header class="topbar">
        <div>
          <p class="eyebrow">水稻种植监测·分阶段参考需水</p>
          <h1>{{ $route.meta.title }}</h1>
        </div>
        <div class="service-state" :class="`is-${system.apiStatus}`">
          <span class="state-dot" />
          <span>{{ system.statusLabel }}</span>
        </div>
      </header>
      <router-view />
    </main>
  </div>
</template>
