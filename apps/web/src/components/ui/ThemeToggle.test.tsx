import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { setTheme } from '../../lib/theme'
import { ThemeToggle } from './ThemeToggle'

describe('ThemeToggle', () => {
  beforeEach(() => {
    localStorage.clear()
    setTheme('dark')
  })

  afterEach(() => {
    setTheme('dark')
  })

  it('reflects the current theme via aria-pressed and label', () => {
    render(<ThemeToggle />)
    const button = screen.getByRole('button', { name: 'Cambiar a modo claro' })
    expect(button).toHaveAttribute('aria-pressed', 'true')
  })

  it('toggles the theme and updates the DOM when clicked', async () => {
    render(<ThemeToggle />)
    await userEvent.click(screen.getByRole('button', { name: 'Cambiar a modo claro' }))

    expect(document.documentElement.dataset.theme).toBe('light')
    expect(screen.getByRole('button', { name: 'Cambiar a modo oscuro' })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
  })
})
