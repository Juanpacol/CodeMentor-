import { StringStream } from '@codemirror/language'
import { describe, expect, it } from 'vitest'

import { pseintStreamParser } from './pseint'

function tokenize(line: string): string[] {
  const stream = new StringStream(line, 2, 4)
  const state = pseintStreamParser.startState!()
  const tokens: string[] = []
  while (!stream.eol()) {
    stream.start = stream.pos
    const token = pseintStreamParser.token(stream, state)
    if (stream.pos === stream.start) break // safety net against infinite loops
    if (token) tokens.push(token)
  }
  return tokens
}

describe('pseint CodeMirror mode', () => {
  it('recognizes keywords in Spanish', () => {
    expect(tokenize('Proceso ejemplo')).toEqual(['keyword', 'variableName'])
    expect(tokenize('FinSi')).toEqual(['keyword'])
    expect(tokenize('Mientras condicion Hacer')).toEqual([
      'keyword',
      'variableName',
      'keyword',
    ])
  })

  it('recognizes declared types', () => {
    expect(tokenize('Definir x Como Entero')).toEqual([
      'keyword',
      'variableName',
      'keyword',
      'typeName',
    ])
  })

  it('recognizes string literals', () => {
    expect(tokenize('Escribir "Hola mundo"')).toEqual(['keyword', 'string'])
  })

  it('recognizes line comments', () => {
    expect(tokenize('// esto es un comentario')).toEqual(['comment'])
  })

  it('recognizes the assignment operator and numbers', () => {
    expect(tokenize('x <- 5')).toEqual(['variableName', 'operator', 'number'])
  })

  it('recognizes boolean literals and logical operator words', () => {
    expect(tokenize('Verdadero Y Falso')).toEqual(['bool', 'operatorKeyword', 'bool'])
  })
})
