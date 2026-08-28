// 收藏功能 v2：支持分文件夹收藏，一个单词可同时加入多个文件夹。
// 结构：{ folders: [{ id, name, items: [{word, pos, meaning}] }] }
// 持久化到 localStorage（旧版扁平列表自动迁移到"默认收藏"文件夹）。
// "翻译高频词汇"为预设收藏夹：仅在首次加载时补齐全部 312 个预设单词，
// 之后用户的增删完全保留，预设不再干预。

import { reactive, watch } from 'vue'
import { FAVORITES_SEED, FAVORITES_SEED_FOLDER } from './favorites-seed'

const KEY = 'word-query-favorites'
// 预设收藏夹的补齐标记：标记不存在时补齐一次，之后增删完全由用户保留
const SEED_MARKER = 'word-query-favorites-seed-v4'

// 预设收藏夹补齐（自愈式）：
// - 文件夹不存在（首次加载 / 数据异常丢失）→ 创建并放入全部 312 个预设词
// - 文件夹已存在 → 永不干预（用户增删完全保留），仅在缺标记时补写标记
function applySeed(folders) {
  try {
    if (!Array.isArray(FAVORITES_SEED) || !FAVORITES_SEED.length) return folders
    const hasMarker = !!localStorage.getItem(SEED_MARKER)
    let folder = folders.find((f) => f.name === FAVORITES_SEED_FOLDER)
    if (hasMarker && folder) return folders // 已补齐且文件夹存在 → 不再干预
    if (folder) {
      // 文件夹存在但缺标记（异常状态）→ 仅补标记，不补词
      try {
        localStorage.setItem(SEED_MARKER, '1')
      } catch {
        /* ignore */
      }
      return folders
    }
    // 文件夹缺失 → 创建并放入全部预设词
    folders.push({
      id: 'seed' + Date.now(),
      name: FAVORITES_SEED_FOLDER,
      items: FAVORITES_SEED.map((i) => ({ word: i.word, pos: i.pos || '', meaning: i.meaning || '' })),
    })
    try {
      localStorage.setItem(SEED_MARKER, '1')
    } catch {
      /* ignore */
    }
  } catch {
    /* ignore */
  }
  return folders
}

// 清理历史残留（旧版种子标记），不影响当前逻辑
try {
  localStorage.removeItem('word-query-favorites-seed-v1')
} catch {
  /* ignore */
}

function load() {
  let folders = []
  try {
    const raw = localStorage.getItem(KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) {
        // 旧版扁平列表 -> 迁移
        folders = [{ id: 'default', name: '默认收藏', items: parsed }]
      } else if (parsed && Array.isArray(parsed.folders)) {
        folders = parsed.folders
      }
    }
  } catch {
    folders = []
  }
  return { folders: applySeed(folders) }
}

export const favorites = reactive(load())

// 立即持久化：加载/预设后的状态马上写入 localStorage，
// 否则（无任何交互变更时）刷新会丢失内存中的收藏数据
function persistFavorites() {
  try {
    localStorage.setItem(KEY, JSON.stringify(favorites))
  } catch {
    /* ignore */
  }
}
persistFavorites()

watch(favorites, persistFavorites, { deep: true })

let idSeq = Date.now()

// ---------------- 文件夹 ----------------
export function createFolder(name) {
  const n = (name || '').trim() || '新建文件夹'
  const folder = { id: 'f' + idSeq++, name: n, items: [] }
  favorites.folders.push(folder)
  return folder.id
}

export function renameFolder(id, name) {
  const f = favorites.folders.find((x) => x.id === id)
  if (f && (name || '').trim()) f.name = name.trim()
}

export function deleteFolder(id) {
  const idx = favorites.folders.findIndex((x) => x.id === id)
  if (idx >= 0) favorites.folders.splice(idx, 1)
}

export function clearFavorites() {
  favorites.folders = []
}

// ---------------- 单词 ----------------
const norm = (w) => (w || '').toLowerCase()

export function isFavorite(word) {
  const w = norm(word)
  return favorites.folders.some((f) => f.items.some((i) => norm(i.word) === w))
}

/** 该单词所在的文件夹 id 列表 */
export function foldersOf(word) {
  const w = norm(word)
  const out = []
  for (const f of favorites.folders) {
    if (f.items.some((i) => norm(i.word) === w)) out.push(f.id)
  }
  return out
}

/** 设定单词的文件夹归属（多选替换式）：meta 用于新加入时的展示信息 */
export function setWordFolders(word, folderIds, meta) {
  const w = norm(word)
  const want = new Set(folderIds)
  for (const f of favorites.folders) {
    const has = f.items.some((i) => norm(i.word) === w)
    if (want.has(f.id)) {
      if (!has) f.items.push({ word, pos: meta?.pos || '', meaning: meta?.meaning || '' })
    } else if (has) {
      f.items = f.items.filter((i) => norm(i.word) !== w)
    }
  }
}

export function addToFolder(word, folderId, meta) {
  const f = favorites.folders.find((x) => x.id === folderId)
  if (!f) return
  if (!f.items.some((i) => norm(i.word) === norm(word))) {
    f.items.push({ word, pos: meta?.pos || '', meaning: meta?.meaning || '' })
  }
}

export function removeFromFolder(word, folderId) {
  const f = favorites.folders.find((x) => x.id === folderId)
  if (!f) return
  f.items = f.items.filter((i) => norm(i.word) !== norm(word))
}

export function removeFromAll(word) {
  const w = norm(word)
  for (const f of favorites.folders) {
    f.items = f.items.filter((i) => norm(i.word) !== w)
  }
}

export function favoriteCount() {
  const seen = new Set()
  for (const f of favorites.folders) {
    for (const i of f.items) seen.add(norm(i.word))
  }
  return seen.size
}
