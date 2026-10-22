import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'notebook', component: () => import('../views/NotebookView.vue'), meta: { title: '错题本' } },
  { path: '/question/:id', name: 'question', component: () => import('../views/QuestionDetail.vue'), meta: { title: '错题详情' } },
  { path: '/papers', name: 'papers', component: () => import('../views/PapersView.vue'), meta: { title: '试卷分析' } },
  { path: '/paper/:id', name: 'paper', component: () => import('../views/PaperDetail.vue'), meta: { title: '试卷详情' } },
  { path: '/plan', name: 'plan', component: () => import('../views/PlanView.vue'), meta: { title: '学习计划' } },
  { path: '/graph', name: 'graph', component: () => import('../views/GraphView.vue'), meta: { title: '知识图谱' } },
  { path: '/settings', name: 'settings', component: () => import('../views/SettingsView.vue'), meta: { title: '设置' } },
  { path: '/print/questions', name: 'printQuestions', component: () => import('../views/PrintQuestionsView.vue'), meta: { plain: true, title: '打印错题重做清单' } },
  { path: '/print/plan/:id', name: 'printPlan', component: () => import('../views/PrintPlanView.vue'), meta: { plain: true, title: '打印学习计划' } },
]

const router = createRouter({ history: createWebHistory(), routes })

router.afterEach((to) => {
  document.title = (to.meta.title ? to.meta.title + ' · ' : '') + '智析错题本'
})

export default router
