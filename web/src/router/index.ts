import { createRouter, createWebHistory } from 'vue-router'

import OverviewView from '@/views/OverviewView.vue'
import PlaceholderView from '@/views/PlaceholderView.vue'
import ReferenceAreasView from '@/views/ReferenceAreasView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'overview',
      component: OverviewView,
      meta: { title: '系统总览' },
    },
    {
      path: '/tasks',
      name: 'tasks',
      component: PlaceholderView,
      meta: { title: '分析任务', section: '任务建立中' },
    },
    {
      path: '/resources',
      name: 'resources',
      component: ReferenceAreasView,
      meta: { title: '空间数据' },
    },
    {
      path: '/results',
      name: 'results',
      component: PlaceholderView,
      meta: { title: '成果研判', section: '成果页面建立中' },
    },
  ],
})

export default router
