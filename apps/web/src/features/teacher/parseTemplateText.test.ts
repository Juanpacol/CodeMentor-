import { describe, expect, it } from 'vitest'

import { parseTemplateText } from './parseTemplateText'

describe('parseTemplateText', () => {
  it('returns nothing for empty input', () => {
    expect(parseTemplateText('   \n  ')).toEqual([])
  })

  it('splits on markdown headings and keeps the body as instructions', () => {
    const parsed = parseTemplateText(
      ['# Introducción', 'Contextualiza el tema.', '', '## Objetivos', 'Uno general.'].join('\n'),
    )
    expect(parsed).toEqual([
      { heading: 'Introducción', instructions: 'Contextualiza el tema.' },
      { heading: 'Objetivos', instructions: 'Uno general.' },
    ])
  })

  it('drops the document title that precedes the first heading', () => {
    // Si no, cada plantilla pegada arranca con una fila basura que el docente
    // tiene que borrar a mano.
    const parsed = parseTemplateText(
      ['FORMATO DE GUÍA', '', '## Introducción', 'Contextualiza.'].join('\n'),
    )
    expect(parsed).toHaveLength(1)
    expect(parsed[0].heading).toBe('Introducción')
  })

  it('falls back to blank-line blocks when there are no markdown headings', () => {
    // La forma real de un formato institucional pegado desde Word.
    const parsed = parseTemplateText(
      [
        'Datos generales',
        'Asignatura, Grado, Docente, Tema, Duración y Fecha.',
        '',
        'Ejemplo resuelto paso a paso',
        '1. Planteamiento.',
        '2. Análisis.',
      ].join('\n'),
    )
    expect(parsed).toEqual([
      {
        heading: 'Datos generales',
        instructions: 'Asignatura, Grado, Docente, Tema, Duración y Fecha.',
      },
      {
        heading: 'Ejemplo resuelto paso a paso',
        instructions: '1. Planteamiento.\n2. Análisis.',
      },
    ])
  })

  it('strips bullets and numbering that Word leaves on the heading', () => {
    const parsed = parseTemplateText('• Objetivos\nUno general y dos específicos.')
    expect(parsed[0].heading).toBe('Objetivos')
  })

  it('keeps a heading with no body so the teacher can fill it in', () => {
    // Descartarla escondería una sección que el docente sí pidió.
    const parsed = parseTemplateText('## Datos generales\n\n## Introducción\nContextualiza.')
    expect(parsed.map((s) => s.heading)).toEqual(['Datos generales', 'Introducción'])
    expect(parsed[0].instructions).toBe('')
  })

  it('normalises CRLF from files pasted or uploaded from Windows', () => {
    const parsed = parseTemplateText('## Introducción\r\nContextualiza el tema.')
    expect(parsed).toEqual([{ heading: 'Introducción', instructions: 'Contextualiza el tema.' }])
  })

  it('truncates to the lengths the backend accepts', () => {
    const parsed = parseTemplateText(`## ${'t'.repeat(300)}\n${'i'.repeat(1500)}`)
    expect(parsed[0].heading).toHaveLength(200)
    expect(parsed[0].instructions).toHaveLength(1000)
  })
})
