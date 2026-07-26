import { QueryClientProvider } from '@tanstack/react-query'
import { MotionConfig } from 'motion/react'
import { useEffect } from 'react'
import { RouterProvider } from 'react-router'

import { Toaster } from './components/ui/Toaster'
import { AuthProvider } from './hooks/useAuth'
import { queryClient } from './lib/queryClient'
import { watchPrintDetailsExpansion } from './lib/print'
import { watchSystemTheme } from './lib/theme'
import { router } from './router'

export function App() {
  // Se registra una sola vez a nivel de app — sigue el sistema hasta que el
  // usuario elige explícitamente con el ThemeToggle (ver lib/theme.ts).
  useEffect(() => watchSystemTheme(), [])
  // Ítem 8: expande cada <details> ("Ver datos" de un gráfico) antes de
  // imprimir y lo devuelve a su estado previo después (ver lib/print.ts).
  useEffect(() => watchPrintDetailsExpansion(), [])

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        {/* reducedMotion="user" respeta prefers-reduced-motion del sistema
            para TODAS las animaciones de motion.* — el @media query en
            theme.css solo cubre transiciones CSS normales (hover de
            botones, etc.), no las animaciones de transform/opacity que
            motion aplica vía JS. */}
        <MotionConfig reducedMotion="user">
          <RouterProvider router={router} />
          <Toaster />
        </MotionConfig>
      </AuthProvider>
    </QueryClientProvider>
  )
}
