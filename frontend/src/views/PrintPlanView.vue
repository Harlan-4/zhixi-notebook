<template>
  <div class="print-page">
    <div class="print-toolbar no-print">
      <el-button type="primary" @click="doPrint">🖨️ 打印</el-button>
      <el-button @click="$router.back()">返回</el-button>
      <span class="muted ml8">按天分块，任务前留勾选框，完成后手写打勾</span>
    </div>

    <template v-if="plan">
      <h1 class="print-title">{{ plan.title }}</h1>
      <div class="print-sub">
        {{ plan.start_date }} 起 · 共 {{ plan.days }} 天 · 生成于 {{ today }}
      </div>

      <div v-for="(day, di) in plan.plan_data" :key="di" class="day-block">
        <div class="day-head">第 {{ di + 1 }} 天（{{ day.date }}）</div>
        <table v-if="day.tasks.length" class="task-table">
          <tr v-for="(t, ti) in day.tasks" :key="ti">
            <td class="cb">☐</td>
            <td class="act">{{ t.action }}</td>
            <td>
              <b>{{ t.knowledge_point }}</b>
              <div class="detail">{{ t.detail }}</div>
              <div v-if="t.reason" class="reason">{{ t.reason }}</div>
            </td>
          </tr>
        </table>
        <div v-else class="rest">休息 / 机动日</div>
      </div>

      <div class="sign-row">
        <span>学生签名：__________</span>
        <span>家长/老师签字：__________</span>
      </div>
    </template>
    <el-empty v-else-if="!loading" description="计划不存在" />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'

const route = useRoute()
const plan = ref(null)
const loading = ref(true)
const today = new Date().toLocaleDateString('zh-CN')

onMounted(async () => {
  try {
    plan.value = await api.get(`/plans/${route.params.id}`)
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
.day-block { border: 1px solid #ccc; border-radius: 6px; padding: 10px 14px; margin-bottom: 12px; page-break-inside: avoid; }
.day-head { font-weight: 700; margin-bottom: 6px; }
.task-table { width: 100%; border-collapse: collapse; }
.task-table td { padding: 5px 6px; vertical-align: top; font-size: 13px; }
.task-table .cb { width: 26px; font-size: 16px; }
.task-table .act { width: 70px; font-weight: 600; }
.detail { color: #444; }
.reason { color: #888; font-size: 12px; }
.rest { color: #999; font-size: 13px; }
.sign-row { display: flex; justify-content: space-between; margin-top: 24px; font-size: 13px; }

@media print {
  .no-print { display: none !important; }
  body { background: #fff; }
  .print-page { padding: 0; max-width: none; }
  .day-block { border-color: #999; }
}
</style>
