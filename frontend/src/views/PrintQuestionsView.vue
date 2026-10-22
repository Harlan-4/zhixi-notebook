<template>
  <div class="print-page">
    <div class="print-toolbar no-print">
      <el-button type="primary" @click="doPrint">🖨️ 打印</el-button>
      <el-button @click="$router.back()">返回</el-button>
      <span class="muted ml8">A4 纵向；每题独立一块，含重做勾选框与订正区</span>
    </div>

    <h1 class="print-title">错题重做清单</h1>
    <div class="print-sub">
      共 {{ items.length }} 题 · 生成于 {{ today }} · 建议先遮住"我的作答"重做，再对照订正
    </div>

    <div v-for="(q, i) in items" :key="q.id" class="q-block">
      <div class="q-head">
        <b>第 {{ i + 1 }} 题</b>
        <span class="meta">{{ q.grade }} {{ q.question_type }}<template v-if="q.source_workbook"> · 来源：{{ q.source_workbook }} {{ q.source_location }}</template> · 录入 {{ (q.created_at || '').slice(0, 10) }}</span>
      </div>
      <div class="q-text"><MathText :text="q.question_text" /></div>
      <div v-if="q.my_answer" class="my-answer">我的作答（重做时先遮住）：<MathText :text="q.my_answer" /></div>
      <div class="redo-row">
        <span>☐ 第1次重做：____月____日 &nbsp;对/错</span>
        <span>☐ 第2次重做：____月____日 &nbsp;对/错</span>
        <span>☐ 已掌握，无需再练</span>
      </div>
      <div class="fix-area">订正/错因：</div>
    </div>

    <el-empty v-if="!loading && items.length === 0" description="当前筛选条件下没有错题" />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'
import MathText from '../components/MathText.vue'

const route = useRoute()
const items = ref([])
const loading = ref(true)
const today = new Date().toLocaleDateString('zh-CN')

onMounted(async () => {
  try {
    const data = await api.get('/questions', {
      params: {
        status: route.query.status || '',
        kp: route.query.kp || '',
        q: route.query.q || '',
      },
    })
    items.value = data.items.slice(0, 100)
  } finally {
    loading.value = false
  }
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
.print-sub { text-align: center; color: #666; font-size: 13px; margin-bottom: 20px; }
.q-block { border: 1px solid #ccc; border-radius: 6px; padding: 12px 14px; margin-bottom: 14px; page-break-inside: avoid; }
.q-head { display: flex; justify-content: space-between; gap: 8px; flex-wrap: wrap; margin-bottom: 6px; }
.meta { color: #666; font-size: 12px; }
.q-text { line-height: 1.8; }
.my-answer { margin-top: 6px; font-size: 13px; color: #444; background: #f7f7f7; padding: 6px 8px; border-radius: 4px; }
.redo-row { display: flex; gap: 18px; flex-wrap: wrap; margin-top: 10px; font-size: 13px; }
.fix-area { margin-top: 10px; border-bottom: 1px dashed #bbb; height: 56px; font-size: 13px; color: #666; }

@media print {
  .no-print { display: none !important; }
  body { background: #fff; }
  .print-page { padding: 0; max-width: none; }
  .q-block { border-color: #999; }
}
</style>
