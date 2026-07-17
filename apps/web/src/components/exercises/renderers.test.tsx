import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { ArguedResponseRenderer } from './ArguedResponseRenderer'
import { FillCodeRenderer } from './FillCodeRenderer'
import { FindErrorRenderer } from './FindErrorRenderer'
import { MultipleChoiceRenderer } from './MultipleChoiceRenderer'
import { OrderLinesRenderer } from './OrderLinesRenderer'
import { TraceVariablesRenderer } from './TraceVariablesRenderer'
import { TrueFalseRenderer } from './TrueFalseRenderer'

describe('TrueFalseRenderer', () => {
  it('emits {value: true/false} matching the backend grader contract', () => {
    const onChange = vi.fn()
    render(
      <TrueFalseRenderer
        content={{ statement: 'Un ciclo Mientras evalúa antes de ejecutar.' }}
        value={undefined}
        onChange={onChange}
      />,
    )
    fireEvent.click(screen.getByText('Verdadero'))
    expect(onChange).toHaveBeenCalledWith({ value: true })
  })
})

describe('MultipleChoiceRenderer', () => {
  it('emits {selected_index} for the clicked option', () => {
    const onChange = vi.fn()
    render(
      <MultipleChoiceRenderer
        content={{ statement: '¿Cuál operador compara igualdad?', options: ['=', '==', '<>'] }}
        value={undefined}
        onChange={onChange}
      />,
    )
    fireEvent.click(screen.getByText('=='))
    expect(onChange).toHaveBeenCalledWith({ selected_index: 1 })
  })
})

describe('FillCodeRenderer', () => {
  it('emits {values: string[]} with one entry per blank marker', () => {
    const onChange = vi.fn()
    render(
      <FillCodeRenderer
        content={{ statement: 'Completa', code_template: '___ saludar():\n    print(1)' }}
        value={undefined}
        onChange={onChange}
      />,
    )
    fireEvent.change(screen.getByLabelText('Espacio en blanco 1'), { target: { value: 'def' } })
    expect(onChange).toHaveBeenCalledWith({ values: ['def'] })
  })
})

describe('FindErrorRenderer', () => {
  it('emits {line} when a line is clicked and merges {kind} when chosen', () => {
    const onChange = vi.fn()
    const { rerender } = render(
      <FindErrorRenderer
        content={{ statement: 'Encuentra el error', code: 'Para i <- 1 Hasta 10\nEscribir i' }}
        value={undefined}
        onChange={onChange}
      />,
    )
    fireEvent.click(screen.getByText('Para i <- 1 Hasta 10'))
    expect(onChange).toHaveBeenLastCalledWith({ line: 1 })

    rerender(
      <FindErrorRenderer
        content={{ statement: 'Encuentra el error', code: 'Para i <- 1 Hasta 10\nEscribir i' }}
        value={{ line: 1 }}
        onChange={onChange}
      />,
    )
    fireEvent.click(screen.getByText('Error de sintaxis'))
    expect(onChange).toHaveBeenLastCalledWith({ line: 1, kind: 'sintaxis' })
  })
})

function ControlledTraceVariables({
  onCommit,
}: {
  onCommit: (v: { trace: Array<Record<string, unknown>> }) => void
}) {
  const [value, setValue] = useState<{ trace: Array<Record<string, unknown>> } | undefined>()
  return (
    <TraceVariablesRenderer
      content={{ statement: 'Traza contador' }}
      value={value}
      onChange={(next) => {
        setValue(next)
        onCommit(next)
      }}
    />
  )
}

describe('TraceVariablesRenderer', () => {
  it('builds a trace array of one dict per step, coercing numeric values', () => {
    const onCommit = vi.fn()
    render(<ControlledTraceVariables onCommit={onCommit} />)
    fireEvent.change(screen.getByPlaceholderText('variable'), { target: { value: 'contador' } })
    fireEvent.change(screen.getByPlaceholderText('valor'), { target: { value: '5' } })
    expect(onCommit).toHaveBeenLastCalledWith({ trace: [{ contador: 5 }] })
  })
})

describe('OrderLinesRenderer', () => {
  it('starts with the identity order over content.lines', () => {
    const onChange = vi.fn()
    render(
      <OrderLinesRenderer
        content={{ statement: 'Ordena', lines: ['def sumar(a, b):', '    return a + b'] }}
        value={undefined}
        onChange={onChange}
      />,
    )
    expect(screen.getByText('def sumar(a, b):')).toBeInTheDocument()
    expect(screen.getByText('return a + b')).toBeInTheDocument()
  })
})

describe('ArguedResponseRenderer', () => {
  it('emits {text} as the student types and shows the manual-review notice', () => {
    const onChange = vi.fn()
    render(
      <ArguedResponseRenderer
        content={{ prompt: 'Explica la recursión' }}
        value={undefined}
        onChange={onChange}
      />,
    )
    fireEvent.change(screen.getByPlaceholderText('Escribe tu respuesta...'), {
      target: { value: 'La recursión...' },
    })
    expect(onChange).toHaveBeenCalledWith({ text: 'La recursión...' })
    expect(screen.getByText(/revisa y califica tu docente/)).toBeInTheDocument()
  })
})
