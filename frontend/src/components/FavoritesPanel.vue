<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  favorites,
  createFolder,
  renameFolder,
  deleteFolder,
  clearFavorites,
  removeFromFolder,
  removeFromAll,
  favoriteCount,
} from '../favorites'

const router = useRouter()
const open = ref(false)

// 当前选中的视图：'all' 或文件夹 id
const selected = ref('all')

const allCount = computed(() => favoriteCount())

const selectedFolder = computed(() => favorites.folders.find((f) => f.id === selected.value) || null)

const visibleItems = computed(() => {
  if (selected.value === 'all') {
    // 全部：按文件夹分组
    return favorites.folders.map((f) => ({ folder: f, items: f.items })).filter((g) => g.items.length)
  }
  return selectedFolder.value ? [{ folder: selectedFolder.value, items: selectedFolder.value.items }] : []
})

// 新建文件夹
const creating = ref(false)
const newName = ref('')
function confirmCreate() {
  const id = createFolder(newName.value)
  newName.value = ''
  creating.value = false
  selected.value = id
}

// 重命名
const renaming = ref(false)
const renameName = ref('')
function startRename() {
  if (!selectedFolder.value) return
  renameName.value = selectedFolder.value.name
  renaming.value = true
}
function confirmRename() {
  if (selectedFolder.value) renameFolder(selectedFolder.value.id, renameName.value)
  renaming.value = false
}

function confirmDeleteFolder() {
  const f = selectedFolder.value
  if (!f) return
  if (window.confirm(`删除文件夹「${f.name}」？其中的单词将不再作为收藏保留（其他文件夹中的收藏不受影响）。`)) {
    deleteFolder(f.id)
    selected.value = 'all'
  }
}

function go(word, folderId) {
  open.value = false
  const query = folderId ? { folder: folderId } : undefined
  router.push({ name: 'word', params: { word }, query })
}

function removeItem(word) {
  if (selected.value === 'all') {
    // 全部视图下无法确定归属文件夹，提示
    if (!window.confirm(`将「${word}」从所有收藏文件夹中移除？`)) return
    removeFromAll(word)
  } else {
    removeFromFolder(word, selected.value)
  }
}
</script>

<template>
  <button class="fav-fab" title="我的收藏" aria-label="我的收藏" @click="open = !open">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  </button>

  <Transition name="drop">
    <div v-if="open" class="fav-pop" @click.stop>
      <h3>我的收藏（{{ allCount }} 词）</h3>

      <!-- 文件夹选择 -->
      <div class="folder-bar">
        <button class="folder-chip" :class="{ active: selected === 'all' }" @click="selected = 'all'">
          全部
        </button>
        <button
          v-for="f in favorites.folders"
          :key="f.id"
          class="folder-chip"
          :class="{ active: selected === f.id }"
          @click="selected = f.id"
        >
          {{ f.name }}（{{ f.items.length }}）
        </button>
        <button class="folder-chip folder-add" title="新建文件夹" @click="creating = !creating">
          ＋
        </button>
      </div>

      <div v-if="creating" class="folder-new">
        <input v-model="newName" class="admin-input" placeholder="文件夹名称" @keydown.enter="confirmCreate" />
        <button class="btn-ghost" @click="confirmCreate">确定</button>
        <button class="btn-ghost" @click="creating = false">取消</button>
      </div>

      <div v-if="selectedFolder" class="folder-ops">
        <button class="link-btn" @click="startRename">重命名</button>
        <button class="link-btn danger" @click="confirmDeleteFolder">删除文件夹</button>
      </div>

      <div v-if="renaming" class="folder-new">
        <input v-model="renameName" class="admin-input" @keydown.enter="confirmRename" />
        <button class="btn-ghost" @click="confirmRename">确定</button>
        <button class="btn-ghost" @click="renaming = false">取消</button>
      </div>

      <!-- 单词列表 -->
      <div v-if="visibleItems.length" class="fav-list">
        <template v-for="g in visibleItems" :key="g.folder.id">
          <div v-if="selected === 'all'" class="folder-label">{{ g.folder.name }}</div>
          <div v-for="f in g.items" :key="g.folder.id + ':' + f.word" class="fav-item">
            <button class="fav-go" @click="go(f.word, g.folder.id)">
              <span class="fav-word">{{ f.word }}</span>
              <span v-if="f.pos" class="fav-pos">{{ f.pos }}</span>
              <span v-if="f.meaning" class="fav-meaning">{{ f.meaning }}</span>
            </button>
            <button class="fav-remove" title="移除" @click="removeItem(f.word)">×</button>
          </div>
        </template>
      </div>
      <p v-else class="chips-empty" style="padding: 6px 0">
        暂无收藏，进入单词详情页点击 ☆ 选择文件夹收藏
      </p>

      <div v-if="allCount" class="fav-footer">
        <button class="link-btn danger" @click="clearFavorites">清空全部</button>
      </div>
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

.folder-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.folder-chip {
  border: 1px solid rgba(31, 35, 48, 0.12);
  background: var(--surface);
  color: var(--text-soft);
  border-radius: var(--radius-full);
  padding: 4px 10px;
  font-size: 0.78rem;
  transition: background 0.12s ease, color 0.12s ease, border-color 0.12s ease;
}

.folder-chip.active {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
}

.folder-chip.folder-add {
  padding: 4px 12px;
}

.folder-new {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
}

.folder-ops {
  display: flex;
  gap: 6px;
  margin-bottom: 6px;
}

.folder-label {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--text-faint);
  margin: 10px 0 4px;
}

.fav-list {
  max-height: 300px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.fav-item {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--surface-soft);
  border-radius: var(--radius-sm);
  padding: 6px 6px 6px 12px;
}

.fav-go {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: baseline;
  gap: 8px;
  border: none;
  background: transparent;
  text-align: left;
  padding: 0;
}

.fav-word {
  font-weight: 600;
  color: var(--text);
}

.fav-pos {
  font-size: 0.72rem;
  color: var(--primary);
  font-weight: 600;
  flex: none;
}

.fav-meaning {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-soft);
  font-size: 0.78rem;
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

.fav-footer {
  margin-top: 10px;
  text-align: right;
}

.link-btn {
  border: none;
  background: transparent;
  color: var(--text-faint);
  font-size: 0.78rem;
  padding: 4px 8px;
  border-radius: var(--radius-sm);
}

.link-btn:hover {
  background: var(--surface-soft);
  color: var(--text);
}

.link-btn.danger:hover {
  color: var(--danger);
  background: #fbeaea;
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

.admin-input {
  flex: 1;
  min-width: 0;
  border: 1px solid rgba(31, 35, 48, 0.14);
  border-radius: var(--radius-sm);
  padding: 6px 10px;
  font-size: 0.82rem;
  background: var(--surface);
  color: var(--text);
}

.admin-input:focus {
  outline: none;
  border-color: var(--primary);
}
</style>
