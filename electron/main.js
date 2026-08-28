// 桌面小组件：无边框 / 透明 / 置顶（可覆盖其他应用窗口）。
// - 内置静态服务（127.0.0.1:8088）：/widget.html 小组件页、/ 完整应用、/api 代理后端
// - 小组件窗口默认按状态文件显示；web 设置页通过 /__widget__/state 远程开关
// - 窗口可自由调整大小（像浏览器窗口一样拖动边缘/角落）；打开结果面板时自动长高以容纳内容
const { app, BrowserWindow, ipcMain, screen, shell } = require('electron')
const fs = require('fs')
const path = require('path')
const { createServer } = require('./server')

const PORT = 8088
const DIST = path.join(__dirname, '..', 'frontend', 'dist')
const STATE_FILE = path.join(__dirname, 'widget-state.json')
const BAR_MIN_H = 54
const INITIAL_H = 72 // 初始高度（略大于搜索条，让内容一打开即可见）
const WIN_MAX_H = 620
const WIN_MIN_W = 240
const WIN_MAX_W = 900

// ---------------- 小组件状态持久化 ----------------
function readState() {
  try {
    const raw = fs.readFileSync(STATE_FILE, 'utf-8')
    const s = JSON.parse(raw)
    if (typeof s.enabled === 'boolean') return s
  } catch {
    /* 首次运行或文件损坏：默认启用 */
  }
  return { enabled: true }
}

function writeState(enabled) {
  try {
    fs.writeFileSync(STATE_FILE, JSON.stringify({ enabled: !!enabled }))
  } catch (e) {
    console.error('[widget] 无法写入状态文件:', e.message)
  }
}

// ---------------- 小组件窗口 ----------------
let win = null

function createWidget(showNow) {
  if (win) return win
  const wa = screen.getPrimaryDisplay().workArea
  win = new BrowserWindow({
    width: 340,
    height: INITIAL_H,
    x: wa.x + wa.width - 380,
    y: wa.y + wa.height - INITIAL_H - 90,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: true, // 自由调整大小（像浏览器窗口，拖动边缘/角落）
    minWidth: WIN_MIN_W,
    minHeight: BAR_MIN_H,
    maxWidth: WIN_MAX_W,
    maxHeight: WIN_MAX_H,
    fullscreenable: false,
    hasShadow: true,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  })

  // 详情链接交给系统默认浏览器打开主应用
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })

  win.loadURL(`http://127.0.0.1:${PORT}/widget.html`)
  win.once('ready-to-show', () => {
    if (showNow) win.show()
  })
  win.on('closed', () => {
    win = null
  })
  return win
}

function showWidget() {
  const w = createWidget(true)
  if (w && !w.isVisible()) w.show()
}

function hideWidget() {
  if (win && win.isVisible()) win.hide()
}

// ---------------- IPC：自动长高 + 关闭 ----------------
ipcMain.on('widget:resize', (_e, rect) => {
  if (!win) return
  const bounds = win.getBounds()
  // 渲染进程只报告"需要的总高度"；这里仅在需要更高时生长，
  // 不自动缩小——用户可自由拖动边缘/角落调整窗口大小，不会被程序覆盖。
  const want = Math.round(rect.height || bounds.height)
  if (want <= bounds.height) return
  const height = Math.max(BAR_MIN_H, Math.min(want, WIN_MAX_H))
  const width = Math.max(WIN_MIN_W, Math.min(bounds.width, WIN_MAX_W))
  const wa = screen.getDisplayMatching(bounds).workArea
  const spaceBelow = wa.bottom - bounds.y - height
  const spaceAbove = bounds.y - wa.y
  const growUp = spaceBelow < spaceAbove
  if (growUp) {
    // 向上生长：保持搜索条（窗口顶部）的屏幕位置不变
    const newY = Math.max(wa.y, bounds.y - (height - bounds.height))
    win.setBounds({ x: bounds.x, y: newY, width, height })
    win.webContents.send('widget:direction', 'above')
  } else {
    win.setBounds({ x: bounds.x, y: bounds.y, width, height })
    win.webContents.send('widget:direction', 'below')
  }
})

ipcMain.on('widget:close', () => {
  // 关闭按钮 = 隐藏小组件，并持久化关闭状态（设置页开关会同步）
  writeState(false)
  hideWidget()
})

// ---------------- 静态服务（含小组件控制接口） ----------------
function startServer() {
  const server = createServer({
    dist: DIST,
    apiTarget: { host: '127.0.0.1', port: 8000 },
    getWidgetState: () => readState().enabled,
    onWidgetState: (enabled) => {
      writeState(enabled)
      if (enabled) showWidget()
      else hideWidget()
    },
  })
  server.listen(PORT, '127.0.0.1')
  console.log(`[widget] static server: http://127.0.0.1:${PORT}`)
  return server
}

app.whenReady().then(() => {
  startServer()
  createWidget(readState().enabled)
})

// 隐藏/关闭小组件窗口后保持进程存活（web 设置页可随时重新开启）
app.on('window-all-closed', () => {
  /* keep alive */
})
