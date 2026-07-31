import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useDraftState } from './useDraftState'

describe('useDraftState', () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  it('starts from the initial value when there is no draft stored', () => {
    const { result } = renderHook(() => useDraftState('rubrica:g1:name', ''))
    expect(result.current[0]).toBe('')
  })

  it('restores the stored draft on a fresh mount', () => {
    const { result, unmount } = renderHook(() => useDraftState('rubrica:g1:name', ''))
    act(() => result.current[1]('Temario primer periodo'))
    unmount()

    // Un remontaje es exactamente lo que pasa al cambiar de pestaña y volver.
    const remounted = renderHook(() => useDraftState('rubrica:g1:name', ''))
    expect(remounted.result.current[0]).toBe('Temario primer periodo')
  })

  it('accepts an updater function, like useState', () => {
    const { result } = renderHook(() => useDraftState<string[]>('rubrica:g1:types', ['a']))
    act(() => result.current[1]((prev) => [...prev, 'b']))
    expect(result.current[0]).toEqual(['a', 'b'])
  })

  it('keeps drafts of different groups apart', () => {
    const g1 = renderHook(() => useDraftState('rubrica:g1:name', ''))
    act(() => g1.result.current[1]('Grupo uno'))

    const g2 = renderHook(() => useDraftState('rubrica:g2:name', ''))
    expect(g2.result.current[0]).toBe('')
  })

  it('falls back to the initial value when the stored draft is corrupt', () => {
    sessionStorage.setItem('rubrica:g1:types', '{no es json')
    const { result } = renderHook(() => useDraftState<string[]>('rubrica:g1:types', ['a']))
    expect(result.current[0]).toEqual(['a'])
  })

  it('still works when sessionStorage throws (private mode, quota)', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError')
    })

    const { result } = renderHook(() => useDraftState('rubrica:g1:name', ''))
    act(() => result.current[1]('sin persistencia'))
    // Se pierde el respaldo, nunca el formulario en pantalla.
    expect(result.current[0]).toBe('sin persistencia')

    vi.restoreAllMocks()
  })
})
