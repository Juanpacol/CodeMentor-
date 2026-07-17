import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useDebouncedCallback } from './useDebouncedCallback'

describe('useDebouncedCallback', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('only fires once for a burst of calls, with the last arguments', () => {
    const fn = vi.fn()
    const { result } = renderHook(() => useDebouncedCallback(fn, 800))

    act(() => {
      result.current('a')
      result.current('b')
      result.current('c')
    })
    expect(fn).not.toHaveBeenCalled()

    act(() => {
      vi.advanceTimersByTime(800)
    })
    expect(fn).toHaveBeenCalledTimes(1)
    expect(fn).toHaveBeenCalledWith('c')
  })

  it('fires again after the delay elapses for a second burst', () => {
    const fn = vi.fn()
    const { result } = renderHook(() => useDebouncedCallback(fn, 800))

    act(() => {
      result.current('first')
      vi.advanceTimersByTime(800)
    })
    expect(fn).toHaveBeenCalledTimes(1)

    act(() => {
      result.current('second')
      vi.advanceTimersByTime(800)
    })
    expect(fn).toHaveBeenCalledTimes(2)
    expect(fn).toHaveBeenLastCalledWith('second')
  })

  it('always uses the latest callback closure, not the one from mount', () => {
    let externalValue = 'initial'
    const fn = vi.fn(() => externalValue)
    const { result, rerender } = renderHook(() => useDebouncedCallback(fn, 800))

    externalValue = 'updated'
    rerender()

    act(() => {
      result.current()
      vi.advanceTimersByTime(800)
    })
    expect(fn).toHaveReturnedWith('updated')
  })
})
