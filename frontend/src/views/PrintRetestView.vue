<template>
  <div class="print-page">
    <div class="print-toolbar no-print">
      <el-button type="primary" @click="doPrint">🖨️ 打印</el-button>
      <el-button @click="$router.back()">返回</el-button>
      <span class="muted ml8">A4 纵向；本周到期复习题的变式自测卷，答案在最后一页</span>
    </div>

    <h1 class="print-title">错题重测卷</h1>
    <div class="print-sub">
      共 {{ items.length }} 题（{{ grouped.map((g) => g.subject + " " + g.list.length + "题").join(" · ") }}） · 生成于 {{ today }} · 范围：{{ weekEnd }} 前到期的复习题（已掌握的不再出现）
    </div>
    <div class="score-row">得分：________ ／ {{ items.length }} 题 &nbsp;&nbsp;·&nbsp;&nbsp; 自查签字：______________</div>

    <section v-for="g in grouped" :key="g.subject" class="subject-section">
      <div class="subject-head">
        <span class="subject-name">{{ g.subject }}</span>
        <span class="meta">{{ g.list.length }} 题</span>
      </div>
      <div v-for="it in g.list" :key="it.id" class="q-block">
      <div class="q-head">
        <b>第 {{ it.no }} 题</b>
        <span class="q-chip">{{ it.from_variant ? '变式' : '原题重做' }}</span>
        <span class="meta">
          <template v-if="it.kp">{{ it.kp }} · </template>{{ it.next_review_at }} 到期
        </span>
      </div>
      <div class="q-text"><MathText :text="it.stem" /></div>
      <div class="answer-lines">
        <div class="aline" v-for="j in 3" :key="j"></div>
      </div>
    </div>
    </section>

    <div v-if="items.length" class="answers-block">
      <h2 class="answers-title">答案速查（全部做完再翻到这页对答案）</h2>
      <ol class="answers-list">
        <li v-for="(it, i) in items" :key="it.id">
          <span class="answers-no">第 {{ i + 1 }} 题：</span>
          <MathText v-if="it.answer" :text="it.answer" />
          <span v-else class="muted">无参考答案，请到详情页对照 AI 解析</span>
        </li>
      </ol>
    </div>

    <el-empty v-if="!loading && items.length === 0" description="本周没有到期的复习题——错题怪兽都被你收服了，保持节奏！" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../api'
import MathText from '../components/MathText.vue'

const items = ref([])
const loading = ref(true)
const today = new Date().toLocaleDateString('zh-CN')

function fmtLocal(d) {
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}
const weekEnd = fmtLocal(new Date(Date.now() + 7 * 24 * 3600 * 1000))

onMounted(async () => {
  try {
    const data = await api.get('/questions')
    items.value = data.items
      .filter((q) => q.status !== 'mastered' && q.next_review_at && q.next_review_at.slice(0, 10) <= weekEnd)
      .sort((a, b) => (a.next_review_at || '').localeCompare(b.next_review_at || ''))
      .slice(0, 20)
      .map((q) => {
        // 优先取"非填步题"的第一个变式做重测（填步题是引导练习，不适合自测）；无变式回退原题
        const variants = Array.isArray(q.variants) ? q.variants : []
        const v = variants.find((x) => x && x.type !== '填步题' && x.text) || null
        return {
          id: q.id,
          subject: q.subject || '未分类',
          from_variant: !!v,
          stem: v ? v.text : q.question_text,
          answer: v ? v.answer || '' : q.analysis?.correct_answer || '',
          kp: (q.analysis?.knowledge_points || [])[0] || '',
          next_review_at: (q.next_review_at || '').slice(0, 10),
        }
      })
  } finally {
    loading.value = false
  }
})

// 按科目分节（题号全局连续），每节打印时独立起页
const SUBJECT_ORDER = ['数学', '物理', '化学', '生物']
const grouped = computed(() => {
  const map = new Map()
  items.value.forEach((it, i) => {
    if (!map.has(it.subject)) map.set(it.subject, [])
    map.get(it.subject).push({ ...it, no: i + 1 })
  })
  const rank = (x) => {
    const i = SUBJECT_ORDER.indexOf(x)
    return i === -1 ? SUBJECT_ORDER.length : i
  }
  return [...map.keys()].sort((a, b) => rank(a) - rank(b)).map((s) => ({ subject: s, list: map.get(s) }))
})

function doPrint() {
  window.print()
}
</script>

<style scoped>
.print-page { max-width: 820px; margin: 0 auto; padding: 24px; background: #fff; min-height: 100vh; }
.print-toolbar { margin-bottom: 16px; }
.ml8 { margin-left: 8px; }
.muted { color: #909399; font-size: 13px; }
.print-title { text-align: center; margin: 0 0 4px; font-size: 22px; }
.print-sub { text-align: center; color: #666; font-size: 13px; margin-bottom: 14px; }
.score-row { border: 1.5px solid #333; border-radius: 6px; padding: 10px 14px; font-size: 15px; margin-bottom: 18px; page-break-inside: avoid; }
.subject-section + .subject-section { break-before: page; page-break-before: always; }
.subject-head {
  display: flex; justify-content: space-between; align-items: baseline;
  border-bottom: 2px solid #333; padding-bottom: 6px; margin: 6px 0 14px;
}
.subject-name { font-size: 20px; font-weight: 700; }
.q-block { border: 1px solid #ccc; border-radius: 6px; padding: 12px 14px; margin-bottom: 14px; page-break-inside: avoid; }
.q-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 6px; }
.q-chip { font-size: 12px; border: 1px solid #d4a017; color: #a16207; border-radius: 4px; padding: 0 6px; line-height: 20px; }
.meta { color: #666; font-size: 12px; margin-left: auto; }
.q-text { line-height: 1.8; }
.answer-lines { margin-top: 10px; }
.aline { border-bottom: 1px solid #999; height: 34px; }
.answers-block { page-break-before: always; border-top: 2px solid #333; padding-top: 12px; }
.answers-title { font-size: 16px; margin: 0 0 10px; }
.answers-list { padding-left: 20px; line-height: 2; font-size: 14px; }
.answers-no { font-weight: 600; }

@media print {
  .no-print { display: none !important; }
  body { background: #fff; }
  .print-page { padding: 0; max-width: none; }
  .q-block { border-color: #999; }
}
</style>
