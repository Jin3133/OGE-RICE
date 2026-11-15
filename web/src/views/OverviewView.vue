<script setup lang="ts">
import { Connection, DataLine, MapLocation } from '@element-plus/icons-vue'

const capabilities = [
  {
    icon: MapLocation,
    title: '管理单元',
    value: '版本化边界',
    description: '灌区、灌片与自定义单元统一管理',
  },
  {
    icon: DataLine,
    title: '阶段需水',
    value: 'W = A × M',
    description: '面积版本与分阶段定额明确关联',
  },
  {
    icon: Connection,
    title: '数据底座',
    value: 'PostGIS',
    description: '空间边界、版本引用与审计可追溯',
  },
]
</script>

<template>
  <section class="overview">
    <div class="hero-panel">
      <div class="hero-copy">
        <span class="section-tag">工程基础已建立</span>
        <h2>从遥感候选区面积<br />到分阶段参考需水</h2>
        <p>
          将管理单元、面积统计版本与灌溉定额组织为可查询、可复算的业务链路，
          为后续任务配置、地图研判和反馈修正提供统一底座。
        </p>
        <div class="hero-actions">
          <router-link class="primary-action" to="/tasks">创建分析任务</router-link>
          <router-link class="secondary-action" to="/resources">查看业务数据</router-link>
        </div>
      </div>
      <div class="hero-visual" aria-hidden="true">
        <div class="field field-a" />
        <div class="field field-b" />
        <div class="field field-c" />
        <div class="water-line" />
        <div class="metric-float">
          <span>当前主线</span>
          <strong>面积 × 阶段定额</strong>
        </div>
      </div>
    </div>

    <div class="capability-grid">
      <article v-for="item in capabilities" :key="item.title" class="capability-card">
        <div class="capability-icon"><el-icon><component :is="item.icon" /></el-icon></div>
        <div>
          <span>{{ item.title }}</span>
          <strong>{{ item.value }}</strong>
          <p>{{ item.description }}</p>
        </div>
      </article>
    </div>

    <section class="next-step-panel">
      <div>
        <span class="section-tag">下一条真实链路</span>
        <h3>管理单元地图与参考需水试算</h3>
      </div>
      <ol>
        <li><span>01</span>选择明确版本的管理单元</li>
        <li><span>02</span>读取遥感面积与阶段定额</li>
        <li><span>03</span>输出可追溯的参考需水结果</li>
      </ol>
    </section>
  </section>
</template>
