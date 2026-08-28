<script setup>
import { ref, reactive, watch, onMounted, onBeforeUnmount } from 'vue'
import { settings, setFontScale } from '../settings'
import { isElectron, isRemoteBrowser } from '../env'
import { fetchWidgetState, setWidgetEnabled } from '../widgetBridge'
import {
  adminDbInfo,
  adminStatus,
  adminAddWord,
  adminUpdateWord,
  adminDeleteWord,
  adminRebuild,
  adminExport,
  adminImportCsv,
  getWord,
} from '../api'

// ---------------- 弹出窗口 ----------------
const open = ref(false)
const page = ref('display') // display | db | widget

function openPanel() {
  open.value = true
  refreshDbInfo()
  if (page.value === 'widget') syncDesktopWidgetToggle()
}

// 切到"桌面小组件"页时同步实际开关状态（以 Electron 状态文件为准）
watch(page, (p) => {
  if (p === 'widget') syncDesktopWidgetToggle()
})
function close() {
  open.value = false
  stopPolling()
}
function onKeydown(e) {
  if (e.key === 'Escape' && open.value) close()
}
onMounted(() => {
  document.addEventListener('keydown', onKeydown)
  refreshDbInfo()
})
onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  stopPolling()
})

// ---------------- 显示 ----------------
const FONT_OPTIONS = [
  { label: '小', value: 0.95 },
  { label: '中', value: 1 },
  { label: '大', value: 1.12 },
]

// ---------------- 网页内小组件 ----------------
function toggleWidget() {
  settings.widgetEnabled = !settings.widgetEnabled
}
function resetWidgetPos() {
  settings.widgetPos = null
}

// ---------------- 桌面小组件（Electron，远程开关） ----------------
const desktopWidgetMsg = ref('')
const desktopWidgetErr = ref('')

async function syncDesktopWidgetToggle() {
  const st = await fetchWidgetState()
  if (st) {
    settings.desktopWidgetEnabled = !!st.enabled
    desktopWidgetErr.value = ''
  }
}

async function toggleDesktopWidget() {
  const next = !settings.desktopWidgetEnabled
  desktopWidgetMsg.value = ''
  desktopWidgetErr.value = ''
  const ok = await setWidgetEnabled(next)
  if (ok) {
    settings.desktopWidgetEnabled = next
    desktopWidgetMsg.value = next ? '桌面小组件已显示' : '桌面小组件已隐藏'
  } else {
    settings.desktopWidgetEnabled = !next
    desktopWidgetErr.value = '未检测到本地 Electron 小组件服务（127.0.0.1:8088），请先运行 electron（npm start）'
  }
}

// ---------------- 词库管理 ----------------
const POS_OPTIONS = ['n.', 'v.', 'vt.', 'vi.', 'adj.', 'adv.', 'prep.', 'conj.', 'pron.', 'num.', 'art.', 'aux.', 'interj.']

const dbInfo = ref({ name: '', path: '', word_count: 0, building: false })
const mode = ref('add') // add | edit | delete
const word = ref('')
const loadedKey = ref('') // edit 模式已载入的单词（只读）
const groups = ref([{ pos: 'n.', meaning: '' }])
const inflections = reactive({ present: '', past: '', past_participle: '' })
const phrases = ref('')
const busy = ref(false)
const msg = ref('')
const err = ref('')
const fileInput = ref(null)

let pollTimer = null

async function refreshDbInfo() {
  try {
    dbInfo.value = await adminDbInfo()
  } catch (e) {
    dbInfo.value = { name: '-', path: '', word_count: 0, building: false }
    err.value = e.message
  }
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(async () => {
    try {
      const st = await adminStatus()
      dbInfo.value.building = st.building
      if (!st.building) {
        stopPolling()
        dbInfo.value.word_count = st.word_count
        msg.value = `索引更新完成，词库共 ${st.word_count} 词`
      }
    } catch {
      /* keep polling */
    }
  }, 2500)
}

function switchMode(m) {
  mode.value = m
  msg.value = ''
  err.value = ''
  if (m !== 'edit') loadedKey.value = ''
}

function addGroup() {
  if (groups.value.length < 5) groups.value.push({ pos: '', meaning: '' })
}

function removeGroup(i) {
  if (groups.value.length > 1) groups.value.splice(i, 1)
}

async function loadWordForEdit() {
  err.value = ''
  msg.value = ''
  const w = word.value.trim()
  if (!w) {
    err.value = '请先输入要修改的单词'
    return
  }
  busy.value = true
  try {
    const res = await getWord(w)
    if (res.notFound) {
      err.value = `词库中不存在：${w}`
      return
    }
    const d = res.body
    word.value = d.word
    loadedKey.value = d.word
    groups.value = d.pos_groups.length ? d.pos_groups.map((g) => ({ pos: g.pos, meaning: g.meaning })) : [{ pos: '', meaning: '' }]
    inflections.present = d.inflections?.present || ''
    inflections.past = d.inflections?.past || ''
    inflections.past_participle = d.inflections?.past_participle || ''
    phrases.value = d.phrases || ''
  } catch (e) {
    err.value = e.message
  } finally {
    busy.value = false
  }
}

function validPayload() {
  const w = word.value.trim()
  if (!w) return { ok: false, why: '请输入单词' }
  const gs = groups.value.filter((g) => g.pos.trim() && g.meaning.trim())
  if (!gs.length) return { ok: false, why: '至少需要一组词性与释义' }
  return {
    ok: true,
    payload: {
      word: w,
      pos_groups: gs.map((g) => ({ pos: g.pos.trim(), meaning: g.meaning.trim() })),
      inflections: {
        present: inflections.present.trim(),
        past: inflections.past.trim(),
        past_participle: inflections.past_participle.trim(),
      },
      phrases: phrases.value.trim(),
    },
  }
}

async function save() {
  err.value = ''
  msg.value = ''
  const v = validPayload()
  if (!v.ok) {
    err.value = v.why
    return
  }
  busy.value = true
  try {
    const body =
      mode.value === 'add'
        ? await adminAddWord(v.payload)
        : await adminUpdateWord(loadedKey.value || word.value.trim(), v.payload)
    msg.value = body.message || '已保存'
    if (body.building) {
      dbInfo.value.building = true
      startPolling()
    }
  } catch (e) {
    err.value = e.message
  } finally {
    busy.value = false
  }
}

async function remove() {
  err.value = ''
  msg.value = ''
  const w = word.value.trim()
  if (!w) {
    err.value = '请输入要删除的单词'
    return
  }
  if (!window.confirm(`确定从词库中删除单词「${w}」吗？`)) return
  busy.value = true
  try {
    const body = await adminDeleteWord(w)
    msg.value = body.message || '已删除'
    if (body.building) {
      dbInfo.value.building = true
      startPolling()
    }
    word.value = ''
  } catch (e) {
    err.value = e.message
  } finally {
    busy.value = false
  }
}

async function rebuildNow() {
  err.value = ''
  msg.value = ''
  try {
    const body = await adminRebuild()
    msg.value = body.message || '已开始更新'
    if (body.building) {
      dbInfo.value.building = true
      startPolling()
    }
  } catch (e) {
    err.value = e.message
  }
}

// ---------------- CSV 导出 / 导入替换 ----------------

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

async function doExport() {
  err.value = ''
  msg.value = ''
  try {
    const { blob, filename } = await adminExport()
    downloadBlob(blob, filename)
    msg.value = '已导出，可下载后用 Excel 批量编辑再导回'
  } catch (e) {
    err.value = e.message
  }
}

async function doImport(text, label) {
  err.value = ''
  msg.value = ''
  busy.value = true
  try {
    const body = await adminImportCsv(text)
    msg.value = body.message || '导入成功'
    if (body.building) {
      dbInfo.value.building = true
      startPolling()
    }
  } catch (e) {
    err.value = `${label}失败：${e.message}`
  } finally {
    busy.value = false
  }
}

function onFilePicked(e) {
  const file = e.target.files && e.target.files[0]
  e.target.value = ''
  if (!file) return
  if (!window.confirm(`将用「${file.name}」整体替换当前词库（旧文件自动备份为 .bak），确定继续？`)) return
  file
    .text()
    .then((text) => doImport(text, '导入'))
    .catch((e2) => {
      err.value = '读取文件失败：' + e2.message
    })
}
</script>

<template>
  <button class="settings-fab" title="设置" aria-label="设置" @click="openPanel">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
      <circle cx="12" cy="12" r="3" />
      <path
        d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h.01a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51h.01a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v.01a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"
      />
    </svg>
  </button>

  <!-- 设置弹出窗口 -->
  <Transition name="modal">
    <div v-if="open" class="modal-overlay" @click.self="close">
      <div class="settings-modal" role="dialog" aria-label="设置">
        <header class="modal-head">
          <h3>设置</h3>
          <button class="modal-close" title="关闭" aria-label="关闭" @click="close">×</button>
        </header>

        <div class="modal-body">
          <!-- 左侧导航 -->
          <nav class="modal-side">
            <button class="side-item" :class="{ active: page === 'display' }" @click="page = 'display'">显示</button>
            <button class="side-item" :class="{ active: page === 'prefs' }" @click="page = 'prefs'">偏好</button>
            <button class="side-item" :class="{ active: page === 'db' }" @click="page = 'db'">数据库 · 词库管理</button>
            <button class="side-item" :class="{ active: page === 'widget' }" @click="page = 'widget'">桌面小组件</button>
          </nav>

          <!-- 右侧内容 -->
          <div class="modal-content">
            <!-- 页面：显示 -->
            <section v-if="page === 'display'" class="page">
              <h4 class="page-title">显示</h4>
              <div class="setting-row">
                <span>字号</span>
                <div class="seg">
                  <button
                    v-for="opt in FONT_OPTIONS"
                    :key="opt.value"
                    :class="{ active: settings.fontScale === opt.value }"
                    @click="setFontScale(opt.value)"
                  >
                    {{ opt.label }}
                  </button>
                </div>
              </div>
              <p class="hint">字号设置对整个页面生效，保存在本地浏览器中。</p>
            </section>

            <!-- 页面：偏好 -->
            <section v-else-if="page === 'prefs'" class="page">
              <h4 class="page-title">偏好</h4>
              <div class="setting-row">
                <span>详情页左右切换方式</span>
                <div class="seg">
                  <button
                    :class="{ active: settings.navMode === 'seq' }"
                    @click="settings.navMode = 'seq'"
                  >
                    顺序
                  </button>
                  <button
                    :class="{ active: settings.navMode === 'random' }"
                    @click="settings.navMode = 'random'"
                  >
                    随机
                  </button>
                </div>
              </div>
              <p class="hint">
                顺序：左右箭头按词表字母顺序切换前一个 / 下一个单词（首词/末词对应方向置灰）；
                随机：左右箭头均跳转到随机单词（排除当前词）。
              </p>
              <p class="hint">偏好保存在本地浏览器中。</p>
            </section>

            <!-- 页面：数据库 · 词库管理 -->
            <section v-else-if="page === 'db'" class="page">
              <h4 class="page-title">
                数据库 · 词库管理
                <span v-if="dbInfo.building" class="db-building">
                  <span class="mini-spinner"></span>更新中…
                </span>
              </h4>

              <div class="db-info">
                <span class="db-name">{{ dbInfo.name || '—' }}</span>
                <span class="db-words">{{ dbInfo.word_count }} 词</span>
              </div>

              <div class="csv-tools">
                <button class="btn-ghost" @click="doExport">导出当前词库</button>
                <button class="btn-ghost" @click="fileInput.click()">导入 CSV 替换</button>
              </div>
              <input
                ref="fileInput"
                type="file"
                accept=".csv,text/csv"
                style="display: none"
                @change="onFilePicked"
              />

              <div class="seg" style="margin: 12px 0">
                <button :class="{ active: mode === 'add' }" @click="switchMode('add')">添加单词</button>
                <button :class="{ active: mode === 'edit' }" @click="switchMode('edit')">修改单词</button>
                <button :class="{ active: mode === 'delete' }" @click="switchMode('delete')">删除单词</button>
              </div>

              <template v-if="mode === 'add' || mode === 'edit'">
                <div class="form-row">
                  <input
                    v-model="word"
                    class="admin-input"
                    :readonly="mode === 'edit' && !!loadedKey"
                    placeholder="单词（英文字母）"
                  />
                  <button v-if="mode === 'edit'" class="btn-ghost" :disabled="busy" @click="loadWordForEdit">
                    载入
                  </button>
                </div>

                <div v-for="(g, i) in groups" :key="i" class="pos-line">
                  <input v-model="g.pos" class="admin-input admin-pos" list="pos-options" placeholder="词性" />
                  <input v-model="g.meaning" class="admin-input admin-meaning" placeholder="释义" />
                  <button class="btn-ghost btn-x" title="移除该组" @click="removeGroup(i)">×</button>
                </div>
                <datalist id="pos-options">
                  <option v-for="p in POS_OPTIONS" :key="p" :value="p" />
                </datalist>
                <button v-if="groups.length < 5" class="btn-ghost" @click="addGroup">＋ 添加一组词性（{{ groups.length }}/5）</button>

                <div class="form-row" style="margin-top: 8px">
                  <input v-model="inflections.present" class="admin-input admin-infl" placeholder="现在分词" />
                  <input v-model="inflections.past" class="admin-input admin-infl" placeholder="过去式" />
                  <input v-model="inflections.past_participle" class="admin-input admin-infl" placeholder="过去分词" />
                </div>

                <div class="form-row">
                  <input v-model="phrases" class="admin-input" placeholder="词组（英文 | 中文释义 | 备注；多个用；隔开）" />
                </div>

                <button class="btn-primary" :disabled="busy" @click="save">
                  {{ busy ? '处理中…' : mode === 'add' ? '保存并更新索引' : '保存修改并更新索引' }}
                </button>
              </template>

              <template v-else>
                <div class="form-row">
                  <input v-model="word" class="admin-input" placeholder="要删除的单词" />
                  <button class="btn-danger" :disabled="busy" @click="remove">删除</button>
                </div>
              </template>

              <p v-if="err" class="admin-msg admin-err">{{ err }}</p>
              <p v-else-if="msg" class="admin-msg admin-ok">{{ msg }}</p>

              <button class="btn-ghost" style="margin-top: 12px" :disabled="dbInfo.building" @click="rebuildNow">
                手动更新索引
              </button>
              <p class="hint">增删改或导入后会自动触发一次索引更新（约 30 秒），期间可正常查询旧数据。</p>
            </section>

            <!-- 页面：桌面小组件 -->
            <section v-else class="page">
              <h4 class="page-title">桌面小组件</h4>

              <!-- 环境状态 -->
              <div class="env-banner" :class="{ ok: isElectron, warn: !isElectron }">
                <template v-if="isElectron">
                  ✓ 运行环境：本地部署（Electron 壳）——桌面小组件功能可用
                </template>
                <template v-else-if="isRemoteBrowser">
                  ✕ 运行环境：远程部署（浏览器访问）——桌面小组件功能已禁用
                </template>
                <template v-else>
                  ✕ 运行环境：浏览器（本机访问）——桌面小组件需配合本地 Electron 运行
                </template>
              </div>

              <!-- 桌面小组件（Electron，远程开关） -->
              <div class="setting-row">
                <span>桌面小组件（可显示在其他应用窗口之上）</span>
                <button
                  class="switch"
                  :class="{ on: settings.desktopWidgetEnabled }"
                  role="switch"
                  :aria-checked="settings.desktopWidgetEnabled"
                  @click="toggleDesktopWidget"
                />
              </div>
              <p v-if="desktopWidgetErr" class="admin-msg admin-err">{{ desktopWidgetErr }}</p>
              <p v-else-if="desktopWidgetMsg" class="admin-msg admin-ok">{{ desktopWidgetMsg }}</p>
              <p class="hint">
                开启/关闭会直接控制 Electron 小组件窗口的显示与隐藏（需本地已运行
                <code>electron</code> 壳，即 <code>npm start</code>；首次运行默认显示）。
                小组件无边框透明置顶，按住搜索条可拖动，结果面板按屏幕空间自动显示在搜索条上方或下方，
                支持 ± 缩放。
              </p>

              <hr class="sep" />

              <!-- 网页内小组件（浏览器 / 本地部署均可用） -->
              <div class="setting-row">
                <span>网页内小组件</span>
                <button
                  class="switch"
                  :class="{ on: settings.widgetEnabled }"
                  role="switch"
                  :aria-checked="settings.widgetEnabled"
                  @click="toggleWidget"
                />
              </div>
              <p class="hint">
                在页面内显示的浮动查词栏：输入单词/中文查词，结果面板按位置自动显示在上方或下方，
                位置可拖动并自动保存；浏览器与本地部署环境均可使用。
              </p>
              <button v-if="settings.widgetEnabled" class="btn-ghost" style="margin-top: 4px" @click="resetWidgetPos">
                重置网页小组件位置
              </button>
            </section>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.18s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

/* 弹出窗口 */
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 150;
  background: rgba(23, 26, 38, 0.45);
  backdrop-filter: blur(3px);
  display: grid;
  place-items: center;
  padding: 16px;
}

.settings-modal {
  width: min(740px, 100%);
  height: min(600px, calc(100vh - 48px));
  background: var(--surface);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 22px;
  border-bottom: 1px solid rgba(31, 35, 48, 0.08);
}

.modal-head h3 {
  margin: 0;
  font-size: 1.05rem;
}

.modal-close {
  border: none;
  background: var(--surface-soft);
  color: var(--text-soft);
  width: 32px;
  height: 32px;
  border-radius: 50%;
  font-size: 18px;
  line-height: 1;
}

.modal-close:hover {
  background: #e3e6f0;
  color: var(--text);
}

.modal-body {
  flex: 1;
  display: flex;
  min-height: 0;
}

/* 左侧导航 */
.modal-side {
  width: 172px;
  flex: none;
  border-right: 1px solid rgba(31, 35, 48, 0.08);
  padding: 14px 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  overflow-y: auto;
}

.side-item {
  border: none;
  background: transparent;
  text-align: left;
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  font-size: 0.9rem;
  color: var(--text-soft);
  transition: background 0.12s ease, color 0.12s ease;
}

.side-item:hover {
  background: var(--surface-soft);
  color: var(--text);
}

.side-item.active {
  background: var(--primary-soft);
  color: var(--primary-deep);
  font-weight: 600;
}

/* 右侧内容 */
.modal-content {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  padding: 20px 24px;
}

.page-title {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 0 14px;
  font-size: 1rem;
}

/* ---- 词库管理表单 ---- */
.db-info {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 0.85rem;
  color: var(--text-soft);
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.db-name {
  font-weight: 600;
  color: var(--text);
}

.db-building {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--primary-deep);
  font-size: 0.78rem;
}

.mini-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid var(--primary-soft);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.csv-tools {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 4px;
}

.form-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}

.admin-input {
  flex: 1;
  min-width: 0;
  border: 1px solid rgba(31, 35, 48, 0.14);
  border-radius: var(--radius-sm);
  padding: 7px 10px;
  font-size: 0.85rem;
  background: var(--surface);
  color: var(--text);
}

.admin-input:focus {
  outline: none;
  border-color: var(--primary);
}

.admin-input[readonly] {
  background: var(--surface-soft);
  color: var(--text-soft);
}

.pos-line {
  display: flex;
  gap: 6px;
  margin-bottom: 6px;
}

.admin-pos {
  flex: 0 0 74px;
}

.admin-meaning {
  flex: 1;
}

.admin-infl {
  flex: 1;
}

.btn-primary {
  margin-top: 4px;
  width: 100%;
  border: none;
  background: var(--primary);
  color: #fff;
  border-radius: var(--radius-sm);
  padding: 9px 0;
  font-size: 0.88rem;
  transition: background 0.15s ease;
}

.btn-primary:hover {
  background: var(--primary-deep);
}

.btn-primary:disabled,
.btn-ghost:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.btn-ghost {
  border: 1px solid rgba(31, 35, 48, 0.14);
  background: var(--surface);
  color: var(--text-soft);
  border-radius: var(--radius-sm);
  padding: 6px 12px;
  font-size: 0.82rem;
  white-space: nowrap;
}

.btn-ghost:hover {
  border-color: var(--primary);
  color: var(--primary-deep);
}

.btn-x {
  padding: 6px 9px;
  line-height: 1;
}

.btn-danger {
  border: none;
  background: var(--danger);
  color: #fff;
  border-radius: var(--radius-sm);
  padding: 8px 16px;
  font-size: 0.85rem;
  white-space: nowrap;
}

.btn-danger:hover {
  opacity: 0.9;
}

.admin-msg {
  margin: 10px 0 0;
  font-size: 0.82rem;
}

.admin-ok {
  color: #1c9a4c;
}

.admin-err {
  color: var(--danger);
}

.hint {
  margin: 8px 0 0;
  font-size: 0.72rem;
  color: var(--text-faint);
  line-height: 1.6;
}

.hint code {
  background: var(--surface-soft);
  padding: 1px 6px;
  border-radius: 6px;
  font-size: 0.7rem;
}

.sep {
  border: none;
  border-top: 1px solid rgba(31, 35, 48, 0.08);
  margin: 16px 0 10px;
}

/* 环境状态 */
.env-banner {
  border-radius: var(--radius-sm);
  padding: 9px 12px;
  font-size: 0.82rem;
  margin-bottom: 14px;
  line-height: 1.5;
}

.env-banner.ok {
  background: #e7f6ec;
  color: #1c7a42;
}

.env-banner.warn {
  background: #fdf3e3;
  color: #9a6a15;
}

.setting-row.muted {
  opacity: 0.55;
}

.env-badge {
  flex: none;
  font-size: 0.74rem;
  font-weight: 700;
  border-radius: var(--radius-full);
  padding: 2px 10px;
}

.env-badge.on {
  background: #e7f6ec;
  color: #1c7a42;
}

.env-badge.off {
  background: var(--surface-soft);
  color: var(--text-faint);
}

/* 移动端：侧栏变顶部标签 */
@media (max-width: 560px) {
  .modal-body {
    flex-direction: column;
  }

  .modal-side {
    width: 100%;
    flex-direction: row;
    border-right: none;
    border-bottom: 1px solid rgba(31, 35, 48, 0.08);
    padding: 8px;
    overflow-x: auto;
  }

  .side-item {
    white-space: nowrap;
    padding: 8px 12px;
  }

  .modal-content {
    padding: 16px;
  }
}
</style>
