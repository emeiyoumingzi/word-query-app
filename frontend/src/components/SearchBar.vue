<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { searchSuggest } from '../api'
import { lookupMode } from '../lookupMode'

const props = defineProps({
  large: { type: Boolean, default: false },
  initWord: { type: String, default: '' },
})

const router = useRouter()
const rootEl = ref(null)
const inputEl = ref(null)

const q = ref(props.initWord)
const suggestions = ref([])
const open = ref(false)
const loading = ref(false)
const active = ref(-1)

const placeholder = computed(() =>
  lookupMode.value === 'cn' ? '输入中文释义，如 放弃…' : '输入英文单词，如 abandon…'
)

let timer = null
let seq = 0

watch(
  () => props.initWord,
  (v) => {
    q.value = v
    suggestions.value = []
    open.value = false
  }
)

watch(q, (v) => {
  clearTimeout(timer)
  active.value = -1
  if (!v.trim()) {
    suggestions.value = []
    open.value = false
    return
  }
  open.value = true
  loading.value = true
  const id = ++seq
  timer = setTimeout(async () => {
    try {
      const list = await searchSuggest(v.trim(), 8)
      if (id !== seq) return
      suggestions.value = list
    } catch {
      if (id === seq) suggestions.value = []
    } finally {
      if (id === seq) loading.value = false
    }
  }, 160)
})

function select(word) {
  if (!word) return
  open.value = false
  router.push({ name: 'word', params: { word } })
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
    select(pick ? pick.word : q.value.trim())
    return
  }
  if (e.key === 'Escape') {
    open.value = false
  }
}

function clear() {
  q.value = ''
  suggestions.value = []
  open.value = false
  inputEl.value?.focus()
}

function onClickOutside(e) {
  if (rootEl.value && !rootEl.value.contains(e.target)) {
    open.value = false
  }
}

onMounted(() => document.addEventListener('click', onClickOutside))
onBeforeUnmount(() => document.removeEventListener('click', onClickOutside))
</script>

<template>
  <div ref="rootEl" class="search-bar" :class="{ 'search-bar--large': large }">
    <div class="search-box">
      <span class="search-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round">
          <circle cx="11" cy="11" r="7" />
          <line x1="16.5" y1="16.5" x2="21" y2="21" />
        </svg>
      </span>

      <input
        ref="inputEl"
        v-model="q"
        class="search-input"
        type="text"
        :placeholder="placeholder"
        autocomplete="off"
        autocapitalize="off"
        autocorrect="off"
        spellcheck="false"
        @keydown="onKeydown"
      />

      <!-- 中英文查询切换 -->
      <div class="mode-toggle" role="group" aria-label="查询语言" title="切换中英文查询">
        <button :class="{ active: lookupMode === 'en' }" @click="lookupMode = 'en'">EN</button>
        <button :class="{ active: lookupMode === 'cn' }" @click="lookupMode = 'cn'">中</button>
      </div>

      <button v-if="q" class="search-clear" title="清空" @click="clear" aria-label="清空">
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round">
          <line x1="5" y1="5" x2="19" y2="19" />
          <line x1="19" y1="5" x2="5" y2="19" />
        </svg>
      </button>
    </div>

    <Transition name="drop">
      <div v-if="open && q.trim()" class="suggest-panel">
        <div v-if="loading" class="suggest-empty">正在联想…</div>
        <template v-else-if="suggestions.length">
          <button
            v-for="(s, i) in suggestions"
            :key="s.word"
            class="suggest-item"
            :class="{ 'is-active': i === active }"
            @mousedown.prevent
            @click="select(s.word)"
            @mouseenter="active = i"
          >
            <span class="suggest-word">{{ s.word }}</span>
            <span class="suggest-meta">
              <span class="pos">{{ s.pos }}</span>{{ s.meaning }}
            </span>
          </button>
        </template>
        <div v-else class="suggest-empty">未找到相关单词，回车仍可继续查询</div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.drop-enter-active,
.drop-leave-active {
  transition: opacity 0.14s ease, transform 0.14s ease;
}
.drop-enter-from,
.drop-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

/* 中英文查询切换（搜索框右侧） */
.mode-toggle {
  flex: none;
  display: inline-flex;
  border: 1px solid rgba(31, 35, 48, 0.12);
  border-radius: var(--radius-full);
  overflow: hidden;
  background: var(--surface-soft);
}

.mode-toggle button {
  border: none;
  background: transparent;
  color: var(--text-faint);
  font-size: 0.76rem;
  font-weight: 700;
  padding: 4px 11px;
  line-height: 1.2;
  transition: background 0.15s ease, color 0.15s ease;
}

.mode-toggle button.active {
  background: var(--primary);
  color: #fff;
}

.mode-toggle button:hover:not(.active) {
  color: var(--primary-deep);
}
</style>
