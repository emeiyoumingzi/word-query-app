<script setup>
import { ref, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { searchSuggest, getWord } from '../api'

// 桌面小组件：占据整个 Electron 透明窗口。
// - 窗口拖动由 Electron 的 -webkit-app-region: drag 完成（搜索条整条可拖）
// - 窗口可自由调整大小（Electron 原生，拖动边缘/角落），内容 100% 撑满窗口
// - 打开结果面板时上报"需要的高度"，主进程仅在需要更高时自动生长（不缩小、不覆盖用户调整）
// - 面板在窗口内自适应滚动，内容不会被截断
// - 无 Electron 环境（普通浏览器打开 widget.html）时退化为窗口内固定布局

const q = ref('')
const suggestions = ref([])
const loading = ref(false)
const active = ref(-1)
const result = ref(null)
const notFound = ref(null)
const panelOpen = ref(false)
const direction = ref('below') // below | above（主进程告知）
const barEl = ref(null)
const panelEl = ref(null)

let timer = null
let seq = 0

const hasShell = typeof window !== 'undefined' && !!window.widgetApi

// 上报"需要的总高度"（搜索条 + 结果面板自然高度，上限 480）
function sendSize() {
  if (!hasShell) return
  const barH = barEl.value ? barEl.value.offsetHeight : 0
  let h = barH
  if (panelOpen.value && panelEl.value) {
    h = barH + 8 + Math.min(panelEl.value.scrollHeight, 480)
  }
  window.widgetApi.resize({ height: Math.round(h) })
}

// 面板是 v-if 动态出现的：打开后建立观察并在内容变化时上报高度
let ro = null
function setupPanelObserver() {
  if (!panelEl.value || !hasShell) return
  if (ro) ro.disconnect()
  ro = new ResizeObserver(() => sendSize())
  ro.observe(panelEl.value)
}

watch(panelOpen, (v) => {
  if (v) {
    nextTick(() => {
      setupPanelObserver()
      sendSize()
    })
  } else if (ro) {
    ro.disconnect()
    ro = null
  }
})

onMounted(() => {
  if (hasShell) {
    window.widgetApi.onDirection((d) => {
      direction.value = d === 'above' ? 'above' : 'below'
    })
  }
  nextTick(sendSize)
})
onBeforeUnmount(() => ro && ro.disconnect())

watch(q, (v) => {
  clearTimeout(timer)
  active.value = -1
  if (!v.trim()) {
    suggestions.value = []
    result.value = null
    notFound.value = null
    panelOpen.value = false
    return
  }
  panelOpen.value = true
  loading.value = true
  const id = ++seq
  timer = setTimeout(async () => {
    try {
      const list = await searchSuggest(v.trim(), 6)
      if (id !== seq) return
      suggestions.value = list
    } catch {
      if (id === seq) suggestions.value = []
    } finally {
      if (id === seq) loading.value = false
    }
  }, 160)
})

async function submit(word) {
  const w = (word || q.value).trim()
  if (!w) return
  panelOpen.value = true
  loading.value = true
  const id = ++seq
  try {
    const res = await getWord(w)
    if (id !== seq) return
    if (res.notFound) {
      result.value = null
      notFound.value = res.body
    } else {
      notFound.value = null
      result.value = res.body
      q.value = res.body.word
    }
  } catch {
    if (id === seq) notFound.value = { detail: '查询失败，请检查后端服务', suggestions: [] }
  } finally {
    if (id === seq) loading.value = false
  }
}

function onKeydown(e) {
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    if (!suggestions.value.length) return
    e.preventDefault()
    const n = suggestions.value.length
    active.value = e.key === 'ArrowDown' ? (active.value + 1) % n : (active.value - 1 + n) % n
    return
  }
  if (e.key === 'Enter') {
    e.preventDefault()
    const pick = active.value >= 0 ? suggestions.value[active.value] : suggestions.value[0]
    submit(pick ? pick.word : q.value)
  }
}

function clear() {
  q.value = ''
  panelOpen.value = false
}

function goDetail(word) {
  // 在主应用（同一来源的 SPA）中打开完整详情页
  window.open(`${window.location.origin}/word/${encodeURIComponent(word)}`, '_blank')
}

function closeWidget() {
  if (hasShell) window.widgetApi.close()
  else window.close()
}
</script>

<template>
  <div ref="wrapEl" class="widget-window" :class="{ above: direction === 'above' }">
    <div v-if="!hasShell" class="dw-preview-note">
      浏览器预览模式：桌面小组件需在本地部署（Electron 壳）中运行
    </div>
    <div ref="barEl" class="dw-bar">
      <input
        v-model="q"
        class="dw-input"
        type="text"
        placeholder="查词…"
        autocomplete="off"
        autocapitalize="off"
        spellcheck="false"
        @keydown="onKeydown"
      />
      <button v-if="q" class="dw-text-btn" title="清空搜索栏" @click="clear">清空</button>
      <button class="dw-go" title="查询" @click="submit()">查</button>
      <button class="dw-icon-btn" title="隐藏小组件" @click="closeWidget">✕</button>
    </div>

    <div v-if="panelOpen" ref="panelEl" class="dw-panel">
      <div v-if="loading" class="dw-empty">查询中…</div>

      <template v-else-if="suggestions.length && !result">
        <button
          v-for="(s, i) in suggestions"
          :key="s.word"
          class="dw-sugg"
          :class="{ active: i === active }"
          @mousedown.prevent
          @click="submit(s.word)"
          @mouseenter="active = i"
        >
          <span class="dw-word">{{ s.word }}</span>
          <span class="dw-meta">{{ s.pos }} {{ s.meaning }}</span>
        </button>
      </template>

      <template v-else-if="result">
        <div class="dw-result">
          <div class="dw-head">
            <button class="dw-title" @click="goDetail(result.word)">{{ result.word }}</button>
            <a class="dw-more" href="#" @click.prevent="goDetail(result.word)">详情 ›</a>
          </div>
          <div v-for="(g, i) in result.pos_groups" :key="i" class="dw-line">
            <span class="dw-pos">{{ g.pos }}</span>
            <span class="dw-meaning">{{ g.meaning }}</span>
          </div>
          <div v-if="result.phrases" class="dw-line">
            <span class="dw-pos">词组</span>
            <span class="dw-meaning">{{ result.phrases }}</span>
          </div>
          <div v-if="result.notes" class="dw-line">
            <span class="dw-pos">备注</span>
            <span class="dw-meaning">{{ result.notes }}</span>
          </div>
        </div>
      </template>

      <div v-else-if="notFound" class="dw-empty">
        {{ notFound.detail }}
        <div v-if="notFound.suggestions.length" class="dw-suggs">
          <a v-for="s in notFound.suggestions" :key="s.word" href="#" @click.prevent="goDetail(s.word)">
            {{ s.word }}
          </a>
        </div>
      </div>
    </div>
  </div>
</template>
