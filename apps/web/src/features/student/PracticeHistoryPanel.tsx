import { useQuery } from '@tanstack/react-query'

import { apiClient, unwrap } from '../../lib/api/client'
import { qk } from '../../lib/api/queries'

/** Ítem 3 (historial de intentos + comparación): cada envío ya se guarda
 * individual — esto solo los lista, resaltando el mejor score para comparar
 * de un vistazo sin necesitar un gráfico nuevo. */
export function PracticeHistoryPanel({ exerciseId }: { exerciseId: string }) {
  const { data: attempts } = useQuery({
    queryKey: qk.practiceHistory(exerciseId),
    queryFn: () =>
      unwrap(
        apiClient.GET('/practice/{exercise_id}/history', {
          params: { path: { exercise_id: exerciseId } },
        }),
      ),
  })

  if (!attempts || attempts.length === 0) return null

  const bestScore = Math.max(...attempts.map((a) => a.score))

  return (
    <details className="mt-5 text-sm">
      <summary className="cursor-pointer text-ink-secondary hover:text-ink">
        Intentos anteriores ({attempts.length})
      </summary>
      <ul className="mt-3 flex flex-col gap-2">
        {attempts.map((attempt) => (
          <li
            key={attempt.id}
            className="flex items-center justify-between rounded-btn bg-canvas px-3 py-2"
          >
            <span className="text-ink-secondary">
              {new Date(attempt.created_at).toLocaleString('es-CO')}
            </span>
            <span className={attempt.correct ? 'text-tint-mint-fg' : 'text-ink'}>
              {Math.round(attempt.score * 100)}%
              {attempt.score === bestScore && attempts.length > 1 && ' 🏆'}
            </span>
          </li>
        ))}
      </ul>
    </details>
  )
}
