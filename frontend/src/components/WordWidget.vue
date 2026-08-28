<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { searchSuggest, getWord } from '../api'
import { settings, WIDGET_DEFAULT_POS } from '../settings'

const router = useRouter()

// 位置（持久化）
const pos = ref(
  settings.widgetPos && settings.widgetPos.x != null
    ? { ...settings.widgetPos }
    : { ...WIDGET_DEFAULT_POS }
)
// 设置中点击"重置位置"（widgetPos 置空）时立即回到默认位置
watch(
  () => settings.widgetPos,
  (v) => {
    if (v == null) pos.value = { ...WIDGET_DEFAULT_POS }
  }
)
const winH = ref(window.innerHeight)
const winW = ref(window.innerWidth)

function onResize() {
  winH.value = window.innerHeight
  winW.value = window.innerWidth
}
onMounted(() => window.addEventListener('resize', onResize))
onBeforeUnmount(() => window.removeEventListener('resize', onResize))

// 搜索状态
const q = ref('')
const suggestions = ref([])
const loading = ref(false)
const active = ref(-1)
const result = ref(null) // 查词结果（详情）
const notFound = ref(null) // {detail, suggestions}
const panelOpen = ref(false)
let timer = null
let seq = 0

const WIDGET_H = 58

// 结果面板：空间决定显示在上方还是下方
const panelBelow = computed(() => {
  const below = winH.value - pos.value.y - WIDGET_H - 12
  return below >= pos.value.y - 12
})

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
    if (id === seq) notFound.value = { detail: '查询失败，请重试', suggestions: [] }
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
  panelOpen.value = false
  router.push({ name: 'word', params: { word } })
}

function closeWidget() {
  settings.widgetEnabled = false
}

// 拖动
function startDrag(e) {
  if (e.target.closest('input,button')) return
  e.preventDefault()
  const startX = e.clientX
  const startY = e.clientY
  const origX = pos.value.x
  const origY = pos.value.y
  const onMove = (ev) => {
    const nx = Math.min(Math.max(4, origX + (ev.clientX - startX)), Math.max(60, winW.value - 60))
    const ny = Math.min(Math.max(4, origY + (ev.clientY - startY)), Math.max(40, winH.value - 40))
    pos.value.x = Math.round(nx)
    pos.value.y = Math.round(ny)
    settings.widgetPos = { x: pos.value.x, y: pos.value.y }
  }
  const onUp = () => {
    window.removeEventListener('pointermove', onMove)
    window.removeEventListener('pointerup', onUp)
  }
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', onUp)
}
</script>

<template>
  <div class="widget" :style="{ left: pos.x + 'px', top: pos.y + 'px' }">
    <div class="widget-bar" @pointerdown="startDrag">
      <span class="widget-grip" title="拖动">⠿</span>
      <input
        v-model="q"
        class="widget-input"
        type="text"
        placeholder="查词…"
        autocomplete="off"
        autocapitalize="off"
        spellcheck="false"
        @keydown="onKeydown"
      />
      <button v-if="q" class="widget-clear" title="清空搜索栏" @click="clear">清空</button>
      <button class="widget-go" title="查询" @click="submit()">查</button>
      <button class="widget-close" title="关闭小组件" @click="closeWidget">✕</button>
    </div>

    <div v-if="panelOpen" class="widget-panel" :class="{ above: !panelBelow }">
      <div v-if="loading" class="widget-empty">查询中…</div>

      <template v-else-if="suggestions.length && !result">
        <button
          v-for="(s, i) in suggestions"
          :key="s.word"
          class="widget-sugg"
          :class="{ active: i === active }"
          @mousedown.prevent
          @click="submit(s.word)"
          @mouseenter="active = i"
        >
          <span class="ws-word">{{ s.word }}</span>
          <span class="ws-meta">{{ s.pos }} {{ s.meaning }}</span>
        </button>
      </template>

      <template v-else-if="result">
        <div class="widget-result">
          <div class="wr-head">
            <button class="wr-word" @click="goDetail(result.word)">{{ result.word }}</button>
            <a class="wr-more" href="#" @click.prevent="goDetail(result.word)">详情 ›</a>
          </div>
          <div v-for="(g, i) in result.pos_groups.slice(0, 3)" :key="i" class="wr-line">
            <span class="wr-pos">{{ g.pos }}</span>
            <span class="wr-meaning">{{ g.meaning }}</span>
          </div>
        </div>
      </template>

      <div v-else-if="notFound" class="widget-empty">
        {{ notFound.detail }}
        <div v-if="notFound.suggestions.length" class="wr-suggs">
          <a v-for="s in notFound.suggestions" :key="s.word" href="#" @click.prevent="goDetail(s.word)">
            {{ s.word }}
          </a>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.widget {
  position: fixed;
  z-index: 200;
  width: 300px;
  max-width: calc(100vw - 24px);
}

.widget-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--surface);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  border: 1.5px solid rgba(79, 110, 247, 0.35);
  padding: 6px 8px;
  cursor: grab;
}

.widget-bar:active {
  cursor: grabbing;
}

.widget-grip {
  color: var(--text-faint);
  font-size: 14px;
  user-select: none;
  line-height: 1;
}

.widget-input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  font-size: 0.95rem;
  padding: 4px 0;
  color: var(--text);
}

.widget-clear {
  flex: none;
  border: 1px solid rgba(31, 35, 48, 0.14);
  background: var(--surface);
  color: var(--text-soft);
  border-radius: var(--radius-sm);
  padding: 3px 9px;
  font-size: 0.76rem;
  white-space: nowrap;
}

.widget-clear:hover {
  border-color: var(--primary);
  color: var(--primary-deep);
}

.widget-close {
  flex: none;
  border: none;
  background: transparent;
  color: var(--text-faint);
  font-size: 15px;
  width: 22px;
  height: 22px;
  line-height: 1;
  border-radius: 50%;
}

.widget-close:hover {
  background: var(--surface-soft);
  color: var(--text);
}

.widget-go {
  flex: none;
  border: none;
  background: var(--primary);
  color: #fff;
  border-radius: var(--radius-sm);
  padding: 4px 12px;
  font-size: 0.82rem;
}

.widget-go:hover {
  background: var(--primary-deep);
}

/* 结果面板：默认在下方；空间不足自动转上方 */
.widget-panel {
  position: absolute;
  left: 0;
  right: 0;
  top: calc(100% + 10px);
  background: var(--surface);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  padding: 6px;
  max-height: 300px;
  overflow-y: auto;
  z-index: 30;
  animation: widget-drop 0.15s ease;
}

.widget-panel.above {
  top: auto;
  bottom: calc(100% + 10px);
}

@keyframes widget-drop {
  from {
    opacity: 0;
    transform: translateY(-6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.widget-panel.above {
  animation-name: widget-rise;
}

@keyframes widget-rise {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.widget-sugg {
  display: flex;
  align-items: baseline;
  gap: 8px;
  width: 100%;
  border: none;
  background: transparent;
  text-align: left;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
}

.widget-sugg:hover,
.widget-sugg.active {
  background: var(--primary-soft);
}

.ws-word {
  font-weight: 600;
  color: var(--text);
  flex: none;
}

.ws-meta {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-soft);
  font-size: 0.78rem;
}

.widget-result {
  padding: 4px 6px;
}

.wr-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}

.wr-word {
  border: none;
  background: transparent;
  font-family: var(--serif);
  font-size: 1.35rem;
  font-weight: 700;
  color: var(--text);
  padding: 0;
}

.wr-more {
  font-size: 0.78rem;
  color: var(--primary);
}

.wr-line {
  display: flex;
  gap: 8px;
  padding: 3px 0;
  font-size: 0.85rem;
  line-height: 1.5;
}

.wr-pos {
  flex: none;
  color: var(--primary-deep);
  font-weight: 700;
  font-size: 0.72rem;
  background: var(--primary-soft);
  border-radius: 6px;
  padding: 1px 7px;
  height: fit-content;
  margin-top: 2px;
}

.wr-meaning {
  color: var(--text);
}

.wr-suggs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.wr-suggs a {
  font-size: 0.85rem;
  font-weight: 600;
}

.widget-empty {
  padding: 10px;
  color: var(--text-soft);
  font-size: 0.85rem;
  text-align: center;
}
</style>
