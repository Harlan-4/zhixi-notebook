<template>
  <div class="page">
    <h1 class="page-title">学习计划</h1>
    <div class="page-sub">
      基于知识图谱<b>前置依赖关系</b>排程：先补基础，再攻薄弱，最后间隔复测 —— 不是简单的"隔1/3/7天重复"
    </div>

    <el-card shadow="never" class="mb12">
      <div class="btn-row">
        <el-select v-model="days" style="width: 120px">
          <el-option label="未来 7 天" :value="7" />
          <el-option label="未来 10 天" :value="10" />
          <el-option label="未来 14 天" :value="14" />
        </el-select>
        <el-button type="primary" :loading="generating" @click="generate">✨ 生成新计划</el-button>
        <el-select v-if="plans.length > 1" v-model="currentId" style="width: 240px" @change="loadCurrent">
          <el-option v-for="p in plans" :key="p.id" :label="`${p.title}`" :value="p.id" />
        </el-select>
        <div class="spacer" />
        <span v-if="plan" class="muted">已完成 {{ doneCount }} / {{ totalCount }} 项</span>
        <el-button v-if="plan" @click="printPlan">🖨️ 打印计划</el-button>
        <el-button v-if="plan" type="warning" plain :loading="reviewLoading" @click="showReview">🌳 周复盘导图</el-button>
      </div>
    </el-card>

    <el-empty v-if="!plan && !loading" description="还没有学习计划。先在错题本和试卷分析里积累一些数据，再点「生成新计划」" />
    <div v-else-if="plan" class="plan-grid">
      <el-card v-for="(day, di) in plan.plan_data" :key="di" shadow="never" class="day-card">
        <template #header>
          <b>第 {{ di + 1 }} 天</b>
          <span class="muted ml8">{{ day.date }}（{{ weekday(day.date) }}）</span>
          <el-tag v-if="day.tasks.length === 0" size="small" type="info" class="ml8">休息/机动</el-tag>
        </template>
        <div v-for="(t, ti) in day.tasks" :key="ti" class="task" :class="{ done: t.done }">
          <el-checkbox :model-value="t.done" @change="toggle(di, ti)" />
          <div class="task-body">
            <div class="task-head">
              <el-tag size="small" :type="actionType(t.action)">{{ t.action }}</el-tag>
              <b>{{ t.knowledge_point }}</b>
              <span class="muted">{{ t.reason }}</span>
            </div>
            <div class="muted task-detail">{{ t.detail }}</div>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 周复盘思维导图 -->
    <el-dialog v-model="reviewDlg" title="学习周复盘" width="860px" top="4vh" @opened="renderReview">
      <div v-if="review" class="review-summary">
        共覆盖 <b>{{ review.kp_count }}</b> 个知识点，任务完成
        <b>{{ review.task_done }} / {{ review.task_total }}</b>
        。红色分支=错因提示，蓝色=当前掌握状态。
      </div>
      <div ref="reviewEl" style="height: 560px" />
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import api from '../api'

const router = useRouter()
const plans = ref([])
const plan = ref(null)
const currentId = ref(null)
const days = ref(7)
const generating = ref(false)
const loading = ref(true)
const reviewDlg = ref(false)
const reviewLoading = ref(false)
const review = ref(null)
const reviewEl = ref(null)
let reviewChart = null

const totalCount = computed(() =>
  plan.value ? plan.value.plan_data.reduce((s, d) => s + d.tasks.length, 0) : 0
)
const doneCount = computed(() =>
  plan.value
    ? plan.value.plan_data.reduce((s, d) => s + d.tasks.filter((t) => t.done).length, 0)
    : 0
)

async function load() {
  loading.value = true
  try {
    const data = await api.get('/plans')
    plans.value = data.items
    if (plans.value.length) {
      if (!currentId.value || !plans.value.some((p) => p.id === currentId.value)) {
        currentId.value = plans.value[0].id
      }
      await loadCurrent()
    } else {
      plan.value = null
    }
  } finally {
    loading.value = false
  }
}

async function loadCurrent() {
  if (!currentId.value) return
  plan.value = await api.get(`/plans/${currentId.value}`)
}

async function generate() {
  generating.value = true
  try {
    await api.post('/plans', { days: days.value })
    await load()
  } finally {
    generating.value = false
  }
}

async function toggle(di, ti) {
  const updated = await api.post(`/plans/${plan.value.id}/toggle`, { day_index: di, task_index: ti })
  const old = plan.value
  plan.value = updated
  // 勾选"错题重做/复测"会让错题状态变化，静默刷新计划列表标题即可
  if (old.id !== updated.id) currentId.value = updated.id
}

function weekday(dateStr) {
  return '日一二三四五六'[new Date(dateStr + 'T00:00:00').getDay()]
}

function actionType(a) {
  return { 概念巩固: 'primary', 错题重做: 'warning', 举一反三: 'success', 复测: 'danger' }[a] || 'info'
}

async function printPlan() {
  router.push(`/print/plan/${plan.value.id}`)
}

async function showReview() {
  reviewLoading.value = true
  try {
    review.value = await api.get(`/plans/${plan.value.id}/review`)
    reviewDlg.value = true
    // 对话框懒渲染 + 打开动画，等 DOM 就绪后主动渲染一次；@opened 兜底
    await nextTick()
    setTimeout(renderReview, 300)
  } finally {
    reviewLoading.value = false
  }
}

function renderReview() {
  if (!reviewEl.value || !review.value) return
  if (!reviewChart) reviewChart = echarts.init(reviewEl.value)
  reviewChart.setOption({
    tooltip: { trigger: 'item', triggerOn: 'mousemove' },
    series: [
      {
        type: 'tree',
        data: [review.value.tree],
        left: '18%',
        right: '26%',
        top: '2%',
        bottom: '2%',
        symbol: 'circle',
        symbolSize: 12,
        edgeShape: 'curve',
        initialTreeDepth: 2,
        itemStyle: { color: '#409eff' },
        lineStyle: { color: '#c0c4cc' },
        label: { position: 'left', verticalAlign: 'middle', align: 'right', fontSize: 12, distance: 6 },
        leaves: {
          label: { position: 'right', verticalAlign: 'middle', align: 'left' },
          itemStyle: { color: '#e6a23c' },
        },
        expandAndCollapse: true,
        animationDuration: 400,
      },
    ],
  })
}

onMounted(async () => {
  await load()
  window.addEventListener('resize', onResize)
})

function onResize() {
  reviewChart && reviewChart.resize()
}
</script>

<style scoped>
.mb12 { margin-bottom: 12px; }
.ml8 { margin-left: 8px; }
.btn-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.spacer { flex: 1; }
.plan-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(330px, 1fr)); gap: 12px; }
.task { display: flex; gap: 8px; padding: 8px 0; border-bottom: 1px dashed #ebeef5; align-items: flex-start; }
.task:last-child { border-bottom: none; }
.task.done .task-body { opacity: 0.45; text-decoration: line-through; }
.task-head { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.task-detail { margin-top: 2px; }
.review-summary { margin-bottom: 8px; color: #606266; font-size: 14px; }
@media (max-width: 768px) {
  .plan-grid { grid-template-columns: 1fr; }
}
</style>
