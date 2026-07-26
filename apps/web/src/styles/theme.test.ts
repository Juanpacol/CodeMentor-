/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

// Lee el archivo directamente del disco en vez de importarlo como módulo:
// Vitest mockea los imports de .css como vacíos por defecto (a menos que se
// habilite `test.css`), así que un `import css from './theme.css?raw'`
// devuelve una cadena vacía bajo jsdom — este archivo no pasa por ese pipeline.
const THEME_CSS_PATH = join(dirname(fileURLToPath(import.meta.url)), 'theme.css')
const css = readFileSync(THEME_CSS_PATH, 'utf-8')

// Tokens declarados en @theme static que son intencionalmente
// independientes de modo (no se duplican en los bloques [data-theme=...]).
const MODE_INDEPENDENT = new Set(['--color-on-primary'])

function extractBlock(source: string, startMarker: string): string {
  const start = source.indexOf(startMarker)
  if (start === -1) throw new Error(`No se encontró el bloque "${startMarker}" en theme.css`)
  let depth = 0
  let i = source.indexOf('{', start)
  const bodyStart = i + 1
  for (; i < source.length; i++) {
    if (source[i] === '{') depth++
    if (source[i] === '}') {
      depth--
      if (depth === 0) return source.slice(bodyStart, i)
    }
  }
  throw new Error(`Bloque "${startMarker}" sin cerrar en theme.css`)
}

function colorVarNames(blockBody: string): string[] {
  const matches = [...blockBody.matchAll(/--color-[a-z0-9-]+(?=\s*:)/g)]
  return [...new Set(matches.map((m) => m[0]))]
}

describe('theme.css — paridad claro/oscuro', () => {
  const darkDefaults = colorVarNames(extractBlock(css, '@theme static')).filter(
    (name) => !MODE_INDEPENDENT.has(name),
  )
  const lightBlock = colorVarNames(extractBlock(css, "[data-theme='light'] {"))
  const darkBlock = colorVarNames(extractBlock(css, "[data-theme='dark'] {"))

  it('no queda ningún token @theme static sin cubrir (sanity del propio test)', () => {
    expect(darkDefaults.length).toBeGreaterThan(10)
  })

  it.each(darkDefaults)('%s existe en el bloque claro', (name) => {
    expect(lightBlock).toContain(name)
  })

  it.each(darkDefaults)('%s existe en el bloque oscuro explícito (para subárboles anidados)', (name) => {
    expect(darkBlock).toContain(name)
  })
})
