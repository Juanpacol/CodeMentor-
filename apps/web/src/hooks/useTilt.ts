import { useRef } from 'react'
import type { PointerEvent } from 'react'

import { prefersReducedMotion } from '../lib/motion'

const MAX_TILT_DEG = 6

/** Tilt 3D por perspectiva del mouse — usado en las cards de la landing y
 * de insignias. Manipula el estilo directamente vía ref (sin re-render por
 * frame) para que el seguimiento del mouse no dispare React en cada pixel. */
export function useTilt<T extends HTMLElement>() {
  const ref = useRef<T>(null)

  function onPointerMove(event: PointerEvent<T>) {
    const el = ref.current
    if (!el || prefersReducedMotion()) return

    const rect = el.getBoundingClientRect()
    const px = (event.clientX - rect.left) / rect.width
    const py = (event.clientY - rect.top) / rect.height
    const rotateY = (px - 0.5) * MAX_TILT_DEG * 2
    const rotateX = (0.5 - py) * MAX_TILT_DEG * 2

    el.style.transform = `perspective(800px) rotateX(${rotateX}deg) rotateY(${rotateY}deg)`
  }

  function onPointerLeave() {
    const el = ref.current
    if (!el) return
    el.style.transform = 'perspective(800px) rotateX(0deg) rotateY(0deg)'
  }

  return { ref, onPointerMove, onPointerLeave }
}
