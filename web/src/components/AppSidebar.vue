<script setup lang="ts">
import { DataAnalysis, Files, MapLocation, Promotion } from '@element-plus/icons-vue'

const navigation = [
  { to: '/', label: '系统总览', icon: DataAnalysis },
  { to: '/tasks', label: '分析任务', icon: Promotion },
  { to: '/resources', label: '业务数据', icon: Files },
  { to: '/results', label: '成果研判', icon: MapLocation },
]
</script>

<template>
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-mark">禾</div>
      <div>
        <strong>禾灌智析</strong>
        <span>OGE RICE</span>
      </div>
    </div>

    <nav aria-label="主导航">
      <router-link v-for="item in navigation" :key="item.to" :to="item.to">
        <el-icon><component :is="item.icon" /></el-icon>
        <span>{{ item.label }}</span>
      </router-link>
    </nav>

    <div class="sidebar-foot">
      <span class="version-chip">V0.1 工程基础</span>
      <p>遥感面积与灌溉参数应用原型</p>
    </div>
  </aside>
</template>
