import { QueryClientProvider } from '@tanstack/react-query'
import { MotionConfig } from 'motion/react'
import { RouterProvider } from 'react-router-dom'

import { Toaster } from './components/ui/Toaster'
import { AuthProvider } from './hooks/useAuth'
import { queryClient } from './lib/queryClient'
import { router } from './router'

export function App() {
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
