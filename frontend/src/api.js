// Thin API client. In dev, Vite proxies /api to the FastAPI backend.

const BASE = '/api'

async function request(path, options = {}) {
  const headers = { Accept: 'application/json' }
  if (options.body) headers['Content-Type'] = 'application/json'
  const res = await fetch(`${BASE}${path}`, { ...options, headers })

  if (res.status === 404) {
    const body = await res.json().catch(() => null)
    return { notFound: true, body }
  }
  if (!res.ok) {
    let detail = `请求失败（${res.status}）`
    try {
      const body = await res.json()
      if (body && body.detail) detail = body.detail
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  return { notFound: false, body: await res.json() }
}

// ---------------- 查询 ----------------

/** Autocomplete suggestions: [{word, pos, meaning}] */
export async function searchSuggest(q, limit = 8) {
  const { body } = await request(`/search?q=${encodeURIComponent(q)}&limit=${limit}`)
  return body.suggestions || []
}

/** Word detail (synonyms / similar / prev / next included) */
export async function getWord(word) {
  return request(`/word/${encodeURIComponent(word)}`)
}

/** 随机返回一个单词（可排除当前词） */
export async function getRandomWord(exclude) {
  const { body } = await request(`/random?exclude=${encodeURIComponent(exclude || '')}`)
  return body.word
}

// ---------------- 词库管理（设置 → 数据库） ----------------

export async function adminDbInfo() {
  const { body } = await request('/admin/db')
  return body
}

export async function adminStatus() {
  const { body } = await request('/admin/status')
  return body
}

export async function adminAddWord(payload) {
  const { body } = await request('/admin/words', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  return body
}

export async function adminUpdateWord(word, payload) {
  const { body } = await request(`/admin/words/${encodeURIComponent(word)}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
  return body
}

export async function adminDeleteWord(word) {
  const { body } = await request(`/admin/words/${encodeURIComponent(word)}`, {
    method: 'DELETE',
  })
  return body
}

/** 下载当前词库 CSV（带 BOM，可用 Excel 打开批量编辑） */
export async function adminExport() {
  const res = await fetch(`${BASE}/admin/export`, { headers: { Accept: 'text/csv' } })
  if (!res.ok) {
    let detail = `导出失败（${res.status}）`
    try {
      const body = await res.json()
      if (body && body.detail) detail = body.detail
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  const blob = await res.blob()
  const cd = res.headers.get('Content-Disposition') || ''
  let filename = 'vocabulary.csv'
  const star = cd.match(/filename\*=utf-8''([^;]+)/i)
  if (star) {
    try {
      filename = decodeURIComponent(star[1])
    } catch {
      /* keep default */
    }
  } else {
    const plain = cd.match(/filename="?([^";]+)"?/i)
    if (plain) filename = plain[1]
  }
  return { blob, filename }
}

/** 用 CSV 文本整体替换当前词库（旧文件自动备份 .bak） */
export async function adminImportCsv(text) {
  const res = await fetch(`${BASE}/admin/import`, {
    method: 'POST',
    headers: { 'Content-Type': 'text/csv; charset=utf-8' },
    body: text,
  })
  if (!res.ok) {
    let detail = `导入失败（${res.status}）`
    try {
      const body = await res.json()
      if (body && body.detail) detail = body.detail
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  return res.json()
}

export async function adminRebuild() {
  const { body } = await request('/admin/rebuild', { method: 'POST' })
  return body
}

// ---------------- 备注 ----------------

/** 保存 / 清除单词备注（轻量接口，不触发索引重建） */
export async function adminSaveNotes(word, notes) {
  const { body } = await request(`/admin/words/${encodeURIComponent(word)}/notes`, {
    method: 'PUT',
    body: JSON.stringify({ notes }),
  })
  return body
}

/** 所有带备注的单词：[{word, pos, meaning, notes}] */
export async function getNotes() {
  const { body } = await request('/notes')
  return body.notes || []
}
