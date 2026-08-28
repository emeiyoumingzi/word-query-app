<script setup>
import { ref, reactive, computed, watch, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import SearchBar from '../components/SearchBar.vue'
import Chip from '../components/Chip.vue'
import { getWord, adminSaveNotes, adminUpdateWord, getRandomWord } from '../api'
import { settings } from '../settings'
import { favorites, foldersOf, setWordFolders, createFolder, isFavorite } from '../favorites'
import { parsePhrases, buildPhrases } from '../phrases'

const props = defineProps({
  word: { type: String, required: true },
})

const router = useRouter()

const detail = ref(null)
const notFound = ref(null) // { detail, suggestions: [] }
const loading = ref(true)
let seq = 0

async function load(word) {
  const id = ++seq
  loading.value = true
  detail.value = null
  notFound.value = null
  try {
    const res = await getWord(word)
    if (id !== seq) return
    if (res.notFound) {
      notFound.value = res.body
    } else {
      detail.value = res.body
      // 中文反查（或大小写差异）命中后，路由替换为规范英文词，搜索栏同步
      const resolved = res.body.word
      if (resolved && resolved.toLowerCase() !== String(word).toLowerCase()) {
        router.replace({ name: 'word', params: { word: resolved } })
      }
    }
  } catch (e) {
    if (id === seq) {
      notFound.value = { detail: '加载失败，请稍后重试', suggestions: [] }
    }
  } finally {
    if (id === seq) loading.value = false
  }
}

watch(() => props.word, load, { immediate: true })

const inflections = () => {
  const inf = detail.value?.inflections
  if (!inf) return []
  const out = []
  if (inf.present) out.push(`现在分词 ${inf.present}`)
  if (inf.past) out.push(`过去式 ${inf.past}`)
  if (inf.past_participle) out.push(`过去分词 ${inf.past_participle}`)
  return out
}

function jump(w) {
  router.push({ name: 'word', params: { word: w } })
}

// ---------------- 左右切换单词（从收藏夹进入：文件夹内切换；否则按偏好：顺序/随机） ----------------
const route = useRoute()
const navMode = computed(() => (settings.navMode === 'random' ? 'random' : 'seq'))

// 收藏夹导航上下文：路由带 folder 参数且该文件夹存在时生效
const folderNav = computed(() => {
  const id = route.query.folder
  if (!id) return null
  const folder = favorites.folders.find((f) => f.id === id)
  if (!folder || !folder.items.length) return null
  return folder
})

const folderWords = computed(() => (folderNav.value ? folderNav.value.items.map((i) => i.word) : []))

function goFolder(step) {
  if (!detail.value) return
  const words = folderWords.value
  const idx = words.findIndex((w) => w.toLowerCase() === detail.value.word.toLowerCase())
  if (idx < 0) return
  const next = (idx + step + words.length) % words.length // 文件夹内循环切换
  router.push({ name: 'word', params: { word: words[next] }, query: { folder: folderNav.value.id } })
}

const prevDisabled = computed(() =>
  !detail.value || (!folderNav.value && navMode.value === 'seq' && !detail.value.prev)
)
const nextDisabled = computed(() =>
  !detail.value || (!folderNav.value && navMode.value === 'seq' && !detail.value.next)
)

const prevTitle = computed(() => {
  if (!detail.value) return ''
  if (folderNav.value) return `上一个（收藏夹「${folderNav.value.name}」内）`
  return navMode.value === 'random' ? '随机切换单词' : detail.value.prev ? `上一个：${detail.value.prev}` : '已是第一个单词'
})
const nextTitle = computed(() => {
  if (!detail.value) return ''
  if (folderNav.value) return `下一个（收藏夹「${folderNav.value.name}」内）`
  return navMode.value === 'random' ? '随机切换单词' : detail.value.next ? `下一个：${detail.value.next}` : '已是最后一个单词'
})

async function goRandom() {
  if (!detail.value) return
  try {
    const w = await getRandomWord(detail.value.word)
    if (w) jump(w)
  } catch {
    /* 保持当前页 */
  }
}

function goPrev() {
  if (!detail.value) return
  if (folderNav.value) {
    goFolder(-1)
  } else if (navMode.value === 'random') {
    goRandom()
  } else if (detail.value.prev) {
    jump(detail.value.prev)
  }
}

function goNext() {
  if (!detail.value) return
  if (folderNav.value) {
    goFolder(1)
  } else if (navMode.value === 'random') {
    goRandom()
  } else if (detail.value.next) {
    jump(detail.value.next)
  }
}

// ---------------- 收藏（文件夹选择） ----------------
const fav = computed(() => (detail.value ? isFavorite(detail.value.word) : false))
const favMenu = ref(false)
const checkedFolders = ref([])
const newFolderName = ref('')

function openFavMenu() {
  if (!detail.value) return
  checkedFolders.value = foldersOf(detail.value.word)
  newFolderName.value = ''
  favMenu.value = true
}

function closeFavMenu() {
  favMenu.value = false
}

function createAndCheck() {
  const name = newFolderName.value.trim()
  if (!name) return
  const id = createFolder(name)
  if (!checkedFolders.value.includes(id)) checkedFolders.value.push(id)
  newFolderName.value = ''
}

function confirmFav() {
  if (!detail.value) return
  const d = detail.value
  const first = d.pos_groups && d.pos_groups[0] ? d.pos_groups[0] : {}
  setWordFolders(d.word, checkedFolders.value, {
    pos: first.pos || '',
    meaning: first.meaning || '',
  })
  favMenu.value = false
}

function onDocumentClick(e) {
  if (favMenu.value && !e.target.closest('.fav-menu-wrap')) {
    favMenu.value = false
  }
}
watch(favMenu, (v) => {
  if (v) document.addEventListener('click', onDocumentClick)
  else document.removeEventListener('click', onDocumentClick)
})
onBeforeUnmount(() => document.removeEventListener('click', onDocumentClick))

// ---------------- 备注 ----------------
const noteText = ref('')
const noteSaving = ref(false)
const noteMsg = ref('')
const noteErr = ref('')

watch(
  () => detail.value?.notes,
  (v) => {
    noteText.value = v || ''
    noteMsg.value = ''
    noteErr.value = ''
  }
)

async function saveNote() {
  if (!detail.value) return
  noteSaving.value = true
  noteMsg.value = ''
  noteErr.value = ''
  try {
    const body = await adminSaveNotes(detail.value.word, noteText.value.trim())
    if (detail.value) detail.value.notes = noteText.value.trim()
    noteMsg.value = body.message || '已保存'
  } catch (e) {
    noteErr.value = e.message
  } finally {
    noteSaving.value = false
  }
}

// ---------------- 词组（固定搭配 · 常用词组 合并，三栏：英文/中文释义/备注） ----------------
const phraseItems = computed(() => parsePhrases(detail.value?.phrases))
const editingPhrases = ref(false)
const editItems = ref([])
const phSaving = ref(false)
const phMsg = ref('')

function enterPhraseEdit() {
  if (!detail.value) return
  const cur = parsePhrases(detail.value.phrases)
  editItems.value = cur.length ? cur.map((p) => ({ ...p })) : [{ en: '', zh: '', note: '' }]
  phMsg.value = ''
  editingPhrases.value = true
}

function cancelPhraseEdit() {
  editingPhrases.value = false
  phMsg.value = ''
}

function addPhraseRow() {
  editItems.value.push({ en: '', zh: '', note: '' })
}

function removePhraseRow(i) {
  editItems.value.splice(i, 1)
}

async function savePhrases() {
  if (!detail.value) return
  const cell = buildPhrases(editItems.value)
  const d = detail.value
  phSaving.value = true
  phMsg.value = ''
  try {
    const payload = {
      word: d.word,
      pos_groups: d.pos_groups.map((g) => ({ pos: g.pos, meaning: g.meaning })),
      inflections: {
        present: d.inflections?.present || '',
        past: d.inflections?.past || '',
        past_participle: d.inflections?.past_participle || '',
      },
      phrases: cell,
      notes: d.notes || '',
    }
    const body = await adminUpdateWord(d.word, payload)
    if (detail.value) detail.value.phrases = cell
    editingPhrases.value = false
    phMsg.value = body.message || '词组已保存'
    setTimeout(() => (phMsg.value = ''), 4000)
  } catch (e) {
    phMsg.value = '保存失败：' + e.message
  } finally {
    phSaving.value = false
  }
}
</script>

<template>
  <div>
    <!-- 顶部粘性搜索栏 -->
    <header class="sticky-header">
      <div class="sticky-inner">
        <SearchBar :init-word="word" />
      </div>
    </header>

    <main class="page-container" style="padding-top: 22px; padding-bottom: 48px">
      <!-- 加载 -->
      <div v-if="loading" class="state-block">
        <div class="spinner"></div>
        <div>正在查询「{{ word }}」…</div>
      </div>

      <!-- 未找到 -->
      <div v-else-if="notFound" class="card" style="text-align: center; padding: 40px 24px">
        <h2>未找到该词</h2>
        <p style="color: var(--text-soft)">没有收录「{{ word }}」，请检查拼写或尝试以下建议：</p>
        <div v-if="notFound.suggestions.length" class="suggest-links">
          <a
            v-for="s in notFound.suggestions"
            :key="s.word"
            href="#"
            @click.prevent="jump(s.word)"
          >
            {{ s.word }}
          </a>
        </div>
        <div v-else style="color: var(--text-faint)">暂无拼写建议</div>
      </div>

      <template v-else-if="detail">
        <!-- 词头区 -->
        <section class="card">
          <div class="headword-row">
            <h1 class="headword">{{ detail.word }}</h1>
            <span v-if="detail.phonetic" class="phonetic">{{ detail.phonetic }}</span>
            <div class="fav-menu-wrap" style="position: relative">
              <button
                class="speak-btn fav-btn"
                :class="{ active: fav }"
                :title="fav ? '已收藏，点击管理文件夹' : '收藏到文件夹'"
                :aria-label="fav ? '收藏管理' : '收藏本词'"
                @click.stop="openFavMenu"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
                </svg>
              </button>

              <!-- 收藏文件夹选择 -->
              <Transition name="drop">
                <div v-if="favMenu" class="fav-menu" @click.stop>
                  <p class="fav-menu-title">收藏到文件夹（可多选）</p>
                  <div class="fav-menu-list">
                    <label v-for="f in favorites.folders" :key="f.id" class="fav-menu-item">
                      <input v-model="checkedFolders" type="checkbox" :value="f.id" />
                      <span>{{ f.name }}（{{ f.items.length }}）</span>
                    </label>
                    <p v-if="!favorites.folders.length" class="chips-empty">还没有文件夹，先新建一个</p>
                  </div>
                  <div class="fav-menu-new">
                    <input
                      v-model="newFolderName"
                      class="fav-menu-input"
                      placeholder="新建文件夹名称"
                      @keydown.enter="createAndCheck"
                    />
                    <button class="btn-mini" @click="createAndCheck">新建</button>
                  </div>
                  <div class="fav-menu-actions">
                    <button class="btn-mini ghost" @click="closeFavMenu">取消</button>
                    <button class="btn-mini primary" @click="confirmFav">确定</button>
                  </div>
                </div>
              </Transition>
            </div>
          </div>

          <template v-if="inflections().length">
            <div class="inflections">
              <span v-for="t in inflections()" :key="t" class="infl-tag">{{ t }}</span>
            </div>
          </template>
        </section>

        <!-- 基础释义区 -->
        <section v-if="detail.pos_groups.length" class="card">
          <div class="pos-group" v-for="(g, i) in detail.pos_groups" :key="i">
            <span class="pos-badge">{{ g.pos }}</span>
            <p class="pos-meaning">{{ g.meaning }}</p>
          </div>
        </section>

        <!-- 近义词 -->
        <section class="card">
          <h2 class="card-title">近义词</h2>
          <div v-if="detail.synonyms.length" class="chips">
            <Chip v-for="s in detail.synonyms" :key="s.word" :item="s" />
          </div>
          <p v-else class="chips-empty">暂无近义词</p>
        </section>

        <!-- 形近词 -->
        <section class="card">
          <h2 class="card-title">形近词</h2>
          <div v-if="detail.similar.length" class="chips">
            <Chip v-for="s in detail.similar" :key="s.word" :item="s" />
          </div>
          <p v-else class="chips-empty">暂无形近词</p>
        </section>

        <!-- 词组（固定搭配 · 常用词组合并；铅笔内联编辑，三栏：英文 / 中文释义 / 备注） -->
        <section class="card">
          <h2 class="card-title">
            词组
            <button
              class="pencil"
              :title="editingPhrases ? '关闭编辑' : '编辑词组'"
              aria-label="编辑词组"
              @click="editingPhrases ? cancelPhraseEdit() : enterPhraseEdit()"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 20h9" />
                <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
              </svg>
            </button>
          </h2>

          <div v-if="!editingPhrases">
            <div v-if="phraseItems.length" class="phrase-list">
              <div v-for="(p, i) in phraseItems" :key="i" class="phrase-item">
                <span class="ph-en">{{ p.en }}</span>
                <span v-if="p.zh" class="ph-zh">{{ p.zh }}</span>
                <span v-if="p.note" class="ph-note">{{ p.note }}</span>
              </div>
            </div>
            <p v-else class="chips-empty">暂无词组，点击 ✎ 添加（英文 / 中文释义 / 备注）</p>
          </div>

          <div v-else class="phrase-edit">
            <div v-for="(p, i) in editItems" :key="i" class="ph-row">
              <input v-model="p.en" class="ph-input" placeholder="英文词组" />
              <input v-model="p.zh" class="ph-input" placeholder="中文释义" />
              <input v-model="p.note" class="ph-input" placeholder="备注" />
              <button class="ph-del" title="删除该词组" @click="removePhraseRow(i)">×</button>
            </div>
            <button class="ph-add" @click="addPhraseRow">＋ 添加词组</button>
            <div class="ph-actions">
              <span v-if="phMsg" class="ph-msg" :class="{ err: phMsg.startsWith('保存失败') }">{{ phMsg }}</span>
              <button class="btn-mini ghost" :disabled="phSaving" @click="cancelPhraseEdit">取消</button>
              <button class="btn-mini primary" :disabled="phSaving" @click="savePhrases">
                {{ phSaving ? '保存中…' : '保存' }}
              </button>
            </div>
            <p class="hint">保存后自动更新索引（约 30 秒），期间可正常查询。</p>
          </div>
        </section>

        <!-- 备注 -->
        <section class="card">
          <h2 class="card-title">备注</h2>
          <textarea
            v-model="noteText"
            class="note-area"
            placeholder="记录易混点、例句、记忆方法等…"
            spellcheck="false"
          ></textarea>
          <div class="note-actions">
            <span v-if="noteMsg" class="note-msg ok">{{ noteMsg }}</span>
            <span v-if="noteErr" class="note-msg err">{{ noteErr }}</span>
            <button class="note-save" :disabled="noteSaving" @click="saveNote">
              {{ noteSaving ? '保存中…' : '保存备注' }}
            </button>
          </div>
        </section>
      </template>
    </main>

    <!-- 左右切换单词 -->
    <button
      v-if="detail"
      class="nav-arrow nav-prev"
      :disabled="prevDisabled"
      :title="prevTitle"
      aria-label="上一个单词"
      @click="goPrev"
    >
      ‹
    </button>
    <button
      v-if="detail"
      class="nav-arrow nav-next"
      :disabled="nextDisabled"
      :title="nextTitle"
      aria-label="下一个单词"
      @click="goNext"
    >
      ›
    </button>
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

/* 左右切换单词 */
.nav-arrow {
  position: fixed;
  top: 50%;
  transform: translateY(-50%);
  z-index: 30;
  width: 46px;
  height: 46px;
  border: none;
  border-radius: var(--radius-full);
  background: var(--surface);
  color: var(--primary-deep);
  font-size: 30px;
  line-height: 1;
  box-shadow: var(--shadow-md);
  display: grid;
  place-items: center;
  transition: background 0.15s ease, transform 0.15s ease, opacity 0.15s ease;
  padding-bottom: 4px;
}

.nav-arrow:hover:not(:disabled) {
  background: var(--primary-soft);
  transform: translateY(-50%) scale(1.08);
}

.nav-arrow:active:not(:disabled) {
  transform: translateY(-50%) scale(0.94);
}

.nav-arrow:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.nav-prev {
  left: max(14px, calc(50vw - 440px));
}

.nav-next {
  right: max(14px, calc(50vw - 440px));
}

@media (max-width: 960px) {
  .nav-arrow {
    width: 38px;
    height: 38px;
    font-size: 24px;
  }
  .nav-prev {
    left: 8px;
  }
  .nav-next {
    right: 8px;
  }
}

@media (max-width: 560px) {
  .nav-arrow {
    width: 34px;
    height: 34px;
    font-size: 20px;
    opacity: 0.85;
  }
}

/* 收藏文件夹选择弹层 */
.fav-menu {
  position: absolute;
  top: calc(100% + 10px);
  left: 0;
  z-index: 40;
  width: 260px;
  background: var(--surface);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  padding: 14px 16px;
  animation: drop-in 0.16s ease;
}

.fav-menu-title {
  margin: 0 0 8px;
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--text);
}

.fav-menu-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 180px;
  overflow-y: auto;
}

.fav-menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.85rem;
  color: var(--text-soft);
  cursor: pointer;
}

.fav-menu-item input {
  accent-color: var(--primary);
}

.fav-menu-new {
  display: flex;
  gap: 6px;
  margin-top: 10px;
}

.fav-menu-input {
  flex: 1;
  min-width: 0;
  border: 1px solid rgba(31, 35, 48, 0.14);
  border-radius: var(--radius-sm);
  padding: 6px 10px;
  font-size: 0.8rem;
  background: var(--surface);
  color: var(--text);
}

.fav-menu-input:focus {
  outline: none;
  border-color: var(--primary);
}

.fav-menu-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
}

.btn-mini {
  border: none;
  border-radius: var(--radius-sm);
  padding: 6px 14px;
  font-size: 0.8rem;
  background: var(--surface-soft);
  color: var(--text-soft);
}

.btn-mini:hover {
  color: var(--text);
}

.btn-mini.primary {
  background: var(--primary);
  color: #fff;
}

.btn-mini.primary:hover {
  background: var(--primary-deep);
}

.btn-mini.ghost {
  border: 1px solid rgba(31, 35, 48, 0.14);
  background: var(--surface);
}

/* 备注 */
.note-area {
  width: 100%;
  min-height: 90px;
  border: 1px solid rgba(31, 35, 48, 0.14);
  border-radius: var(--radius-sm);
  padding: 10px 12px;
  font-family: inherit;
  font-size: 0.9rem;
  line-height: 1.6;
  resize: vertical;
  background: var(--surface);
  color: var(--text);
}

.note-area:focus {
  outline: none;
  border-color: var(--primary);
}

.note-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
}

.note-msg {
  font-size: 0.8rem;
}

.note-msg.ok {
  color: #1c9a4c;
}

.note-msg.err {
  color: var(--danger);
}

.note-save {
  margin-left: auto;
  border: none;
  background: var(--primary);
  color: #fff;
  border-radius: var(--radius-sm);
  padding: 8px 18px;
  font-size: 0.85rem;
}

.note-save:hover {
  background: var(--primary-deep);
}

.note-save:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* ---- 词组（三栏：英文 / 中文释义 / 备注） ---- */
.pencil {
  border: none;
  background: var(--surface-soft);
  color: var(--text-faint);
  width: 26px;
  height: 26px;
  border-radius: var(--radius-full);
  display: grid;
  place-items: center;
  transition: background 0.15s ease, color 0.15s ease, transform 0.15s ease;
}

.pencil:hover {
  background: var(--primary-soft);
  color: var(--primary-deep);
  transform: scale(1.08);
}

.pencil svg {
  width: 14px;
  height: 14px;
}

/* 词组显示：按空间自适应 1~3 行 */
.phrase-list {
  display: flex;
  flex-direction: column;
}

.phrase-item {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 2px 10px;
  padding: 8px 2px;
  border-bottom: 1px dashed rgba(31, 35, 48, 0.08);
}

.phrase-item:last-child {
  border-bottom: none;
}

.ph-en {
  font-weight: 600;
  color: var(--text);
}

.ph-zh {
  color: var(--text-soft);
}

.ph-note {
  width: 100%;
  display: flex;
  align-items: baseline;
  gap: 8px;
  color: var(--text-faint);
  font-size: 0.8rem;
}

.ph-note::before {
  content: "备注";
  flex: none;
  color: var(--text-faint);
  opacity: 0.7;
  font-size: 0.72rem;
}

/* 窄屏：英文 / 中文释义 / 备注 各占一行（最多 3 行） */
@media (max-width: 560px) {
  .ph-zh {
    width: 100%;
  }
}

/* 内联编辑 */
.phrase-edit {
  margin-top: 4px;
}

.ph-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 6px;
}

.ph-input {
  flex: 1 1 120px;
  min-width: 0;
  border: 1px solid rgba(31, 35, 48, 0.14);
  border-radius: var(--radius-sm);
  padding: 7px 10px;
  font-size: 0.84rem;
  background: var(--surface);
  color: var(--text);
}

.ph-input:focus {
  outline: none;
  border-color: var(--primary);
}

.ph-del {
  flex: none;
  border: none;
  background: transparent;
  color: var(--text-faint);
  font-size: 16px;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  line-height: 1;
}

.ph-del:hover {
  color: var(--danger);
  background: #fbeaea;
}

.ph-add {
  border: 1px dashed rgba(79, 110, 247, 0.4);
  background: var(--surface);
  color: var(--primary-deep);
  border-radius: var(--radius-sm);
  padding: 6px 14px;
  font-size: 0.82rem;
  margin-top: 2px;
}

.ph-add:hover {
  background: var(--primary-soft);
}

.ph-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 12px;
}

.ph-msg {
  margin-right: auto;
  font-size: 0.8rem;
  color: #1c9a4c;
}

.ph-msg.err {
  color: var(--danger);
}

.hint {
  margin: 8px 0 0;
  font-size: 0.72rem;
  color: var(--text-faint);
  line-height: 1.6;
}
</style>
