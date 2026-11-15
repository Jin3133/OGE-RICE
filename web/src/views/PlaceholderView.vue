<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const section = computed(() => route.meta.section as string)
</script>

<template>
  <section class="placeholder-panel">
    <span class="section-tag">按业务链路逐步实现</span>
    <h2>{{ section }}</h2>
    <p>此页将在对应后端契约完成后接入真实数据，不使用难以替换的静态假接口。</p>
  </section>
</template>
