import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { ExerciseContentForm } from './ExerciseContentForm'
import type { ExerciseType } from '../../components/exercises/registry'

function Controlled({ type, onCommit }: { type: ExerciseType; onCommit: (v: object) => void }) {
  const [value, setValue] = useState<Record<string, unknown>>({})
  return (
    <ExerciseContentForm
      type={type}
      value={value}
      onChange={(next) => {
        setValue(next)
        onCommit(next)
      }}
    />
  )
}

describe('ExerciseContentForm', () => {
  it('true_false: toggling the checkbox sets answer', () => {
    const onCommit = vi.fn()
    render(<Controlled type="true_false" onCommit={onCommit} />)
    fireEvent.click(screen.getByLabelText('El enunciado es verdadero'))
    expect(onCommit).toHaveBeenLastCalledWith(expect.objectContaining({ answer: true }))
  })

  it('multiple_choice: adding options and picking the correct index builds answer_index', () => {
    const onCommit = vi.fn()
    render(<Controlled type="multiple_choice" onCommit={onCommit} />)
    fireEvent.click(screen.getByText('+ agregar'))
    fireEvent.change(screen.getByPlaceholderText('Opción 1'), { target: { value: '3' } })
    fireEvent.click(screen.getByText('+ agregar'))
    fireEvent.change(screen.getByPlaceholderText('Opción 2'), { target: { value: '4' } })

    fireEvent.change(screen.getByRole('combobox'), { target: { value: '1' } })
    expect(onCommit).toHaveBeenLastCalledWith(
      expect.objectContaining({ answer_index: 1, options: ['3', '4', ''] }),
    )
  })

  it('order_lines: parses comma-separated correct_order into numbers', () => {
    const onCommit = vi.fn()
    render(<Controlled type="order_lines" onCommit={onCommit} />)
    fireEvent.change(screen.getByPlaceholderText('1,0,2'), { target: { value: '1,0,2' } })
    expect(onCommit).toHaveBeenLastCalledWith(
      expect.objectContaining({ correct_order: [1, 0, 2] }),
    )
  })

  it('trace_variables: valid JSON updates expected_trace, invalid JSON shows an error and does not commit', () => {
    const onCommit = vi.fn()
    render(<Controlled type="trace_variables" onCommit={onCommit} />)
    const textarea = screen.getByPlaceholderText('[{"contador": 1}, {"contador": 3}]')

    fireEvent.change(textarea, { target: { value: '[{"x": 1}]' } })
    expect(onCommit).toHaveBeenLastCalledWith(
      expect.objectContaining({ expected_trace: [{ x: 1 }] }),
    )

    const callsBefore = onCommit.mock.calls.length
    fireEvent.change(textarea, { target: { value: '{not valid json' } })
    expect(screen.getByText('"expected_trace" no es JSON válido')).toBeInTheDocument()
    expect(onCommit.mock.calls.length).toBe(callsBefore) // no se llamó con JSON roto
  })

  it('argued_response: only has a prompt field', () => {
    const onCommit = vi.fn()
    render(<Controlled type="argued_response" onCommit={onCommit} />)
    fireEvent.change(screen.getByPlaceholderText('Pregunta o consigna'), {
      target: { value: 'Explica la recursión' },
    })
    expect(onCommit).toHaveBeenLastCalledWith({ prompt: 'Explica la recursión' })
  })
})
