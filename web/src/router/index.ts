import { createRouter, createWebHistory } from 'vue-router'

import OverviewView from '@/views/OverviewView.vue'
import ReferenceAreasView from '@/views/ReferenceAreasView.vue'
import GeoreferencingView from '@/views/GeoreferencingView.vue'
import TasksView from '@/views/TasksView.vue'
import ResultsView from '@/views/ResultsView.vue'

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
      component: TasksView,
      meta: { title: '分析任务' },
    },
    {
      path: '/resources',
      name: 'resources',
      component: ReferenceAreasView,
      meta: { title: '空间数据' },
    },
    {
      path: '/georeferencing',
      name: 'georeferencing',
      component: GeoreferencingView,
      meta: { title: '影像配准' },
    },
    {
      path: '/results',
      name: 'results',
      component: ResultsView,
      meta: { title: '成果研判' },
    },
  ],
})

export default router
