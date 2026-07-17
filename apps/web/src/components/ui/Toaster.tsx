import { AnimatePresence, motion } from 'motion/react'

import { cn } from '../../lib/cn'
import { dismissToast, useToasts } from './toastStore'

const tones = {
  default: 'border-hairline-strong bg-raised text-ink',
  error: 'border-error/40 bg-tint-rose text-tint-rose-fg',
  success: 'border-success/40 bg-tint-mint text-tint-mint-fg',
}

export function Toaster() {
  const toasts = useToasts()

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      <AnimatePresence>
        {toasts.map((toast) => (
          <motion.div
            key={toast.id}
            initial={{ opacity: 0, y: 12, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, scale: 0.96 }}
            transition={{ duration: 0.15 }}
            role="status"
            onClick={() => dismissToast(toast.id)}
            className={cn(
              'max-w-sm cursor-pointer rounded-card border px-4 py-3 text-sm shadow-lg',
              tones[toast.tone],
            )}
          >
            {toast.message}
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}
