import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { BarList } from './BarList'

describe('BarList', () => {
  it('renders a percentage value label by default', () => {
    render(
      <BarList
        items={[{ key: 'a', label: 'Ciclos', value: 0.92 }]}
      />,
    )
    expect(screen.getByText('Ciclos')).toBeInTheDocument()
    expect(screen.getByText('92%')).toBeInTheDocument()
  })

  it('renders "—" and no bar track when value is null', () => {
    const { container } = render(
      <BarList items={[{ key: 'a', label: 'Sin datos', value: null }]} />,
    )
    expect(screen.getByText('—')).toBeInTheDocument()
    expect(container.querySelector('[aria-hidden="true"]')).not.toBeInTheDocument()
  })

  it('renders a hint element next to the value', () => {
    render(
      <BarList
        items={[{ key: 'a', label: 'Ciclos', value: 0.5, hint: <span>10 envíos</span> }]}
      />,
    )
    expect(screen.getByText('10 envíos')).toBeInTheDocument()
  })

  it('respects a custom max for the bar width calculation', () => {
    render(<BarList items={[{ key: 'a', label: 'X', value: 5, max: 10 }]} />)
    expect(screen.getByText('50%')).toBeInTheDocument()
  })

  it('respects an explicit valueLabel override', () => {
    render(
      <BarList items={[{ key: 'a', label: 'X', value: 0.5, valueLabel: '3 de 6' }]} />,
    )
    expect(screen.getByText('3 de 6')).toBeInTheDocument()
    expect(screen.queryByText('50%')).not.toBeInTheDocument()
  })
})
