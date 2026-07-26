import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { setTheme, toggleTheme } from './theme'

describe('theme store', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    setTheme('dark')
  })

  it('setTheme updates the DOM attribute, inline color-scheme and localStorage', () => {
    setTheme('light')
    expect(document.documentElement.dataset.theme).toBe('light')
    expect(document.documentElement.style.colorScheme).toBe('light')
    expect(localStorage.getItem('cm-theme')).toBe('light')
  })

  it('toggleTheme flips between light and dark', () => {
    setTheme('dark')
    toggleTheme()
    expect(document.documentElement.dataset.theme).toBe('light')
    toggleTheme()
    expect(document.documentElement.dataset.theme).toBe('dark')
  })
})
