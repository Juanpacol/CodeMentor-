import { AnimatePresence, motion } from 'motion/react'
import { useEffect } from 'react'
import type { ReactNode } from 'react'

interface DialogProps {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
}

/** Modal simple sobre un overlay — no usa `<dialog>` nativo para poder
 * animar entrada/salida con motion (AnimatePresence necesita controlar el
 * desmontaje, lo que `<dialog>` nativo con `showModal()` no permite). */
export function Dialog({ open, onClose, title, children }: DialogProps) {
  useEffect(() => {
    if (!open) return
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [open, onClose])

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          onClick={onClose}
          role="presentation"
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label={title}
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
            onClick={(e) => e.stopPropagation()}
            className="relative w-full max-w-md rounded-card border border-hairline bg-raised p-6 shadow-2xl"
          >
            <button
              type="button"
              aria-label="Cerrar"
              onClick={onClose}
              className="absolute right-4 top-4 rounded-btn p-1 text-ink-secondary hover:bg-hover hover:text-ink"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path
                  d="M4 4l8 8M12 4l-8 8"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
              </svg>
            </button>
            <h2 className="mb-4 text-lg font-semibold text-ink">{title}</h2>
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
