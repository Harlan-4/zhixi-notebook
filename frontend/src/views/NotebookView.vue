<template>
  <div class="page">
    <h1 class="page-title">错题本</h1>
    <div class="page-sub">拍照/手动录入错题 → AI 识别与解析 → 举一反三 → 复习打卡</div>

    <!-- 学习者画像 -->
    <el-card shadow="never" class="mb12">
      <el-collapse @change="onProfileToggle">
        <el-collapse-item name="profile">
          <template #title>
            <b>🎓 学习者画像</b>
            <span class="muted ml8">错因分布·薄弱点·进步趋势·个性化建议</span>
          </template>
          <div v-if="profile" class="profile-grid">
            <div>
              <div class="profile-label">错因分布（共 {{ profile.question_count }} 道错题）</div>
              <div v-for="e in profile.error_dist" :key="e.type" class="dist-row">
                <span class="dist-name">{{ e.type }}</span>
                <el-progress
                  class="dist-bar"
                  :percentage="Math.round(e.ratio * 100)"
                  :stroke-width="10"
                  :color="e.type === '未解析' ? '#c0c4cc' : '#409eff'"
                />
                <span class="muted">{{ e.count }} 题</span>
              </div>
            </div>
            <div>
              <div class="profile-label">高频薄弱点 Top5</div>
              <div class="weak-tags">
                <el-tag
                  v-for="w in profile.weak_top"
                  :key="w.name"
                  type="danger"
                  effect="plain"
                  size="small"
                  class="weak-tag"
                  @click="filterByKp(w.name)"
                >{{ w.name }} {{ Math.round(w.mastery * 100) }}%</el-tag>
                <span v-if="!profile.weak_top.length" class="muted">暂无薄弱知识点</span>
              </div>
              <div class="profile-label mt8">考试趋势</div>
              <div class="trend-line">
                <template v-for="(t, i) in profile.trend" :key="t.date">
                  <span v-if="i > 0" class="muted"> → </span>
                  <el-tag :type="i === profile.trend.length - 1 ? 'success' : 'info'" size="small">
                    {{ shortExamName(t.title) }} {{ t.my_score }}分
                  </el-tag>
                </template>
                <span v-if="!profile.trend.length" class="muted">暂无试卷记录</span>
              </div>
            </div>
            <div>
              <div class="profile-label">💡 个性化建议</div>
              <ul class="suggestion-list">
                <li v-for="(s, i) in profile.suggestions" :key="i">{{ s }}</li>
              </ul>
            </div>
          </div>
        </el-collapse-item>
      </el-collapse>
    </el-card>

    <el-card shadow="never" class="mb12">
      <div class="toolbar">
        <div class="toolbar-row">
          <el-select v-model="filter.subject" placeholder="科目" clearable style="width: 110px" @change="onSubjectChange">
            <el-option v-for="s in subjects" :key="s" :label="s" :value="s" />
          </el-select>
          <el-select v-model="filter.grade" placeholder="年级" clearable style="width: 110px" @change="onGradeChange">
            <el-option v-for="g in grades" :key="g" :label="g" :value="g" />
          </el-select>
          <el-select v-model="filter.status" placeholder="状态" clearable style="width: 120px" @change="load">
            <el-option label="未解析" value="new" />
            <el-option label="复习中" value="reviewing" />
            <el-option label="已掌握" value="mastered" />
          </el-select>
          <el-select v-model="filter.kp" placeholder="知识点" clearable filterable style="width: 200px" @change="load">
            <template v-if="filter.subject">
              <el-option v-for="k in kps" :key="k.name" :label="k.name" :value="k.name" />
            </template>
            <template v-else>
              <el-option-group v-for="g in kpsBySubject" :key="g.subject" :label="g.subject">
                <el-option v-for="k in g.list" :key="k.name" :label="k.name" :value="k.name" />
              </el-option-group>
            </template>
          </el-select>
          <el-input
            v-model="filter.q"
            placeholder="搜索题目关键词 / 练习册"
            clearable
            class="filter-search"
            @input="debouncedLoad"
          />
          <span v-if="game.streak || game.collected_count" class="game-badge">
            <el-tag v-if="game.streak" type="danger" effect="plain" size="small">🔥 连续打卡 {{ game.streak }} 天</el-tag>
            <el-tag type="warning" effect="plain" size="small">🏰 已收服 {{ game.collected_count }} 题</el-tag>
          </span>
        </div>
        <div class="toolbar-row">
          <el-button @click="printList">🖨️ 打印重做清单</el-button>
          <el-button @click="printRetest">📝 错题重测卷</el-button>
          <div class="spacer" />
          <el-button @click="manualDlg = true">✍️ 手动录入</el-button>
          <el-button type="primary" @click="photoDlg = true">📷 拍照录入</el-button>
        </div>
      </div>
    </el-card>

    <div v-if="loading" v-loading="loading" style="min-height: 200px" />
    <el-empty v-else-if="items.length === 0" description="还没有错题，点右上角录入第一道吧" />
    <div v-else>
      <section v-for="g in grouped" :key="g.subject" class="subject-section">
        <div class="subject-head">
          <span class="subject-title">{{ subjectIcon(g.subject) }} {{ g.subject }}</span>
          <span class="muted">{{ g.list.length }} 题</span>
        </div>
        <div class="card-grid">
          <el-card
            v-for="q in g.list"
            :key="q.id"
            shadow="hover"
            class="question-card"
            @click="$router.push(`/question/${q.id}`)"
          >
            <div class="q-head">
              <el-tag :type="statusType(q.status)" size="small">{{ statusText(q.status) }}</el-tag>
              <el-tag v-if="q.collected_at" type="warning" size="small" effect="dark">🏰</el-tag>
              <el-tag v-if="q.error_type" type="warning" size="small" effect="plain">{{ q.error_type }}</el-tag>
              <span class="muted">{{ (q.created_at || '').slice(0, 10) }}</span>
            </div>
            <div class="question-text-clamp q-body">
              <MathText :text="q.question_text" />
            </div>
            <div class="q-foot muted">
              <span v-if="q.source_workbook">📖 {{ q.source_workbook }} {{ q.source_location }}</span>
              <span v-else>题目 #{{ q.id }}</span>
              <span v-if="q.next_review_at">⏰ {{ q.next_review_at }} 复习</span>
            </div>
          </el-card>
        </div>
      </section>
    </div>

    <!-- 手动录入 -->
    <el-dialog v-model="manualDlg" title="手动录入错题" width="560px">
      <el-form label-width="90px">
        <el-form-item label="题目内容" required>
          <el-input v-model="form.question_text" type="textarea" :rows="4" placeholder="支持 $...$ 包裹的 LaTeX 公式" />
        </el-form-item>
        <el-form-item label="年级">
          <el-select v-model="form.grade" style="width: 140px">
            <el-option v-for="g in grades" :key="g" :label="g" :value="g" />
          </el-select>
        </el-form-item>
        <el-form-item label="我的作答">
          <el-input v-model="form.my_answer" type="textarea" :rows="2" placeholder="写了什么答案/怎么错的，AI 解析更准" />
        </el-form-item>
        <el-form-item label="来源练习册">
          <el-input v-model="form.source_workbook" placeholder="如：同步练习册（可留空）" />
        </el-form-item>
        <el-form-item label="页码题号">
          <el-input v-model="form.source_location" placeholder="如：P45 T8" style="width: 160px" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="manualDlg = false">取消</el-button>
        <el-button type="primary" :disabled="!form.question_text.trim()" @click="createManual">保存</el-button>
      </template>
    </el-dialog>

    <!-- 拍照录入 -->
    <el-dialog v-model="photoDlg" title="拍照录入（AI 识别）" width="560px">
      <el-alert
        v-if="aiUnavailable"
        type="warning"
        :closable="false"
        title="尚未配置 AI 服务"
        description="请先到「设置」页配置 OpenAI 兼容的 API Key（如智谱 GLM），配置后即可拍照识题。也可以先用「手动录入」。"
        class="mb12"
      />
      <input type="file" accept="image/*" capture="environment" @change="onPickPhoto" />
      <div v-if="photoUploading" class="mt8">
        <el-progress :percentage="60" :indeterminate="true" :duration="2" :show-text="false" />
        <div class="muted mt8">
          <template v-if="photoStage === 'compressing'">正在压缩图片…</template>
          <template v-else-if="photoStage === 'uploading'">正在上传图片…</template>
          <template v-else>🤖 AI 识别中，已用 {{ photoElapsed }} 秒（通常需要 15–40 秒，请勿关闭窗口）…</template>
        </div>
      </div>
      <el-form v-if="draft" label-width="90px" class="mt16">
        <el-form-item label="识别结果">
          <el-input v-model="draft.question_text" type="textarea" :rows="5" />
        </el-form-item>
        <el-form-item label="年级">
          <el-select v-model="draft.grade" style="width: 140px">
            <el-option v-for="g in grades" :key="g" :label="g" :value="g" />
          </el-select>
        </el-form-item>
        <el-form-item label="题型">
          <el-select v-model="draft.question_type" style="width: 140px">
            <el-option v-for="t in ['选择题', '填空题', '解答题']" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="我的作答">
          <el-input v-model="draft.my_answer_visible" type="textarea" :rows="2" />
        </el-form-item>
        <div class="muted">识别后可修改；图片已随错题一起保存。</div>
      </el-form>
      <template #footer>
        <el-button @click="photoDlg = false">取消</el-button>
        <el-button type="primary" :disabled="!draft" @click="savePhotoDraft">保存入错题本</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import MathText from '../components/MathText.vue'
import { compressImage } from '../utils/image'

const router = useRouter()
const grades = ['七年级', '八年级', '九年级', '高一', '高二', '高三']
const subjects = ['数学', '物理', '化学', '生物']
const items = ref([])
const profile = ref(null)
const kps = ref([])
const game = reactive({ streak: 0, collected_count: 0 })
const loading = ref(false)
const filter = reactive({ subject: '', grade: '', status: '', kp: '', q: '' })
const manualDlg = ref(false)
const photoDlg = ref(false)
const photoUploading = ref(false)
const aiUnavailable = ref(false)
const photoStage = ref('') // compressing / uploading / recognizing
const photoElapsed = ref(0)
let photoTimer = null

function startPhotoTimer() {
  photoElapsed.value = 0
  photoTimer = setInterval(() => {
    photoElapsed.value += 1
  }, 1000)
}
function stopPhotoTimer() {
  if (photoTimer) {
    clearInterval(photoTimer)
    photoTimer = null
  }
}
const draft = ref(null)
let photoImagePath = ''
let debounceTimer = null

const form = reactive({
  question_text: '', grade: '', my_answer: '', source_workbook: '', source_location: '',
})

function debouncedLoad() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(load, 300)
}

function printList() {
  const query = {}
  if (filter.subject) query.subject = filter.subject
  if (filter.grade) query.grade = filter.grade
  if (filter.status) query.status = filter.status
  if (filter.kp) query.kp = filter.kp
  if (filter.q) query.q = filter.q
  router.push({ path: '/print/questions', query })
}

function printRetest() {
  router.push('/print/retest')
}

async function loadProfile() {
  try {
    profile.value = await api.get('/stats/profile')
  } catch { /* 画像加载失败不阻塞列表 */ }
}

function onProfileToggle(activeNames) {
  if ((Array.isArray(activeNames) ? activeNames : [activeNames]).includes('profile') && profile.value === null) {
    loadProfile()
  }
}

function filterByKp(kp) {
  filter.kp = kp
  load()
}

function shortExamName(title) {
  // "高一上学期第一次月考" -> "第一次月考"；无"学期"字样则原样返回
  const parts = String(title).split('学期')
  return parts.length > 1 ? parts[parts.length - 1] : title
}

// 按科目分组展示（固定顺序：数学/物理/化学/生物，其余排最后）
const SUBJECT_ORDER = ['数学', '物理', '化学', '生物']
const grouped = computed(() => {
  const groups = new Map()
  for (const it of items.value) {
    const s = it.subject || '未分类'
    if (!groups.has(s)) groups.set(s, [])
    groups.get(s).push(it)
  }
  return [...groups.keys()]
    .sort((a, b) => rank(a) - rank(b))
    .map((s) => ({ subject: s, list: groups.get(s) }))
})
function rank(s) {
  const i = SUBJECT_ORDER.indexOf(s)
  return i === -1 ? SUBJECT_ORDER.length : i
}
function subjectIcon(s) {
  return { 数学: '🧮', 物理: '🧲', 化学: '⚗️', 生物: '🧬' }[s] || '📚'
}

async function load() {
  loading.value = true
  try {
    const data = await api.get('/questions', { params: { ...filter } })
    items.value = data.items
  } finally {
    loading.value = false
  }
}

function statusText(s) {
  return { new: '未解析', reviewing: '复习中', mastered: '已掌握' }[s] || s
}
function statusType(s) {
  return { new: 'info', reviewing: 'warning', mastered: 'success' }[s] || 'info'
}

async function createManual() {
  const q = await api.post('/questions', { ...form })
  manualDlg.value = false
  Object.assign(form, { question_text: '', grade: '', my_answer: '', source_workbook: '', source_location: '' })
  router.push(`/question/${q.id}`)
}

async function onPickPhoto(e) {
  const raw = e.target.files[0]
  if (!raw) return
  e.target.value = '' // 允许连续两次选同一张图
  photoUploading.value = true
  photoStage.value = 'compressing'
  aiUnavailable.value = false
  draft.value = null
  try {
    const file = await compressImage(raw)
    // 1) 保存图片（错题附带）2) AI 识别
    photoStage.value = 'uploading'
    const up = new FormData()
    up.append('file', file)
    const saved = await api.post('/questions/upload', up)
    photoImagePath = saved.image_path

    photoStage.value = 'recognizing'
    startPhotoTimer()
    const rec = new FormData()
    rec.append('file', file)
    rec.append('mime', file.type || 'image/jpeg')
    const { draft: d } = await api.post('/questions/recognize', rec)
    draft.value = {
      question_text: d.question_text || '',
      grade: d.grade || '',
      question_type: d.question_type || '解答题',
      my_answer_visible: d.my_answer_visible || '',
    }
  } catch (err) {
    if (err.response?.status === 503) aiUnavailable.value = true
  } finally {
    stopPhotoTimer()
    photoUploading.value = false
  }
}

async function savePhotoDraft() {
  const q = await api.post('/questions', {
    question_text: draft.value.question_text,
    grade: draft.value.grade,
    question_type: draft.value.question_type,
    my_answer: draft.value.my_answer_visible,
    image_path: photoImagePath,
  })
  photoDlg.value = false
  draft.value = null
  router.push(`/question/${q.id}`)
}

// 知识点下拉跟随科目：选了科目只列该科考点；未选科目时按科目分组展示
async function loadKps() {
  try {
    const params = {}
    if (filter.subject) params.subject = filter.subject
    if (filter.grade) params.grade = filter.grade
    const data = await api.get('/knowledge-points', { params })
    kps.value = data.items
  } catch { /* 图谱加载失败不阻塞列表 */ }
}

const kpsBySubject = computed(() => {
  const map = new Map()
  for (const k of kps.value) {
    const s = k.subject || '未分类'
    if (!map.has(s)) map.set(s, [])
    map.get(s).push(k)
  }
  return [...map.keys()].sort((a, b) => rank(a) - rank(b)).map((s) => ({ subject: s, list: map.get(s) }))
})

function onSubjectChange() {
  filter.kp = '' // 科目变化时清空已选知识点，避免跨科目残留
  loadKps()
  load()
}

function onGradeChange() {
  filter.kp = '' // 年级变化时清空已选知识点，知识点下拉跟随 科目×年级
  loadKps()
  load()
}

onMounted(async () => {
  load()
  try {
    const g = await api.get('/stats/gamification')
    game.streak = g.streak
    game.collected_count = g.collected_count
  } catch { /* 徽标加载失败不阻塞列表 */ }
  loadKps()
})
</script>

<style scoped>
.mb12 { margin-bottom: 12px; }
.ml8 { margin-left: 10px; }
.toolbar { display: flex; flex-direction: column; gap: 10px; }
.toolbar-row { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.toolbar-row .el-button + .el-button { margin-left: 0; }
.filter-search { flex: 1; min-width: 200px; max-width: 360px; }
.game-badge { display: inline-flex; gap: 6px; align-items: center; margin-left: auto; }
.spacer { flex: 1; }
.subject-section { margin-bottom: 18px; }
.subject-head {
  display: flex; justify-content: space-between; align-items: baseline;
  padding-bottom: 6px; margin-bottom: 10px; border-bottom: 2px solid var(--el-border-color, #e4e7ed);
}
.subject-title { font-size: 16px; font-weight: 700; color: #303133; }
.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; }
.q-head { display: flex; gap: 6px; align-items: center; margin-bottom: 8px; }
.q-head .muted { margin-left: auto; }
.q-body { min-height: 44px; }
.q-foot { display: flex; justify-content: space-between; gap: 8px; margin-top: 10px; flex-wrap: wrap; }
.profile-grid { display: grid; grid-template-columns: 1.2fr 1fr 1fr; gap: 20px; }
.profile-label { font-weight: 600; margin-bottom: 8px; }
.dist-row { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.dist-name { width: 72px; font-size: 13px; flex-shrink: 0; }
.dist-bar { flex: 1; }
.weak-tags { display: flex; gap: 6px; flex-wrap: wrap; }
.weak-tag { cursor: pointer; }
.trend-line { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }
.suggestion-list { margin: 0; padding-left: 18px; color: #606266; font-size: 13px; line-height: 1.9; }
@media (max-width: 900px) {
  .profile-grid { grid-template-columns: 1fr; }
}
@media (max-width: 768px) {
  .card-grid { grid-template-columns: 1fr; }
}
</style>
