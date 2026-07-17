import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query'

import { ApiError, isAiUnavailable } from './api/client'
import { pushToast } from '../components/ui/toastStore'

function reportError(error: unknown) {
  // Un 503 de /ai/* se degrada en el propio componente (Callout), nunca
  // como un toast genérico — la funcionalidad no-IA sigue intacta y no
  // queremos alarmar al usuario por algo que ya se explica en contexto.
  if (isAiUnavailable(error)) return
  const message = error instanceof ApiError ? error.detail : 'Ocurrió un error inesperado'
  pushToast(message, 'error')
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false, staleTime: 30_000 },
    mutations: { retry: false },
  },
  queryCache: new QueryCache({ onError: reportError }),
  mutationCache: new MutationCache({ onError: reportError }),
})
