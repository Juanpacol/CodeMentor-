import { motion } from 'motion/react'
import { Link } from 'react-router'
import type { ReactNode } from 'react'

import { ThemeToggle } from '../../components/ui/ThemeToggle'

export function AuthLayout({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center bg-canvas px-4">
      <ThemeToggle className="absolute right-4 top-4" />
      <Link to="/" className="mb-8 font-mono text-lg font-semibold text-ink">
        CodeMentor
      </Link>
      <main className="w-full max-w-sm">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
          className="rounded-card border border-hairline bg-raised p-8"
        >
          <h1 className="text-xl font-semibold text-ink">{title}</h1>
          {subtitle && <p className="mt-1.5 text-sm text-ink-secondary">{subtitle}</p>}
          <div className="mt-6">{children}</div>
        </motion.div>
      </main>
    </div>
  )
}
