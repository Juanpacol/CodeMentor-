import { StreamLanguage } from '@codemirror/language'
import type { StringStream } from '@codemirror/language'

// RF-26: modo de resaltado propio para el subconjunto de PSeInt en español
// que enseña el docente. No existe un paquete de CodeMirror para esto —
// es una gramática de un solo colegio, así que un StreamParser (estilo
// CodeMirror 5) es más simple que escribir una gramática Lezer completa.
const KEYWORDS = new Set(
  [
    'Proceso',
    'FinProceso',
    'Algoritmo',
    'FinAlgoritmo',
    'Si',
    'Entonces',
    'Sino',
    'FinSi',
    'Mientras',
    'Hacer',
    'FinMientras',
    'Para',
    'Hasta',
    'Con Paso',
    'FinPara',
    'Repetir',
    'Segun',
    'FinSegun',
    'Definir',
    'Como',
    'Dimension',
    'SubProceso',
    'FinSubProceso',
    'Escribir',
    'Leer',
  ].map((kw) => kw.toLowerCase()),
)

const TYPES = new Set(['entero', 'real', 'caracter', 'logico', 'cadena'])
const BOOLEANS = new Set(['verdadero', 'falso'])
const OPERATOR_WORDS = new Set(['y', 'o', 'no', 'mod'])

interface PseIntState {
  inComment: boolean
}

function readIdentifier(stream: StringStream): string {
  stream.eatWhile(/[A-Za-zÀ-ÿ0-9_]/)
  return stream.current()
}

export const pseintStreamParser = {
  name: 'pseint',
  startState(): PseIntState {
    return { inComment: false }
  },
  token(stream: StringStream, _state: PseIntState): string | null {
    if (stream.eatSpace()) return null

    if (stream.match('//')) {
      stream.skipToEnd()
      return 'comment'
    }

    if (stream.match('"')) {
      while (!stream.eol()) {
        const next = stream.next()
        if (next === '"') break
      }
      return 'string'
    }

    if (stream.match('<-') || stream.match(/^[+\-*/%<>=]+/)) {
      return 'operator'
    }

    if (/\d/.test(stream.peek() ?? '')) {
      stream.eatWhile(/[\d.]/)
      return 'number'
    }

    if (/[A-Za-zÀ-ÿ_]/.test(stream.peek() ?? '')) {
      const word = readIdentifier(stream).toLowerCase()
      if (KEYWORDS.has(word)) return 'keyword'
      if (TYPES.has(word)) return 'typeName'
      if (BOOLEANS.has(word)) return 'bool'
      if (OPERATOR_WORDS.has(word)) return 'operatorKeyword'
      return 'variableName'
    }

    stream.next()
    return null
  },
  languageData: {
    commentTokens: { line: '//' },
  },
}

export const pseintLanguage = StreamLanguage.define(pseintStreamParser)
