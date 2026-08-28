import { reactive, watch } from 'vue'

const KEY = 'word-query-settings'
const DEFAULTS = {
  fontScale: 1, // 字号：0.95 / 1 / 1.12
  widgetEnabled: false, // 网页内小组件开关
  widgetPos: null, // 网页内小组件位置 {x, y}，null 表示使用默认位置
  desktopWidgetEnabled: false, // 桌面小组件（Electron）开关镜像
  navMode: 'seq', // 详情页左右切换：'seq' 按词表顺序 | 'random' 随机
}

export const WIDGET_DEFAULT_POS = { x: 24, y: 96 }

function load() {
  try {
    const raw = localStorage.getItem(KEY)
    return raw ? { ...DEFAULTS, ...JSON.parse(raw) } : { ...DEFAULTS }
  } catch {
    return { ...DEFAULTS }
  }
}

export const settings = reactive(load())

// 设置变更自动持久化
watch(settings, persistSettings, { deep: true })

export function applyFontScale() {
  // scale the whole rem-based layout via the root font-size
  document.documentElement.style.fontSize = `${16 * settings.fontScale}px`
}

export function persistSettings() {
  try {
    localStorage.setItem(KEY, JSON.stringify(settings))
  } catch {
    /* ignore */
  }
}

export function setFontScale(value) {
  settings.fontScale = value
  applyFontScale()
  persistSettings()
}
