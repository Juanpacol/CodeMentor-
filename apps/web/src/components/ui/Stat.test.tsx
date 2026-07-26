import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Stat } from './Stat'

describe('Stat', () => {
  it('renders label, value and hint', () => {
    render(<Stat label="Puntos" value={120} hint="acumulados" />)
    expect(screen.getByText('Puntos')).toBeInTheDocument()
    expect(screen.getByText('120')).toBeInTheDocument()
    expect(screen.getByText('acumulados')).toBeInTheDocument()
  })

  it('links the value to its label via aria-labelledby', () => {
    render(<Stat label="Precisión global" value="87%" />)
    const value = screen.getByText('87%')
    const label = screen.getByText('Precisión global')
    expect(value).toHaveAttribute('aria-labelledby', label.id)
  })

  it('omits the hint when not provided', () => {
    render(<Stat label="Grupos" value={3} />)
    expect(screen.queryByText('acumulados')).not.toBeInTheDocument()
  })
})
