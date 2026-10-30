<template>
  <div class="page" v-if="paper">
    <el-page-header @back="$router.back()" class="mb12">
      <template #content>
        <span>{{ paper.title }}</span>
        <el-tag size="small" class="ml8">{{ paper.paper_type }}</el-tag>
        <span class="muted ml8">{{ paper.exam_date }}</span>
      </template>
    </el-page-header>

    <el-row :gutter="12" class="mb12">
      <el-col :span="8">
        <el-card shadow="never"><el-statistic title="我的得分" :value="paper.my_score" /></el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never"><el-statistic title="卷面总分" :value="paper.total_score" /></el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never">
          <el-statistic title="得分率" :value="scoreRate" suffix="%" :precision="1" />
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="mb12">
      <div class="btn-row">
        <el-button type="primary" :loading="analyzing" @click="analyze">📊 生成/更新进步分析</el-button>
        <el-button @click="editScores = !editScores">✏️ {{ editScores ? '完成编辑' : '编辑逐题得分' }}</el-button>
        <el-button @click="openImportDlg">📥 失分题加入错题本</el-button>
        <div class="spacer" />
        <el-button type="success" @click="makePlan">📅 按薄弱点生成学习计划</el-button>
      </div>
    </el-card>

    <template v-if="paper.analysis">
      <el-card shadow="never" class="mb12">
        <template #header><b>📈 纵向进步分析</b></template>
        <el-alert
          v-for="(s, i) in paper.analysis.summary"
          :key="i"
          :title="s"
          type="info"
          :closable="false"
          class="mb8"
        />
      </el-card>

      <el-row :gutter="12" class="mb12">
        <el-col :xs="24" :md="12">
          <el-card shadow="never">
            <template #header><b>历次考试得分率趋势</b></template>
            <div ref="trendEl" style="height: 260px" />
          </el-card>
        </el-col>
        <el-col :xs="24" :md="12">
          <el-card shadow="never">
            <template #header><b>薄弱知识点 TOP（本卷失分）</b></template>
            <el-table :data="paper.analysis.weak_points.slice(0, 8)" size="small">
              <el-table-column prop="name" label="知识点" min-width="140" />
              <el-table-column label="失分/总分" width="100">
                <template #default="{ row }">{{ row.lost_score }} / {{ row.total_score }}</template>
              </el-table-column>
              <el-table-column label="失分率" width="140">
                <template #default="{ row }">
                  <el-progress :percentage="Math.round(row.lost_ratio * 100)" :stroke-width="10"
                    :color="row.lost_ratio >= 0.5 ? '#f56c6c' : row.lost_ratio >= 0.3 ? '#e6a23c' : '#67c23a'" />
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>
      </el-row>
    </template>

    <el-card shadow="never">
      <template #header><b>📋 逐题明细</b></template>
      <el-table :data="paper.questions" size="small" border>
        <el-table-column prop="no" label="题号" width="60" />
        <el-table-column label="题目" min-width="240">
          <template #default="{ row }"><MathText :text="row.text" /></template>
        </el-table-column>
        <el-table-column label="知识点" min-width="160">
          <template #default="{ row }">
            <el-tag v-for="kp in row.knowledge_points" :key="kp" size="small" effect="plain" class="kp-tag">{{ kp }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="score" label="分值" width="70" />
        <el-table-column label="得分" width="120">
          <template #default="{ row }">
            <el-input-number v-if="editScores" v-model="row.got_score" :min="0" :max="row.score" size="small" style="width: 100%" />
            <span v-else :class="{ 'lost': row.got_score < row.score }">{{ row.got_score }}</span>
          </template>
        </el-table-column>
      </el-table>
      <el-button v-if="editScores" type="primary" class="mt8" @click="saveScores">保存得分</el-button>
    </el-card>

    <el-dialog v-model="importDlg" title="把失分题加入错题本" width="640px">
      <div class="muted mb8">勾选要收进错题本的题目（默认全选本卷失分题）。加入后到错题本逐题「AI 解析」，即可进入复习计划。</div>
      <el-empty v-if="!wrongQuestions.length" description="本卷没有失分题，全部掌握！" :image-size="60" />
      <div v-for="q in wrongQuestions" :key="q.no" class="wrong-item" @click="toggle(q.no)">
        <el-checkbox :model-value="importNos.includes(q.no)" @change="toggle(q.no)">
          <b>第{{ q.no }}题</b>
          <span class="muted">（{{ q.got_score }}/{{ q.score }} 分）</span>
        </el-checkbox>
        <span class="wrong-text">{{ plainText(q.text) }}</span>
      </div>
      <template #footer>
        <el-button @click="importDlg = false">取消</el-button>
        <el-button type="primary" :disabled="!importNos.length" :loading="importing" @click="doImport">
          加入错题本（{{ importNos.length }} 题）
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import api from '../api'
import MathText from '../components/MathText.vue'

const route = useRoute()
const router = useRouter()
const paper = ref(null)
const analyzing = ref(false)
const editScores = ref(false)
const trendEl = ref(null)
let chart = null
const importDlg = ref(false)
const importNos = ref([])
const importing = ref(false)

const wrongQuestions = computed(() =>
  (paper.value?.questions || []).filter((q) => (q.got_score || 0) < (q.score || 0))
)

function openImportDlg() {
  importNos.value = wrongQuestions.value.map((q) => q.no)
  importDlg.value = true
}

function toggle(no) {
  const i = importNos.value.indexOf(no)
  if (i >= 0) importNos.value.splice(i, 1)
  else importNos.value.push(no)
}

function plainText(t) {
  return String(t || '').replace(/\s+/g, ' ').slice(0, 56)
}

async function doImport() {
  importing.value = true
  try {
    const r = await api.post(`/papers/${paper.value.id}/add-wrong-to-notebook`, { nos: importNos.value })
    ElMessage.success(
      `已加入 ${r.created_count} 道错题` +
        (r.skipped_nos.length ? `，${r.skipped_nos.length} 道已在错题本中（跳过）` : '')
    )
    importDlg.value = false
  } catch { /* 拦截器已提示 */ } finally {
    importing.value = false
  }
}

const scoreRate = computed(() =>
  paper.value && paper.value.total_score
    ? Math.round((paper.value.my_score / paper.value.total_score) * 1000) / 10
    : 0
)

async function load() {
  paper.value = await api.get(`/papers/${route.params.id}`)
  if (paper.value.analysis) await nextTick(renderTrend)
}

async function analyze() {
  analyzing.value = true
  try {
    paper.value = await api.post(`/papers/${paper.value.id}/analyze`)
    await nextTick(renderTrend)
  } finally {
    analyzing.value = false
  }
}

async function saveScores() {
  const my = paper.value.questions.reduce((s, q) => s + (q.got_score || 0), 0)
  paper.value = await api.patch(`/papers/${paper.value.id}`, {
    questions: paper.value.questions,
    my_score: my,
  })
  editScores.value = false
}

async function makePlan() {
  const plan = await api.post('/plans', { days: 7 })
  router.push('/plan')
}

function renderTrend() {
  if (!trendEl.value || !paper.value?.analysis) return
  const t = paper.value.analysis.trend
  if (!chart) chart = echarts.init(trendEl.value)
  chart.setOption({
    grid: { left: 40, right: 16, top: 30, bottom: 40 },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: t.dates, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', min: 0, max: 1, axisLabel: { formatter: (v) => Math.round(v * 100) + '%' } },
    series: [
      {
        type: 'line',
        name: '得分率',
        data: t.score_rates,
        smooth: true,
        symbolSize: 8,
        lineStyle: { width: 3, color: '#409eff' },
        itemStyle: { color: '#409eff' },
        label: { show: true, formatter: (p) => Math.round(p.value * 100) + '%', fontSize: 10 },
      },
    ],
  })
}

onMounted(async () => {
  await load()
  if (route.query.analyze && !paper.value.analysis) analyze()
})
</script>

<style scoped>
.mb12 { margin-bottom: 12px; }
.mb8 { margin-bottom: 8px; }
.ml8 { margin-left: 8px; }
.mt8 { margin-top: 8px; }
.btn-row { display: flex; gap: 8px; flex-wrap: wrap; }
.spacer { flex: 1; }
.kp-tag { margin: 0 4px 4px 0; }
.lost { color: #f56c6c; font-weight: 600; }
.wrong-item { display: flex; align-items: flex-start; gap: 8px; margin-bottom: 8px; cursor: pointer; }
.wrong-item :deep(.el-checkbox__label) { white-space: normal; line-height: 1.6; }
.wrong-text { color: #909399; font-size: 13px; line-height: 1.8; }
</style>
