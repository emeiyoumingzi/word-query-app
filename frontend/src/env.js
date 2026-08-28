// 运行环境检测
// - Electron 壳（本地部署的桌面应用）：preload 注入了 window.widgetApi，且 UA 含 "Electron"
// - 浏览器：无 widgetApi；再区分本机访问（localhost）与远程部署（hosted）
const ua = typeof navigator !== 'undefined' ? navigator.userAgent : ''
const host = typeof window !== 'undefined' ? window.location.hostname : ''

/** 是否运行在本地部署的 Electron 桌面壳中（唯一能实现"置顶悬浮在其他应用窗口之上"的环境） */
export const isElectron = (typeof window !== 'undefined' && !!window.widgetApi) || ua.includes('Electron')

/** 是否本机部署（浏览器访问 localhost） */
export const isLocalHost = isElectron || ['localhost', '127.0.0.1', '::1', ''].includes(host)

/** 是否纯浏览器环境（网页中，未运行桌面壳） */
export const isBrowser = !isElectron

/** 是否远程部署（托管在非本机地址） */
export const isRemoteBrowser = !isElectron && !isLocalHost
