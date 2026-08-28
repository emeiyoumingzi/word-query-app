// 小组件静态服务：静态文件（SPA 回退）+ /api 代理 + 小组件控制接口。
// 不依赖 electron，可独立测试。
const http = require('http')
const fs = require('fs')
const path = require('path')

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.ico': 'image/x-icon',
  '.woff2': 'font/woff2',
}

function json(res, status, obj) {
  const body = JSON.stringify(obj)
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Content-Length': Buffer.byteLength(body),
  })
  res.end(body)
}

function cors(res) {
  res.setHeader('Access-Control-Allow-Origin', '*')
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type')
}

/**
 * options:
 *   dist        静态目录（frontend/dist）
 *   apiTarget   { host, port } 后端地址（/api 代理目标）
 *   getWidgetState() -> boolean  返回桌面小组件是否应显示
 *   onWidgetState(enabled)       设置桌面小组件显示/隐藏
 */
function createServer({ dist, apiTarget, getWidgetState, onWidgetState }) {
  return http.createServer((req, res) => {
    const url = new URL(req.url, 'http://127.0.0.1')

    // ---- 小组件控制接口（web 设置页远程开关桌面小组件）----
    if (url.pathname === '/__widget__/state') {
      cors(res)
      if (req.method === 'OPTIONS') {
        res.writeHead(204)
        res.end()
        return
      }
      if (req.method === 'GET') {
        json(res, 200, { enabled: getWidgetState ? !!getWidgetState() : false })
        return
      }
      if (req.method === 'POST') {
        let body = ''
        req.on('data', (c) => (body += c))
        req.on('end', () => {
          try {
            const parsed = JSON.parse(body || '{}')
            const enabled = !!parsed.enabled
            if (onWidgetState) onWidgetState(enabled)
            json(res, 200, { ok: true, enabled })
          } catch {
            json(res, 400, { detail: '请求体必须是 JSON' })
          }
        })
        return
      }
      json(res, 405, { detail: 'method not allowed' })
      return
    }

    // ---- /api -> 后端代理 ----
    if (url.pathname.startsWith('/api')) {
      const proxyReq = http.request(
        {
          host: apiTarget.host,
          port: apiTarget.port,
          path: url.pathname + url.search,
          method: req.method,
          headers: req.headers,
        },
        (proxyRes) => {
          cors(res)
          res.writeHead(proxyRes.statusCode, proxyRes.headers)
          proxyRes.pipe(res)
        }
      )
      proxyReq.on('error', () => {
        json(res, 502, { detail: `后端服务未启动（${apiTarget.host}:${apiTarget.port}）` })
      })
      req.pipe(proxyReq)
      return
    }

    // ---- 静态文件 + SPA 回退 ----
    let p = decodeURIComponent(url.pathname)
    if (p === '/') p = '/index.html'
    let file = path.normalize(path.join(dist, p))
    if (!file.startsWith(dist) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
      file = path.join(dist, 'index.html') // SPA fallback
    }
    const ext = path.extname(file).toLowerCase()
    res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream' })
    fs.createReadStream(file).pipe(res)
  })
}

module.exports = { createServer }
