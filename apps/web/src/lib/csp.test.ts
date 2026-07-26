/// <reference types="node" />
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

// El script inline de arranque de index.html necesita su hash en la CSP de
// vercel.json (script-src). Sin este test, editar el script sin recalcular
// el hash desincroniza ambos archivos en silencio — el navegador bloquearía
// el script en producción, dejando el toggle de tema sin aplicar antes del
// primer pintado (vuelve el flash que el script existe para evitar).
const WEB_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..')

describe('CSP — hash del script inline de arranque', () => {
  it('el hash en vercel.json corresponde al contenido actual del script en index.html', () => {
    const html = readFileSync(join(WEB_ROOT, 'index.html'), 'utf-8')
    const match = html.match(/<script>([\s\S]*?)<\/script>/)
    expect(match, 'no se encontró el <script> inline en index.html').not.toBeNull()

    const inlineScript = match![1]
    const hash = createHash('sha256').update(inlineScript, 'utf-8').digest('base64')

    const vercelConfig = JSON.parse(readFileSync(join(WEB_ROOT, 'vercel.json'), 'utf-8')) as {
      headers: { headers: { key: string; value: string }[] }[]
    }
    const csp = vercelConfig.headers
      .flatMap((h) => h.headers)
      .find((h) => h.key === 'Content-Security-Policy')?.value

    expect(csp, 'no se encontró Content-Security-Policy en vercel.json').toBeDefined()
    expect(csp).toContain(`'sha256-${hash}'`)
  })
})
