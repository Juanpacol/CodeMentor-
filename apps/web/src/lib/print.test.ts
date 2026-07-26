import { afterEach, describe, expect, it } from 'vitest'

import { watchPrintDetailsExpansion } from './print'

describe('watchPrintDetailsExpansion', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('opens every <details> on beforeprint and restores prior state on afterprint', () => {
    document.body.innerHTML = `
      <details id="closed"><summary>a</summary><p>A</p></details>
      <details id="already-open" open><summary>b</summary><p>B</p></details>
    `
    const stop = watchPrintDetailsExpansion()

    const closed = document.getElementById('closed') as HTMLDetailsElement
    const alreadyOpen = document.getElementById('already-open') as HTMLDetailsElement
    expect(closed.open).toBe(false)

    window.dispatchEvent(new Event('beforeprint'))
    expect(closed.open).toBe(true)
    expect(alreadyOpen.open).toBe(true)

    window.dispatchEvent(new Event('afterprint'))
    expect(closed.open).toBe(false)
    expect(alreadyOpen.open).toBe(true)

    stop()
  })

  it('stops listening after the returned cleanup runs', () => {
    document.body.innerHTML = `<details id="closed"><summary>a</summary><p>A</p></details>`
    const stop = watchPrintDetailsExpansion()
    stop()

    const closed = document.getElementById('closed') as HTMLDetailsElement
    window.dispatchEvent(new Event('beforeprint'))
    expect(closed.open).toBe(false)
  })
})
