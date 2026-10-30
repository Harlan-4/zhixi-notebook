<template>
  <div class="page">
    <h1 class="page-title">试卷分析</h1>
    <div class="page-sub">录入每次考试的逐题得分 → 按知识点统计失分 → 对比历次考试看进步方向</div>

    <div class="btn-row mb12">
      <el-button type="primary" @click="manualDlg = true">➕ 手动录入试卷</el-button>
      <el-button @click="photoDlg = true">📷 上传试卷识别</el-button>
    </div>

    <el-empty v-if="!loading && papers.length === 0" description="还没有试卷记录" />
    <div class="paper-list">
      <el-card
        v-for="p in papers"
        :key="p.id"
        shadow="hover"
        class="question-card"
        @click="$router.push(`/paper/${p.id}`)"
      >
        <div class="paper-row">
          <div>
            <b>{{ p.title }}</b>
            <div class="muted mt8">{{ p.paper_type }} · {{ p.exam_date }} · 共 {{ p.questions.length }} 题</div>
          </div>
          <div class="score-box">
            <span class="score">{{ p.my_score }}</span>
            <span class="muted">/ {{ p.total_score }}</span>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 手动录入 -->
    <el-dialog v-model="manualDlg" title="录入试卷" width="720px" top="5vh">
      <el-form label-width="80px">
        <div class="form-grid">
          <el-form-item label="试卷名称" required>
            <el-input v-model="form.title" placeholder="如：九年级上学期期中考试" />
          </el-form-item>
          <el-form-item label="考试日期">
            <el-date-picker v-model="form.exam_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
          </el-form-item>
          <el-form-item label="类型">
            <el-select v-model="form.paper_type" style="width: 100%">
              <el-option v-for="t in ['月考', '期中', '期末', '模拟']" :key="t" :label="t" :value="t" />
            </el-select>
          </el-form-item>
          <el-form-item label="我的总分">
            <el-input-number v-model="form.my_score" :min="0" style="width: 100%" />
          </el-form-item>
        </div>
      </el-form>
      <div class="muted mb8">逐题录入（题号 / 题目摘要 / 分值 / 我的得分 / 知识点，逗号分隔）：</div>
      <el-table :data="form.questions" size="small" border>
        <el-table-column label="#" width="60">
          <template #default="{ $index }">{{ $index + 1 }}</template>
        </el-table-column>
        <el-table-column label="题目摘要">
          <template #default="{ row }"><el-input v-model="row.text" placeholder="题干要点" /></template>
        </el-table-column>
        <el-table-column label="分值" width="90">
          <template #default="{ row }"><el-input-number v-model="row.score" :min="0" size="small" style="width: 100%" /></template>
        </el-table-column>
        <el-table-column label="得分" width="90">
          <template #default="{ row }"><el-input-number v-model="row.got_score" :min="0" size="small" style="width: 100%" /></template>
        </el-table-column>
        <el-table-column label="知识点">
          <template #default="{ row }">
            <el-select v-model="row.knowledge_points" multiple filterable allow-create placeholder="选择或输入" style="width: 100%">
              <el-option v-for="k in kps" :key="k.name" :label="k.name" :value="k.name" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column width="60">
          <template #default="{ $index }">
            <el-button text type="danger" @click="form.questions.splice($index, 1)">删</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-button text type="primary" class="mt8" @click="addQuestionRow">+ 添加一题</el-button>
      <template #footer>
        <el-button @click="manualDlg = false">取消</el-button>
        <el-button type="primary" :disabled="!form.title.trim() || form.questions.length === 0" @click="savePaper(false)">保存并分析</el-button>
      </template>
    </el-dialog>

    <!-- 上传识别 -->
    <el-dialog v-model="photoDlg" title="上传试卷识别（AI）" width="720px" top="5vh">
      <el-alert
        v-if="aiUnavailable"
        type="warning"
        :closable="false"
        title="尚未配置 AI 服务"
        description="请先到「设置」页配置 API Key；或直接用「手动录入试卷」。"
        class="mb12"
      />
      <div class="upload-grid">
        <div class="upload-cell">
          <div class="upload-label">📄 试卷照片（必填，可多张，按页序）</div>
          <input type="file" accept="image/*" multiple @change="(e) => onPickFiles(e, 'paper')" :disabled="photoUploading" />
          <div class="muted" v-if="paperFiles.length">已选 {{ paperFiles.length }} 张</div>
        </div>
        <div class="upload-cell">
          <div class="upload-label">📝 答题卡照片（选填，可多张）</div>
          <input type="file" accept="image/*" multiple @change="(e) => onPickFiles(e, 'answer')" :disabled="photoUploading" />
          <div class="muted" v-if="answerFiles.length">已选 {{ answerFiles.length }} 张</div>
        </div>
      </div>
      <div class="muted mt8">
        同时上传试卷和答题卡时，AI 会对照批改痕迹自动判定每题得分与错误点；只传试卷则识别题目和分值，得分需手动补填。
      </div>
      <div class="mt8" v-if="!draftReady">
        <el-button type="primary" :loading="photoUploading" :disabled="!paperFiles.length" @click="recognizeFiles">
          🔍 开始 AI 识别
        </el-button>
        <span v-if="photoUploading" class="muted ml8">
          <template v-if="photoStage === 'compressing'">正在压缩图片…</template>
          <template v-else-if="photoStage === 'uploading'">正在上传…</template>
          <template v-else>🤖 AI 识别中，已用 {{ photoElapsed }} 秒（整卷加答题卡可能需要 1–3 分钟，请勿关闭）…</template>
        </span>
      </div>
      <template v-if="draftReady">
        <el-form label-width="80px" class="mt16">
          <div class="form-grid">
            <el-form-item label="试卷名称">
              <el-input v-model="form.title" />
            </el-form-item>
            <el-form-item label="考试日期">
              <el-date-picker v-model="form.exam_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </div>
        </el-form>
        <el-table :data="form.questions" size="small" border>
          <el-table-column label="题号" width="70">
            <template #default="{ row }"><el-input v-model="row.no" size="small" /></template>
          </el-table-column>
          <el-table-column label="题目摘要">
            <template #default="{ row }"><el-input v-model="row.text" size="small" /></template>
          </el-table-column>
          <el-table-column label="分值" width="90">
            <template #default="{ row }"><el-input-number v-model="row.score" :min="0" size="small" style="width: 100%" /></template>
          </el-table-column>
          <el-table-column label="我的得分" width="100">
            <template #default="{ row }"><el-input-number v-model="row.got_score" :min="0" size="small" style="width: 100%" /></template>
          </el-table-column>
          <el-table-column label="知识点">
            <template #default="{ row }">
              <el-select v-model="row.knowledge_points" multiple filterable allow-create size="small" style="width: 100%">
                <el-option v-for="k in kps" :key="k.name" :label="k.name" :value="k.name" />
              </el-select>
            </template>
          </el-table-column>
        </el-table>
        <el-alert v-if="gradeNote" :title="gradeNote" type="info" :closable="false" class="mt8" />
        <div class="muted mt8">请核对识别结果，得分与实际情况不符的直接改，然后保存。</div>
      </template>
      <template #footer>
        <el-button @click="photoDlg = false">取消</el-button>
        <el-button type="primary" :disabled="!draftReady" @click="savePaper(true)">保存并分析</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { compressImage } from '../utils/image'

const router = useRouter()
const papers = ref([])
const kps = ref([])
const loading = ref(true)
const manualDlg = ref(false)
const paperFiles = ref([])
const answerFiles = ref([])
const gradeNote = ref('')
const photoStage = ref('')
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
const photoDlg = ref(false)
const photoUploading = ref(false)
const aiUnavailable = ref(false)
const draftReady = ref(false)

const today = new Date().toISOString().slice(0, 10)
const form = reactive({
  title: '', exam_date: today, paper_type: '月考', my_score: 0, questions: [],
})

function addQuestionRow() {
  form.questions.push({ no: String(form.questions.length + 1), text: '', score: 0, got_score: 0, knowledge_points: [] })
}

async function load() {
  loading.value = true
  try {
    const data = await api.get('/papers')
    papers.value = data.items
  } finally {
    loading.value = false
  }
}

async function savePaper(fromPhoto) {
  const payload = {
    title: form.title,
    exam_date: form.exam_date,
    paper_type: form.paper_type,
    my_score: form.my_score || form.questions.reduce((s, q) => s + (q.got_score || 0), 0),
    questions: form.questions.map((q, i) => ({ ...q, no: q.no || String(i + 1) })),
  }
  const p = await api.post('/papers', payload)
  manualDlg.value = false
  photoDlg.value = false
  router.push(`/paper/${p.id}?analyze=1`)
}

// 选择某类图片（paper/answer）：压缩后整组替换，支持重复选择更正
async function onPickFiles(e, kind) {
  const raw = [...e.target.files]
  e.target.value = ''
  if (!raw.length) return
  const compressed = await Promise.all(raw.map((f) => compressImage(f)))
  if (kind === 'answer') answerFiles.value = compressed
  else paperFiles.value = compressed
}

async function recognizeFiles() {
  if (!paperFiles.value.length || photoUploading.value) return
  photoUploading.value = true
  aiUnavailable.value = false
  draftReady.value = false
  try {
    photoStage.value = 'compressing'
    const rec = new FormData()
    const entries = [
      ...paperFiles.value.map((f) => ({ file: f, kind: 'paper' })),
      ...answerFiles.value.map((f) => ({ file: f, kind: 'answer' })),
    ]
    const kinds = []
    for (const { file, kind } of entries) {
      rec.append('files', file)
      kinds.push(kind)
    }
    rec.append('kinds', kinds.join(','))
    photoStage.value = 'uploading'
    startPhotoTimer()
    const { draft } = await api.post('/papers/recognize', rec)
    form.title = draft.title || '（请填写试卷名称）'
    form.questions = (draft.questions || []).map((q, i) => ({
      no: String(q.no ?? i + 1),
      text: q.text || '',
      score: q.score || 0,
      got_score: q.got_score ?? 0,
      knowledge_points: q.knowledge_points || [],
    }))
    gradeNote.value = draft.grade_note || ''
    draftReady.value = true
  } catch (err) {
    if (err.response?.status === 503) aiUnavailable.value = true
  } finally {
    stopPhotoTimer()
    photoUploading.value = false
  }
}

onMounted(async () => {
  load()
  try {
    kps.value = (await api.get('/knowledge-points')).items
  } catch { /* ignore */ }
})
</script>

<style scoped>
.upload-grid { display: flex; gap: 24px; flex-wrap: wrap; }
.upload-cell { flex: 1; min-width: 240px; }
.upload-label { font-weight: 600; margin-bottom: 6px; }
.mb12 { margin-bottom: 12px; }
.mb8 { margin-bottom: 8px; }
.mt8 { margin-top: 8px; }
.btn-row { display: flex; gap: 8px; }
.paper-list { display: grid; gap: 12px; }
.paper-row { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.score-box .score { font-size: 28px; font-weight: 700; color: #409eff; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 16px; }
@media (max-width: 640px) { .form-grid { grid-template-columns: 1fr; } }
</style>
