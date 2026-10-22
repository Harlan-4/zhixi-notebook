<template>
  <div class="page">
    <h1 class="page-title">知识图谱</h1>
    <div class="page-sub">
      选择科目与年级，查看对应的知识图谱与前置依赖关系（团队自主整理）。红色=薄弱，橙色=待巩固，绿色=较好，灰色=暂无数据。点击节点查看详情。
    </div>

    <el-card shadow="never" class="mb12">
      <div class="filter-row">
        <span class="filter-label">科目</span>
        <el-select v-model="subject" style="width: 120px" @change="onFilterChange">
          <el-option v-for="s in subjects" :key="s" :label="s" :value="s" />
        </el-select>
        <span class="filter-label">年级</span>
        <el-select v-model="grade" style="width: 140px" @change="onFilterChange">
          <el-option label="全部年级" value="" />
          <el-option v-for="g in grades" :key="g" :label="g" :value="g" />
        </el-select>
        <span class="muted">当前 {{ nodeCount }} 个知识点</span>
      </div>
    </el-card>

    <el-row :gutter="12">
      <el-col :xs="24" :md="17">
        <el-card shadow="never">
          <div v-show="nodeCount > 0" ref="chartEl" style="height: 560px" />
          <el-empty
            v-if="nodeCount === 0"
            :description="`${subject}${grade ? ' · ' + grade : ''} 的知识图谱暂未收录，正在建设中`"
          />
        </el-card>
      </el-col>
      <el-col :xs="24" :md="7">
        <el-card shadow="never">
          <template #header><b>{{ detail ? detail.name : '知识点详情' }}</b></template>
          <template v-if="detail">
            <p class="muted">{{ detail.description }}</p>
            <p><b>年级：</b>{{ detail.grade }} <el-tag size="small" class="ml8">{{ detail.ktype }}</el-tag></p>
            <p><b>教材定位：</b>{{ detail.chapter }}</p>
            <p>
              <b>掌握度：</b>
              <el-tag v-if="detail.mastery == null" type="info" size="small">暂无数据</el-tag>
              <el-tag v-else :type="masteryType(detail.mastery)" size="small">{{ Math.round(detail.mastery * 100) }}%</el-tag>
            </p>
            <p><b>前置知识：</b>{{ detail.prereqs.length ? detail.prereqs.join('、') : '无（起点知识点）' }}</p>
            <el-button
              size="small"
              type="primary"
              plain
              class="mt8"
              :loading="lessonLoading"
              @click="loadLesson"
            >🤖 AI 讲解本知识点</el-button>
            <div v-if="lesson" class="lesson mt8">
              <div class="lesson-sec"><b>💡 为什么学：</b>{{ lesson.hook }}</div>
              <div class="lesson-sec"><b>📖 核心内容：</b><MathText :text="lesson.core" /></div>
              <div class="lesson-sec"><b>⚠️ 易错点：</b>{{ lesson.pitfalls }}</div>
              <div class="lesson-sec"><b>✏️ 自测一下：</b><MathText :text="lesson.check" /></div>
              <el-collapse class="mt8">
                <el-collapse-item title="查看答案与解答"><MathText :text="lesson.answer" /></el-collapse-item>
              </el-collapse>
            </div>
            <template v-if="detail.related_questions.length">
              <p class="mt8"><b>相关错题（{{ detail.related_questions.length }}）：</b></p>
              <div v-for="q in detail.related_questions" :key="q.id" class="related-q">
                <el-link type="primary" @click="$router.push(`/question/${q.id}`)">
                  #{{ q.id }} {{ q.question_text.slice(0, 30) }}…
                </el-link>
              </div>
            </template>
          </template>
          <el-empty v-else description="点击左侧图中的知识点" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import api from '../api'
import MathText from '../components/MathText.vue'

const chartEl = ref(null)
const detail = ref(null)
const lessonLoading = ref(false)
const lesson = ref(null)
const subjects = ['数学', '物理', '化学', '生物']
const grades = ['七年级', '八年级', '九年级', '高一', '高二', '高三']
const subject = ref('数学')
const grade = ref('')
const nodeCount = ref(0)
let chart = null
let graphData = null

function nodeColor(mastery) {
  if (mastery == null) return '#909399'
  if (mastery < 0.65) return '#f56c6c'
  if (mastery < 0.85) return '#e6a23c'
  return '#67c23a'
}

async function loadDetail(name) {
  detail.value = await api.get(`/knowledge-points/${encodeURIComponent(name)}`)
  lesson.value = null
}

async function loadLesson() {
  if (!detail.value) return
  lessonLoading.value = true
  try {
    const r = await api.get(`/knowledge-points/${encodeURIComponent(detail.value.name)}/lesson`)
    lesson.value = r.lesson
  } catch { /* 拦截器已提示（未配置 AI 等） */ } finally {
    lessonLoading.value = false
  }
}

function render() {
  if (!chartEl.value || !graphData) return
  if (!chart) chart = echarts.init(chartEl.value)
  chart.setOption({
    tooltip: { formatter: (p) => (p.dataType === 'node' ? `${p.data.name}<br/>${p.data.chapter || ''}` : '') },
    series: [
      {
        type: 'graph',
        layout: 'force',
        roam: true,
        draggable: true,
        data: graphData.nodes.map((n) => ({
          ...n,
          itemStyle: { color: nodeColor(n.mastery) },
        })),
        links: graphData.edges,
        categories: [],
        force: { repulsion: 90, edgeLength: 55, gravity: 0.08 },
        label: { show: true, fontSize: 10, color: '#303133' },
        edgeSymbol: ['none', 'arrow'],
        edgeSymbolSize: 6,
        lineStyle: { color: '#c0c4cc', curveness: 0.1 },
        emphasis: { focus: 'adjacency', lineStyle: { width: 3, color: '#409eff' } },
      },
    ],
  })
  chart.off('click')
  chart.on('click', (p) => {
    if (p.dataType === 'node') loadDetail(p.data.name)
  })
}

async function reload() {
  graphData = await api.get('/graph', { params: { subject: subject.value, grade: grade.value } })
  nodeCount.value = graphData.nodes.length
  if (nodeCount.value === 0) {
    detail.value = null
    await nextTick()
    if (chart) {
      chart.clear()
    }
    return
  }
  await nextTick(render)
}

function onFilterChange() {
  reload()
}

function onResize() {
  chart && chart.resize()
}

onMounted(async () => {
  await reload()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart && chart.dispose()
})

function masteryType(m) {
  if (m < 0.65) return 'danger'
  if (m < 0.85) return 'warning'
  return 'success'
}
</script>

<style scoped>
.related-q { margin-bottom: 6px; }
.mb12 { margin-bottom: 12px; }
.ml8 { margin-left: 8px; }
.mt8 { margin-top: 8px; }
.filter-row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.filter-label { font-weight: 600; font-size: 14px; }
.lesson { background: #f5f7fa; border-radius: 6px; padding: 10px 12px; }
.lesson-sec { margin-bottom: 8px; line-height: 1.8; font-size: 13px; }
</style>
