// Static validation of the Vue frontend sources.
// - every .vue SFC: parse + compileScript + compileTemplate via @vue/compiler-sfc
// - every .js file: module-syntax check via @babel/parser
// No bundler / esbuild subprocess involved, so it works in restricted sandboxes.
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import babelParser from '@babel/parser'

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = join(__dirname, '..', 'src')

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name)
    if (statSync(p).isDirectory()) walk(p, out)
    else out.push(p)
  }
  return out
}

let failed = 0
const files = walk(root)

for (const file of files) {
  const code = readFileSync(file, 'utf8')
  if (file.endsWith('.vue')) {
    const { descriptor, errors } = parse(code, { filename: file })
    if (errors.length) {
      failed++
      console.error(`PARSE ERROR ${file}:`, errors.map((e) => e.message).join('; '))
      continue
    }
    if (descriptor.script || descriptor.scriptSetup) {
      try {
        compileScript(descriptor, { id: file })
      } catch (e) {
        failed++
        console.error(`SCRIPT ERROR ${file}:`, e.message)
      }
    }
    if (descriptor.template) {
      try {
        const { errors: tErrors } = compileTemplate({
          source: descriptor.template.content,
          filename: file,
          id: file,
        })
        if (tErrors.length) {
          failed++
          console.error(`TEMPLATE ERROR ${file}:`, tErrors.map((e) => e.message).join('; '))
        }
      } catch (e) {
        failed++
        console.error(`TEMPLATE ERROR ${file}:`, e.message)
      }
    }
    console.log(`ok .vue  ${file.replace(root, '')}`)
  } else if (file.endsWith('.js')) {
    try {
      babelParser.parse(code, { sourceType: 'module', plugins: ['importMeta'] })
      console.log(`ok .js   ${file.replace(root, '')}`)
    } catch (e) {
      failed++
      console.error(`JS ERROR ${file}:`, e.message)
    }
  }
}

if (failed) {
  console.error(`\n${failed} file(s) failed validation`)
  process.exit(1)
}
console.log(`\nAll ${files.length} source files validated OK`)
