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
        <span v-if="q.collected_at">🏰 {{ q.collected_at }} 收服</span>
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
        <el-tag v-else type="success">🏰 已收服 🎉</el-tag>
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
          <el-button size="small" type="warning" plain @click="openQaChat">💬 我有疑问</el-button>
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
          <el-button
            v-if="(q.analysis.diagnose_chat || []).length"
            link
            type="primary"
            size="small"
            class="ml8"
            @click="openChat"
          >💬 查看错因对话</el-button>
        </span>
        <div><MathText :text="q.analysis.error_analysis" /></div>
        <div v-if="diagnoseQuestions.length" class="diagnose-box mt8">
          <b>建议先问学生这几问，确认真实错因：</b>
          <ol class="steps">
            <li v-for="(d, i) in diagnoseQuestions" :key="i"><MathText :text="d" /></li>
          </ol>
          <el-button size="small" type="warning" plain class="mt8" @click="openChat">💬 和 AI 对话确认错因</el-button>
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

    <el-dialog v-model="celebrateVisible" width="380px" align-center>
      <div class="celebrate" v-if="celebrate">
        <div class="celebrate-emoji">{{ celebrate.justCollected ? '🏰✨' : '🎉' }}</div>
        <div class="celebrate-title">{{ celebrate.justCollected ? '收服成功！' : '复习通过！' }}</div>
        <div class="celebrate-praise">{{ celebrate.praise }}</div>
        <div class="celebrate-tags">
          <el-tag type="danger" effect="dark">🔥 连续打卡 {{ celebrate.streak }} 天</el-tag>
          <el-tag v-if="celebrate.justCollected" type="warning" effect="dark">🏰 已收入错题图鉴</el-tag>
        </div>
        <div class="muted mt8" style="font-size: 12px">按艾宾浩斯节奏打怪兽，错题再也不回来</div>
      </div>
      <template #footer>
        <el-button type="primary" @click="celebrateVisible = false">继续加油</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="chatOpen" title="💬 错因追问对话" width="560px" :close-on-click-modal="false" :before-close="guardChatClose" @opened="scrollChat">
      <div v-if="chatConcluded" class="chat-concluded">
        ✅ 错因已确认{{ q?.error_type ? '：' + q.error_type : '' }}，学习画像已同步更新
      </div>
      <div ref="chatListEl" class="chat-list">
        <div v-for="(m, i) in chatMessages" :key="i" class="chat-row" :class="m.role">
          <div class="bubble"><MathText :text="m.text" /></div>
        </div>
        <div v-if="pendingMsg" class="chat-row student">
          <div class="bubble"><MathText :text="pendingMsg" /></div>
        </div>
        <div v-if="chatSending" class="chat-row ai">
          <div class="bubble typing">AI 正在分析你的回答…</div>
        </div>
        <div v-if="!chatMessages.length && !pendingMsg && !chatSending" class="chat-hint">
          <div class="muted">还没开始对话。对照下面几问，用口语说说你当时的想法：</div>
          <ol class="steps">
            <li v-for="(d, i) in diagnoseQuestions" :key="i"><MathText :text="d" /></li>
          </ol>
        </div>
      </div>
      <div class="chat-input">
        <el-input
          v-model="chatDraft"
          type="textarea"
          :rows="2"
          placeholder="说说你当时的想法 / 卡在哪一步…（Enter 发送）"
          @keydown.enter="onChatEnter"
        />
        <el-button type="primary" :loading="chatSending" :disabled="!chatDraft.trim()" @click="sendChat">发送</el-button>
      </div>
    </el-dialog>
    <el-dialog v-model="qaOpen" title="💬 向 AI 提问（哪里没看懂？）" width="560px" :close-on-click-modal="false" :before-close="guardQaClose" @opened="scrollQa">
      <div ref="qaListEl" class="chat-list">
        <div v-for="(m, i) in qaMessages" :key="i" class="chat-row" :class="m.role">
          <div class="bubble"><MathText :text="m.text" /></div>
        </div>
        <div v-if="qaPending" class="chat-row student">
          <div class="bubble"><MathText :text="qaPending" /></div>
        </div>
        <div v-if="qaSending" class="chat-row ai">
          <div class="bubble typing">AI 正在讲解…</div>
        </div>
        <div v-if="!qaMessages.length && !qaPending && !qaSending" class="chat-hint">
          <div class="muted">
            看完解析后哪一步没跟上？直接问，比如："第 2 步为什么要先开三次方、再平方？"也可以问概念本身。
          </div>
        </div>
      </div>
      <div class="chat-input">
        <el-input
          v-model="qaDraft"
          type="textarea"
          :rows="2"
          placeholder="问任何没看懂的步骤、概念、公式…（Enter 发送）"
          @keydown.enter="onQaEnter"
        />
        <el-button type="primary" :loading="qaSending" :disabled="!qaDraft.trim()" @click="sendQa">发送</el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
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
const celebrate = ref(null)
const celebrateVisible = ref(false)
const chatOpen = ref(false)
const chatDraft = ref('')
const chatSending = ref(false)
const chatListEl = ref(null)
const pendingMsg = ref(null)

// 讲解答疑对话（学生问 AI：哪里没看懂）
const qaOpen = ref(false)
const qaDraft = ref('')
const qaSending = ref(false)
const qaListEl = ref(null)
const qaPending = ref(null)
const qaMessages = computed(() => q.value?.analysis?.qa_chat || [])

function openQaChat() {
  qaOpen.value = true
}

function scrollQa() {
  nextTick(() => {
    const el = qaListEl.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

async function sendQa() {
  const text = qaDraft.value.trim()
  if (!text || qaSending.value) return
  qaDraft.value = ''
  qaPending.value = text
  qaSending.value = true
  nextTick(() => {
    if (qaListEl.value) qaListEl.value.scrollTop = qaListEl.value.scrollHeight
  })
  try {
    const r = await api.post(`/questions/${q.value.id}/qa-chat`, { message: text })
    q.value.analysis = { ...q.value.analysis, qa_chat: r.chat }
    qaPending.value = null
    nextTick(() => {
      if (qaListEl.value) qaListEl.value.scrollTop = qaListEl.value.scrollHeight
    })
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '发送失败，请重试')
    qaPending.value = null
    qaDraft.value = text // 发送失败把问题还给输入框
  } finally {
    qaSending.value = false
  }
}

const altExplanations = computed(() => q.value?.analysis?.alt_explanations || [])
const chatMessages = computed(() => q.value?.analysis?.diagnose_chat || [])
const chatConcluded = computed(
  () => q.value?.analysis?.cause_evidence === 'confirmed' && chatMessages.value.length > 0
)

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
  const r = await api.post(`/questions/${q.value.id}/review`, { result })
  q.value = r.question
  if (result === 'pass') {
    celebrate.value = { praise: r.praise, streak: r.streak, justCollected: r.just_collected }
    celebrateVisible.value = true
  } else {
    ElMessage.info('没关系，错题怪兽明天还会再来——对照解析补上缺口，你一定收服它！')
  }
}

function openChat() {
  chatOpen.value = true
  nextTick(scrollChat)
}

// 输入法选词的回车（isComposing/229）不触发发送
function onChatEnter(e) {
  if (e.isComposing || e.keyCode === 229) return
  e.preventDefault()
  sendChat()
}
function onQaEnter(e) {
  if (e.isComposing || e.keyCode === 229) return
  e.preventDefault()
  sendQa()
}
// 有未发送内容或正在发送时，关闭弹窗需确认，避免误触 ESC/遮罩丢失输入
function guardChatClose(done) {
  if (chatSending.value || chatDraft.value.trim()) {
    ElMessageBox.confirm('对话内容尚未保存，确定关闭吗？', '提示', {
      type: 'warning', confirmButtonText: '关闭', cancelButtonText: '继续输入',
    }).then(() => done()).catch(() => {})
  } else {
    done()
  }
}
function guardQaClose(done) {
  if (qaSending.value || qaDraft.value.trim()) {
    ElMessageBox.confirm('提问内容尚未保存，确定关闭吗？', '提示', {
      type: 'warning', confirmButtonText: '关闭', cancelButtonText: '继续输入',
    }).then(() => done()).catch(() => {})
  } else {
    done()
  }
}

function scrollChat() {
  nextTick(() => {
    const el = chatListEl.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

async function sendChat() {
  const text = chatDraft.value.trim()
  if (!text || chatSending.value) return
  chatDraft.value = ''
  pendingMsg.value = text
  chatSending.value = true
  scrollChat()
  try {
    const r = await api.post(`/questions/${q.value.id}/diagnose-chat`, { message: text })
    pendingMsg.value = null
    q.value.analysis = { ...q.value.analysis, diagnose_chat: r.chat }
    if (r.concluded) {
      await load()
      ElMessage.success('错因已确认：' + (r.error_type || r.cause_summary || ''))
    }
  } catch {
    pendingMsg.value = null
    chatDraft.value = text // 发送失败把内容还给输入框
  } finally {
    chatSending.value = false
    scrollChat()
  }
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
.celebrate { text-align: center; padding: 8px 0; }
.celebrate-emoji { font-size: 56px; line-height: 1.2; }
.celebrate-title { font-size: 20px; font-weight: 700; margin-top: 8px; color: #303133; }
.celebrate-praise { margin-top: 8px; line-height: 1.7; color: #606266; }
.celebrate-tags { margin-top: 12px; display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; }
.chat-list { max-height: 320px; overflow-y: auto; padding: 10px; background: #f7f8fa; border-radius: 6px; }
.chat-row { display: flex; margin-bottom: 8px; }
.chat-row.student { justify-content: flex-end; }
.chat-row.ai { justify-content: flex-start; }
.bubble { max-width: 80%; padding: 8px 12px; border-radius: 10px; line-height: 1.7; font-size: 14px; word-break: break-word; }
.chat-row.ai .bubble { background: #fff; border: 1px solid #e4e7ed; }
.chat-row.student .bubble { background: #d9ecff; }
.typing { color: #909399; }
.chat-hint { text-align: center; padding: 6px 4px; }
.chat-hint .steps { text-align: left; color: #b45309; }
.chat-concluded { background: #f0f9eb; color: #529b2e; border-radius: 6px; padding: 8px 12px; margin-bottom: 10px; font-weight: 600; }
.chat-input { display: flex; gap: 8px; margin-top: 10px; align-items: flex-end; }
</style>
