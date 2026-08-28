// 词组编码规则（CSV「词组」列）：
// - 多个词组用 "；" 分隔
// - 每个词组为 "英文 | 中文释义 | 备注"（英文必填，中文释义/备注可空）
// 与详情页内联编辑、词库管理表单共用。

export function parsePhrases(cell) {
  if (!cell) return []
  return cell
    .split('；')
    .map((s) => {
      const parts = s.split('|').map((p) => p.trim())
      return { en: parts[0] || '', zh: parts[1] || '', note: parts[2] || '' }
    })
    .filter((p) => p.en)
}

export function buildPhrases(items) {
  return items
    .map((p) => {
      const en = (p.en || '').trim()
      const zh = (p.zh || '').trim()
      const note = (p.note || '').trim()
      if (!en) return null
      if (zh && note) return `${en} | ${zh} | ${note}`
      if (zh) return `${en} | ${zh}`
      if (note) return `${en} |  | ${note}`
      return en
    })
    .filter(Boolean)
    .join('；')
}
