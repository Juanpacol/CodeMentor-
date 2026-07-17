import type { Transition, Variants } from 'motion/react'

export const EASE_OUT = [0.16, 1, 0.3, 1] as const

export const pageVariants: Variants = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
}

export const pageTransition: Transition = { duration: 0.2, ease: EASE_OUT }

export const staggerContainer: Variants = {
  animate: {
    transition: { staggerChildren: 0.04 },
  },
}

export const staggerItem: Variants = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.35, ease: EASE_OUT } },
}

export const springScale: Variants = {
  initial: { opacity: 0, scale: 0.94 },
  animate: {
    opacity: 1,
    scale: 1,
    transition: { type: 'spring', stiffness: 300, damping: 24 },
  },
}

/** Usado por hooks que animan por fuera de motion.* (como useTilt, que
 * manipula `element.style.transform` directamente vía mousemove) — las
 * animaciones de componentes motion.* ya respetan la preferencia del
 * sistema automáticamente a través de `<MotionConfig reducedMotion="user">`
 * en App.tsx, así que no necesitan consultar esto. */
export function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined') return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}
