// 桌面小组件桥接：web 设置页通过本地 Electron 静态服务的控制接口，
// 远程开关桌面小组件窗口（需要 electron 壳运行在 127.0.0.1:8088）。

const BASE = 'http://127.0.0.1:8088/__widget__'

/** 读取桌面小组件当前开关状态；Electron 未运行返回 null */
export async function fetchWidgetState() {
  try {
    const res = await fetch(`${BASE}/state`, { headers: { Accept: 'application/json' } })
    if (!res.ok) return null
    return await res.json()
  } catch {
    return null
  }
}

/** 设置桌面小组件显示/隐藏；成功返回 true，Electron 未运行返回 false */
export async function setWidgetEnabled(enabled) {
  try {
    const res = await fetch(`${BASE}/state`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: !!enabled }),
    })
    return res.ok
  } catch {
    return false
  }
}
