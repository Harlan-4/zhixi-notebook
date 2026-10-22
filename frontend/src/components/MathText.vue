<template>
  <span ref="el" class="math-text"></span>
</template>

<script setup>
// 把文本中的 $...$ 片段用 KaTeX 渲染成数学公式，其余按纯文本输出
import { onMounted, ref, watch } from 'vue'
import katex from 'katex'

const props = defineProps({ text: { type: String, default: '' } })
const el = ref(null)

function render() {
  if (!el.value) return
  el.value.innerHTML = ''
  const parts = (props.text || '').split(/(\$[^$]+\$)/g)
  for (const p of parts) {
    if (p.length > 2 && p.startsWith('$') && p.endsWith('$')) {
      const span = document.createElement('span')
      try {
        katex.render(p.slice(1, -1), span, { throwOnError: false })
      } catch {
        span.textContent = p
      }
      el.value.appendChild(span)
    } else if (p) {
      el.value.appendChild(document.createTextNode(p))
    }
  }
}

onMounted(render)
watch(() => props.text, render)
</script>
