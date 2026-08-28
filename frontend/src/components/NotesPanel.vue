<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { getNotes, adminSaveNotes } from '../api'

const router = useRouter()
const open = ref(false)
const items = ref([])
const loading = ref(false)
const err = ref('')

async function refresh() {
  loading.value = true
  err.value = ''
  try {
    items.value = await getNotes()
  } catch (e) {
    err.value = e.message
  } finally {
    loading.value = false
  }
}

function toggle() {
  open.value = !open.value
  if (open.value) refresh()
}

function go(word) {
  open.value = false
  router.push({ name: 'word', params: { word } })
}

async function clearNote(word) {
  if (!window.confirm(`清除「${word}」的备注？`)) return
  try {
    await adminSaveNotes(word, '')
    await refresh()
  } catch (e) {
    err.value = e.message
  }
}
</script>

<template>
  <button class="notes-fab" title="单词备注" aria-label="单词备注" @click="toggle">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
    </svg>
  </button>

  <Transition name="drop">
    <div v-if="open" class="notes-pop" @click.stop>
      <h3>单词备注（{{ items.length }}）</h3>

      <div v-if="loading" class="chips-empty" style="padding: 8px 0">加载中…</div>
      <p v-else-if="err" class="admin-err">{{ err }}</p>

      <div v-else-if="items.length" class="notes-list">
        <div v-for="n in items" :key="n.word" class="note-item">
          <button class="note-go" @click="go(n.word)">
            <span class="note-head">
              <span class="fav-word">{{ n.word }}</span>
              <span v-if="n.pos" class="fav-pos">{{ n.pos }}</span>
            </span>
            <span class="note-text">{{ n.notes }}</span>
          </button>
          <button class="fav-remove" title="清除备注" @click="clearNote(n.word)">×</button>
        </div>
      </div>
      <p v-else class="chips-empty" style="padding: 6px 0">
        暂无备注，在单词详情页底部可添加备注
      </p>
    </div>
  </Transition>
</template>

<style scoped>
.drop-enter-active,
.drop-leave-active {
  transition: opacity 0.14s ease, transform 0.14s ease;
}
.drop-enter-from,
.drop-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

.notes-list {
  max-height: 300px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.note-item {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--surface-soft);
  border-radius: var(--radius-sm);
  padding: 8px 6px 8px 12px;
}

.note-go {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  border: none;
  background: transparent;
  text-align: left;
  padding: 0;
}

.note-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.fav-word {
  font-weight: 600;
  color: var(--text);
}

.fav-pos {
  font-size: 0.72rem;
  color: var(--primary);
  font-weight: 600;
}

.note-text {
  color: var(--text-soft);
  font-size: 0.8rem;
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.fav-remove {
  flex: none;
  border: none;
  background: transparent;
  color: var(--text-faint);
  font-size: 16px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  line-height: 1;
}

.fav-remove:hover {
  color: var(--danger);
  background: #fbeaea;
}

.admin-err {
  color: var(--danger);
  font-size: 0.82rem;
  margin: 6px 0;
}
</style>
