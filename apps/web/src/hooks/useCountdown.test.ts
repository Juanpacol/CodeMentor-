import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useCountdown } from './useCountdown'

describe('useCountdown', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-01-01T12:00:00Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns null/not-expired when there is no deadline (untimed evaluation)', () => {
    const { result } = renderHook(() => useCountdown(null))
    expect(result.current.secondsLeft).toBeNull()
    expect(result.current.expired).toBe(false)
  })

  it('is already expired if the deadline is in the past', () => {
    const onExpire = vi.fn()
    const { result } = renderHook(() =>
      useCountdown('2026-01-01T11:59:00Z', onExpire),
    )
    expect(result.current.secondsLeft).toBe(0)
    expect(result.current.expired).toBe(true)
  })

  it('calls onExpire exactly once when the countdown reaches zero', () => {
    const onExpire = vi.fn()
    const deadline = new Date(Date.now() + 3000).toISOString()
    renderHook(() => useCountdown(deadline, onExpire))

    expect(onExpire).not.toHaveBeenCalled()

    act(() => {
      vi.advanceTimersByTime(3000)
    })
    expect(onExpire).toHaveBeenCalledTimes(1)

    act(() => {
      vi.advanceTimersByTime(5000)
    })
    expect(onExpire).toHaveBeenCalledTimes(1)
  })

  it('counts down second by second toward the deadline', () => {
    const deadline = new Date(Date.now() + 5000).toISOString()
    const { result } = renderHook(() => useCountdown(deadline))
    expect(result.current.secondsLeft).toBe(5)

    act(() => {
      vi.advanceTimersByTime(2000)
    })
    expect(result.current.secondsLeft).toBe(3)
  })
})
