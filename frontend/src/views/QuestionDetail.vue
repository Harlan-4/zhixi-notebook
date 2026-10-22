<template>
  <div class="page" v-if="q">
    <el-page-header @back="$router.back()" class="mb12">
      <template #content>
        <span>错题 #{{ q.id }}</span>
        <el-tag :type="statusType(q.status)" size="small" class="ml8">{{ statusText(q.status) }}</el-tag>
        <el-tag v-if="q.error_type" type="warning" size="small" effect="plain" class="ml8">{{ q.error_type }}</el-tag>
      </template>
    </el-page-header>

    <el-card shadow="never" class="mb12">
      <div class="q-meta muted">
        <span>{{ q.grade }} {{ q.question_type }}</span>
        <span v-if="q.source_workbook">📖 来源：{{ q.source_workbook }} {{ q.source_location }}</span>
        <span v-if="q.next_review_at">⏰ 下次复习：{{ q.next_review_at }}</span>
        <span>已复习 {{ q.review_count }} 次</span>
      </div>
      <div class="q-text mt8"><MathText :text="q.question_text" /></div>
      <img v-if="q.image_url" :src="q.image_url" class="q-img mt8" />
      <div v-if="q.my_answer" class="my-answer mt8">
        <span class="muted">我的作答：</span><MathText :text="q.my_answer" />
      </div>
    </el-card>

    <el-card shadow="never" class="mb12">
      <div class="btn-row">
        <el-button type="primary" :loading="analyzing" @click="analyze">
          {{ q.analysis ? '🔄 重新AI解析' : '🤖 AI解析' }}
        </el-button>
        <el-button :loading="variantLoading" :disabled="!q.analysis" @click="genVariants">✨ 举一反三</el-button>
        <div class="spacer" />
        <template v-if="q.status !== 'mastered'">
          <el-button type="success" plain @click="review('pass')">✅ 这道我会了</el-button>
          <el-button type="danger" plain @click="review('fail')">❌ 还没掌握</el-button>
        </template>
        <el-tag v-else type="success">已掌握 🎉</el-tag>
      </div>
      <div v-if="q.analysis && q.analysis.correct_answer && q.status !== 'mastered'" class="check-row mt8">
        <el-input
          v-model="myCheckAnswer"
          size="small"
          placeholder="输入你重做后的答案，让 AI 批改（比自评更客观）"
          style="max-width: 360px"
          @keyup.enter="checkAnswer"
        />
        <el-button size="small" type="primary" :loading="checking" @click="checkAnswer"> AI 批改</el-button>
        <el-tag v-if="checkResult" :type="checkResult.correct ? 'success' : 'danger'" size="small">
          {{ checkResult.correct ? '✓ 正确' : '✗ ' + (checkResult.partial || '有误') }}
        </el-tag>
      </div>
      <el-alert
        v-if="checkResult && checkResult.feedback"
        :title="checkResult.feedback"
        :type="checkResult.correct ? 'success' : 'warning'"
        :closable="false"
        class="mt8"
      />
    </el-card>

    <el-card v-if="q.analysis" shadow="never" class="mb12">
      <template #header>
        <div class="btn-row">
          <b>🤖 AI 解析</b>
          <div class="spacer" />
          <el-select v-model="reexplainStyle" size="small" style="width: 130px" placeholder="自动选策略">
            <el-option label="回到定义" value="回到定义" />
            <el-option label="生活类比" value="生活类比" />
            <el-option label="拆小步骤" value="拆小步骤" />
            <el-option label="从错误倒推" value="从错误倒推" />
            <el-option label="考试视角" value="考试视角" />
          </el-select>
          <el-button size="small" type="primary" plain :loading="reexplainLoading" @click="reexplain">
            🔄 换种讲法
          </el-button>
        </div>
      </template>
      <div class="section"><span class="label">正确答案</span><MathText :text="q.analysis.correct_answer" /></div>
      <div class="section">
        <span class="label">解题步骤</span>
        <ol class="steps">
          <li v-for="(s, i) in q.analysis.solution_steps" :key="i"><MathText :text="s" /></li>
        </ol>
      </div>
      <div class="section">
        <span class="label">
          错因分析
          <el-tag
            v-if="q.analysis.cause_evidence"
            :type="q.analysis.cause_evidence === 'confirmed' ? 'success' : 'warning'"
            size="small"
            class="ml8"
          >{{ q.analysis.cause_evidence === 'confirmed' ? '✓ 有作答证据' : '? 推测（待确认）' }}</el-tag>
        </span>
        <div><MathText :text="q.analysis.error_analysis" /></div>
        <div v-if="diagnoseQuestions.length" class="diagnose-box mt8">
          <b>建议先问学生这几问，确认真实错因：</b>
          <ol class="steps">
            <li v-for="(d, i) in diagnoseQuestions" :key="i"><MathText :text="d" /></li>
          </ol>
        </div>
      </div>
      <div class="section">
        <span class="label">涉及知识点</span>
        <div class="kp-row">
          <el-tag
            v-for="kp in q.analysis.knowledge_points"
            :key="kp"
            type="primary"
            effect="plain"
            class="kp-tag"
            @click="$router.push('/graph')"
          >{{ kp }}</el-tag>
        </div>
        <div v-if="q.analysis.textbook_location" class="muted mt8">
          📖 教材定位：{{ q.analysis.textbook_location }}
        </div>
        <div v-if="workbookRefs.length" class="muted mt8">
          📝 练习册定位：<span v-for="(w, i) in workbookRefs" :key="i">{{ w }}<span v-if="i < workbookRefs.length - 1">；</span></span>
        </div>
      </div>
      <div v-if="q.analysis.tips && q.analysis.tips.length" class="section">
        <span class="label">易错提醒</span>
        <ul class="tips">
          <li v-for="(t, i) in q.analysis.tips" :key="i"><MathText :text="t" /></li>
        </ul>
      </div>
      <div v-if="altExplanations.length" class="section">
        <span class="label">🔁 换种讲法（觉得上面没讲通？看看别的角度）</span>
        <div v-for="(a, i) in altExplanations" :key="i" class="alt-box mb8">
          <el-tag size="small" type="success" class="mb8">{{ a.strategy }}</el-tag>
          <div><MathText :text="a.explanation" /></div>
        </div>
      </div>
    </el-card>

    <el-card v-if="q.variants && q.variants.length" shadow="never">
      <template #header><b>✨ 举一反三</b></template>
      <el-collapse>
        <el-collapse-item v-for="(v, i) in q.variants" :key="i" :name="i">
          <template #title>
            <el-tag v-if="v.type === '填步题'" size="small" class="mr8">填步题：补全 ______</el-tag>
            <el-tag v-else :type="v.difficulty === '基础' ? 'success' : 'warning'" size="small" class="mr8">{{ v.difficulty || '变式' }}</el-tag>
            <span class="variant-title"><MathText :text="v.text" /></span>
          </template>
          <div v-if="v.steps && v.steps.length" class="section">
            <span class="label">解法框架（请补全 ______ 处，再对照答案）</span>
            <ol class="steps">
              <li v-for="(s, j) in v.steps" :key="j"><MathText :text="s" /></li>
            </ol>
          </div>
          <div class="section"><span class="label">参考答案</span><MathText :text="v.answer" /></div>
          <div class="section"><span class="label">完整解析</span><MathText :text="v.solution" /></div>
        </el-collapse-item>
      </el-collapse>
    </el-card>

    <el-empty v-if="!q.analysis" description="还没有解析。点击上方「AI解析」生成解法、错因与知识点定位（需在设置页配置AI）" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute } from 'vue-router'
import api from '../api'
import MathText from '../components/MathText.vue'

const route = useRoute()
const q = ref(null)
const analyzing = ref(false)
const variantLoading = ref(false)
const workbookRefs = ref([])
const reexplainStyle = ref('')
const reexplainLoading = ref(false)
const myCheckAnswer = ref('')
const checking = ref(false)
const checkResult = ref(null)

const altExplanations = computed(() => q.value?.analysis?.alt_explanations || [])

const diagnoseQuestions = computed(() => {
  const analysis = q.value?.analysis
  if (!analysis || analysis.cause_evidence !== 'inferred') return []
  return analysis.diagnose_questions || []
})

async function load() {
  q.value = await api.get(`/questions/${route.params.id}`)
  workbookRefs.value = []
  const kps = q.value?.analysis?.knowledge_points || []
  for (const kp of kps.slice(0, 4)) {
    try {
      const data = await api.get('/workbooks/locate', { params: { kp } })
      for (const it of data.items) {
        workbookRefs.value.push(`《${it.workbook}》${it.chapter}${it.page ? '（' + it.page + '）' : ''}`)
      }
    } catch { /* ignore */ }
  }
}

async function analyze() {
  analyzing.value = true
  try {
    await api.post(`/questions/${q.value.id}/analyze`)
    await load()
  } catch { /* 拦截器已提示 */ } finally {
    analyzing.value = false
  }
}

async function genVariants() {
  variantLoading.value = true
  try {
    await api.post(`/questions/${q.value.id}/variants`)
    await load()
  } finally {
    variantLoading.value = false
  }
}

async function review(result) {
  q.value = await api.post(`/questions/${q.value.id}/review`, { result })
}

async function reexplain() {
  reexplainLoading.value = true
  try {
    await api.post(`/questions/${q.value.id}/reexplain`, { style: reexplainStyle.value || null })
    await load()
  } catch { /* 拦截器已提示 */ } finally {
    reexplainLoading.value = false
  }
}

async function checkAnswer() {
  if (!myCheckAnswer.value.trim()) return
  checking.value = true
  checkResult.value = null
  try {
    const r = await api.post(`/questions/${q.value.id}/check-answer`, { answer: myCheckAnswer.value })
    checkResult.value = r
    // 按核验证据自动记录一次复习（正确→pass，错误→fail）
    await review(r.correct ? 'pass' : 'fail')
    if (r.correct) ElMessage.success('批改正确，已记一次复习通过！')
  } catch { /* 拦截器已提示 */ } finally {
    checking.value = false
  }
}

function statusText(s) {
  return { new: '未解析', reviewing: '复习中', mastered: '已掌握' }[s] || s
}
function statusType(s) {
  return { new: 'info', reviewing: 'warning', mastered: 'success' }[s] || 'info'
}

onMounted(load)
</script>

<style scoped>
.mb12 { margin-bottom: 12px; }
.ml8 { margin-left: 8px; }
.mr8 { margin-right: 8px; }
.q-meta { display: flex; gap: 16px; flex-wrap: wrap; }
.q-text { font-size: 15px; line-height: 1.8; }
.q-img { max-width: 100%; max-height: 320px; border-radius: 6px; border: 1px solid #ebeef5; }
.my-answer { background: #fdf6ec; border-radius: 6px; padding: 8px 12px; line-height: 1.7; }
.btn-row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.spacer { flex: 1; }
.section { margin-bottom: 14px; line-height: 1.8; }
.label { display: block; font-weight: 600; margin-bottom: 4px; color: #303133; }
.steps { padding-left: 20px; margin: 4px 0; }
.tips { padding-left: 20px; margin: 4px 0; color: #b45309; }
.kp-row { display: flex; gap: 8px; flex-wrap: wrap; }
.kp-tag { cursor: pointer; }
.variant-title { flex: 1; }
.diagnose-box { background: #fdf6ec; border-radius: 6px; padding: 8px 12px; color: #b45309; }
.alt-box { background: #f0f9eb; border-radius: 6px; padding: 8px 12px; line-height: 1.8; }
.mb8 { margin-bottom: 8px; }
.mt8 { margin-top: 8px; }
.check-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
</style>
