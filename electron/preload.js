// 安全预加载：向小组件页面暴露最小化 IPC 接口
const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('widgetApi', {
  /** 请求主进程调整窗口大小（高度按屏幕空间自动向上/向下生长） */
  resize: (rect) => ipcRenderer.send('widget:resize', rect),
  /** 主进程告知面板应显示在上方还是下方 */
  onDirection: (cb) => ipcRenderer.on('widget:direction', (_e, d) => cb(d)),
  /** 关闭小组件窗口 */
  close: () => ipcRenderer.send('widget:close'),
})
