<template>
  <div class="page">
    <h1 class="page-title">设置</h1>
    <div class="page-sub">AI 后端配置（OpenAI 兼容协议，支持智谱 / 通义千问 / DeepSeek / 本地 Ollama 等多后端切换）</div>

    <el-card shadow="never" class="mb12">
      <template #header><b>🤖 AI 服务</b></template>
      <el-form label-width="170px" style="max-width: 640px">
        <el-form-item label="接口地址 base_url">
          <el-input v-model="cfg.ai_base_url" placeholder="https://open.bigmodel.cn/api/paas/v4" />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input
            v-model="cfg.ai_api_key"
            type="password"
            show-password
            :placeholder="masked ? `已配置：${masked}（留空则不修改）` : '尚未配置'"
          />
        </el-form-item>
        <el-form-item label="多模态模型（识题）">
          <el-input v-model="cfg.ai_model" placeholder="glm-4.5v / qwen-vl-max / gpt-4o ..." />
        </el-form-item>
        <el-form-item label="文本模型（解析出题）">
          <el-input v-model="cfg.ai_text_model" placeholder="glm-4.6 / deepseek-chat / qwen-plus ..." />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="save">保存配置</el-button>
          <el-button :loading="testing" @click="test">测试连接</el-button>
        </el-form-item>
      </el-form>
      <el-alert v-if="testResult" :title="testResult" :type="testOk ? 'success' : 'error'" :closable="false" class="mt8" />
      <el-alert type="info" :closable="false" class="mt8">
        <template #title>常见后端示例</template>
        <div class="backend-examples">
          <div>智谱：https://open.bigmodel.cn/api/paas/v4（glm-4.5v / glm-4.6）</div>
          <div>通义：https://dashscope.aliyuncs.com/compatible-mode/v1（qwen-vl-max / qwen-plus）</div>
          <div>DeepSeek：https://api.deepseek.com（deepseek-chat）</div>
          <div>本地 Ollama：http://127.0.0.1:11434/v1（qwen2.5vl 等开源模型）</div>
        </div>
      </el-alert>
    </el-card>

    <el-card shadow="never" class="mb12">
      <template #header><b>🗄️ 数据</b></template>
      <div class="btn-row">
        <el-button @click="resetDemo">重置为演示数据</el-button>
        <span class="muted">清空错题/试卷/计划，重新导入内置示例（知识图谱保留）</span>
      </div>
    </el-card>

    <el-card shadow="never">
      <template #header><b>ℹ️ 关于</b></template>
      <p><b>智析错题本 v1.5</b> —— AI + 开源 的中学生错题管理与学习规划平台。</p>
      <p class="muted">
        v1.5 新增：讲解答疑对话（学生向 AI 提问没看懂的步骤）、错题按科目分类与打印分科分节、
        知识点筛选联动科目×年级（新增年级筛选）。
        v1.4 新增：知识图谱重构为四科 728 个考点级知识点（数学/物理/化学/生物，覆盖初高中全学段）、
        图谱页 URL 直达（/graph?subject=物理&grade=高二）。
        v1.3 新增：错因追问对话（AI 对话确认错因）、试卷失分题一键加入错题本、
        游戏化激励（收服徽章/连续打卡/庆祝卡）、错题重测卷 A4。
        v1.2 新增：知识图谱按科目/年级筛选、学习者画像、换种讲法、答案 AI 核验、
        知识点课型与 AI 迷你微课、图谱数据完整性校验。
        v1.1 新增：四步教学法"举一反三"、错因证据分级与诊断追问、
        错题重做清单/学习计划打印视图、学习周复盘思维导图、高一上学期示例数据与人教A版必修一知识图谱。
      </p>
      <p class="muted">
        基于 FastAPI / Vue3 / Element Plus / ECharts / KaTeX / SQLAlchemy 等开源组件构建；
        知识图谱数据与排程算法为本团队自主整理与实现，仓库整体以 MIT 许可证开放。
      </p>
      <el-collapse class="mt8">
        <el-collapse-item title="版本迭代记录" name="changelog">
          <el-timeline>
            <el-timeline-item
              v-for="rel in changelog"
              :key="rel.version"
              :timestamp="rel.version + ' · ' + rel.date"
              placement="top"
              type="primary"
            >
              <div v-for="g in rel.groups" :key="g.label" class="log-group">
                <el-tag :type="g.label === '新增' ? 'success' : 'warning'" size="small" class="log-tag">{{ g.label }}</el-tag>
                <ul class="log-list">
                  <li v-for="item in g.items" :key="item">{{ item }}</li>
                </ul>
              </div>
            </el-timeline-item>
          </el-timeline>
        </el-collapse-item>
      </el-collapse>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'

const cfg = ref({ ai_base_url: '', ai_api_key: '', ai_model: '', ai_text_model: '' })
const masked = ref('')
const saving = ref(false)
const testing = ref(false)
const testResult = ref('')
const testOk = ref(false)

async function load() {
  const s = await api.get('/settings')
  masked.value = s.api_key_masked
  cfg.value = {
    ai_base_url: s.ai_base_url,
    ai_api_key: '',
    ai_model: s.ai_model,
    ai_text_model: s.ai_text_model,
  }
}

async function save() {
  saving.value = true
  try {
    const payload = { ...cfg.value }
    if (!payload.ai_api_key) delete payload.ai_api_key // 留空不覆盖
    const s = await api.put('/settings', payload)
    masked.value = s.api_key_masked
    cfg.value.ai_api_key = ''
    ElMessage.success('已保存')
  } finally {
    saving.value = false
  }
}

async function test() {
  testing.value = true
  testResult.value = ''
  try {
    const r = await api.post('/settings/test')
    testOk.value = r.ok
    testResult.value = r.message
  } catch {
    testOk.value = false
    testResult.value = '测试失败（详见错误提示）'
  } finally {
    testing.value = false
  }
}

async function resetDemo() {
  await ElMessageBox.confirm('将清空所有错题/试卷/计划数据并重新导入演示数据，确定？', '重置演示数据', { type: 'warning' })
  await api.post('/demo/reset')
  ElMessage.success('已重置')
}

// 版本迭代记录（与根目录 CHANGELOG.md 保持一致）
const changelog = [
  {
    version: 'v1.5.0',
    date: '2026-10-25',
    groups: [
      {
        label: '新增',
        items: [
          '讲解答疑对话：AI 解析新增"我有疑问"入口，学生就没看懂的步骤、概念、公式自由提问，AI 口语化讲解（可引用步骤编号），保留最近 30 条对话',
          '错题按科目分类：错题本卡片按科目分组展示并新增"科目"筛选；打印重做清单与错题重测卷按科目分节、每科独立起页',
          '知识点筛选联动：新增"年级"筛选，知识点下拉由 科目×年级 共同确定，切换任一维度自动清空已选知识点',
        ],
      },
    ],
  },
  {
    version: 'v1.4.0',
    date: '2026-10-25',
    groups: [
      {
        label: '新增',
        items: [
          '知识图谱重构为四科 728 个考点级知识点（数学 173 + 物理 202 + 化学 163 + 生物 190）：新增物理（八年级~高三）、化学（九年级~高三）、生物（七年级~高三）人教版图谱，每个节点均为可独立标注错题的考点（非教材节标题），含科目内前置边与初高中衔接边；种子导入增量升级，老库无需重置',
          '数学图谱细化至 173 个知识点（高中 100 > 初中 73）：圆锥曲线按方程/性质拆分、空间向量应用按位置关系/空间角/空间距离拆分，补齐解三角形、条件概率与全概率公式、二项分布与超几何分布等整节考点',
          '图谱页 URL 直达：支持 /graph?subject=物理&grade=高二 参数，分享与演示视频可深链到任意科目×年级视图',
        ],
      },
      {
        label: '修正',
        items: [
          '错题本工具栏重排：筛选条件、游戏化徽章与操作按钮拆为两行对齐，间距统一，窄屏换行不再错位',
        ],
      },
    ],
  },
  {
    version: 'v1.3.0',
    date: '2026-10-24',
    groups: [
      {
        label: '新增',
        items: [
          '错因追问对话：与 AI 一对一回答诊断追问，证据足够时自动确认错因并修正错因分类，同步学习者画像',
          '失分题一键加入错题本：试卷详情勾选导入，自动带来源定位"试卷名+第N题"，重复导入去重',
          '游戏化激励层：复习通过庆祝卡（鼓励语+连续打卡天数）、三次通过"收服"错题、顶栏打卡与收服计数',
          '错题重测卷：本周到期复习题合成 A4 自测卷（优先变式、答题横线、得分签字栏、答案速查独立成页）',
        ],
      },
    ],
  },
  {
    version: 'v1.2.0',
    date: '2026-10-22',
    groups: [
      {
        label: '新增',
        items: [
          '知识图谱按科目（数学/物理/化学/生物）与年级两级筛选，跨年级边自动剪枝',
          '学习者画像：错因分布、高频薄弱点、考试趋势与个性化建议',
          '换种讲法：AI 按 5 种策略重讲错题，避开已用策略',
          '答案核验：重做答案交 AI 批改（数学等价算对），按证据自动记录复习',
          '知识点 AI 讲解：图谱节点一键生成迷你微课卡（导语/核心/易错/自测）',
          '知识点课型（概念/计算技能/综合应用），学习计划按课型差异化任务',
          '图谱数据完整性校验（引用存在/无环/章节非空），并入回归测试',
        ],
      },
      {
        label: '变更',
        items: ['knowledge_points 模型新增 subject（科目）与 ktype（课型）字段，老库自动迁移回填'],
      },
    ],
  },
  {
    version: 'v1.1.0',
    date: '2026-10-19',
    groups: [
      {
        label: '新增',
        items: [
          '四步教学法"举一反三"：同构填步题（关键步骤挖空）→ 基础/提高变式',
          '错因证据分级：区分"有作答证据/推测"两级，推测时自动生成诊断性追问',
          '打印视图：错题重做清单（A4、重做勾选框、订正栏）与学习计划（任务勾选框、签字栏）',
          '学习周复盘思维导图：知识点 → 错因分布 / 掌握现状 / 任务完成度',
          '示例数据升级为高一上学期（人教A版必修第一册）；知识图谱扩充至 102 个知识点（初中 72 + 高一上 30，含初高中衔接边）',
          '设置页"常见后端示例"分行排版',
        ],
      },
      {
        label: '修复',
        items: [
          '排程算法兼容 CPython list.sort() 排序期间列表置空的行为',
          '试卷日期反序列化、Windows 下测试临时库句柄释放',
        ],
      },
    ],
  },
  {
    version: 'v1.0.0',
    date: '2026-10-19',
    groups: [
      {
        label: '新增',
        items: [
          '首个可用版本：错题录入（拍照 AI 识别 / 手动）→ AI 解析 → 举一反三 → 试卷纵向进步分析 → 学习计划 五功能闭环',
          '知识图谱可视化（按掌握度着色）、练习册目录库与错题/薄弱点定位',
          'OpenAI 兼容多后端 AI 接入（智谱/通义/DeepSeek/本地 Ollama 可视化配置），未配置 Key 时分析功能离线可用',
          '人教版初中数学知识图谱数据与前置依赖边（团队自主整理，MIT 开放）',
          '9 项后端冒烟测试（pytest）',
        ],
      },
    ],
  },
]

onMounted(load)
</script>

<style scoped>
.mb12 { margin-bottom: 12px; }
.mt8 { margin-top: 8px; }
.btn-row { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.backend-examples { line-height: 2; }
.log-group { display: flex; gap: 8px; align-items: flex-start; margin-bottom: 8px; }
.log-tag { margin-top: 2px; flex-shrink: 0; }
.log-list { margin: 2px 0 0; padding-left: 4px; list-style: none; color: #606266; font-size: 13px; line-height: 1.8; }
</style>
