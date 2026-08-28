// 查询语言模式：'en'（英文查词）| 'cn'（中文反查）。
// 持久化到 localStorage；仅用于切换联想查询的输入语言提示（占位符等）。

import { ref, watch } from 'vue'

const KEY = 'word-query-lookup-mode'

function load() {
  try {
    return localStorage.getItem(KEY) === 'cn' ? 'cn' : 'en'
  } catch {
    return 'en'
  }
}

export const lookupMode = ref(load())

watch(lookupMode, (v) => {
  try {
    localStorage.setItem(KEY, v)
  } catch {
    /* ignore */
  }
})

export function toggleLookupMode() {
  lookupMode.value = lookupMode.value === 'en' ? 'cn' : 'en'
}
