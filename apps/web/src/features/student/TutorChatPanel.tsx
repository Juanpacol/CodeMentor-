import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'motion/react'
import { useState } from 'react'

import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Callout } from '../../components/ui/Callout'
import { Textarea } from '../../components/ui/Input'
import { Spinner } from '../../components/ui/Spinner'
import { apiClient, isAiUnavailable, unwrap } from '../../lib/api/client'
import { qk } from '../../lib/api/queries'

interface TutorChatPanelProps {
  groupId: string
  exerciseId: string
}

/** Panel del Tutor IA (RF-31, RF-35): cada respuesta del tutor va
 * visiblemente etiquetada como IA, nunca se confunde con un mensaje de un
 * docente humano. Si el harness de IA no está disponible (503, §9.4), se
 * muestra un aviso amable en vez de romper la práctica. */
export function TutorChatPanel({ groupId, exerciseId }: TutorChatPanelProps) {
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState('')
  const [unavailable, setUnavailable] = useState(false)
  const historyKey = qk.ai.tutorHistory(groupId, exerciseId)

  const { data: history } = useQuery({
    queryKey: historyKey,
    queryFn: () =>
      unwrap(
        apiClient.GET('/ai/tutor/history', {
          params: { query: { group_id: groupId, exercise_id: exerciseId } },
        }),
      ),
  })

  const attemptNumber = (history?.length ?? 0) / 2 + 1

  const sendHint = useMutation({
    mutationFn: (studentAnswer: string) =>
      unwrap(
        apiClient.POST('/ai/tutor/hint', {
          body: {
            group_id: groupId,
            exercise_id: exerciseId,
            attempt_number: Math.round(attemptNumber),
            student_answer: studentAnswer,
          },
        }),
      ),
    onSuccess: () => {
      setUnavailable(false)
      setDraft('')
      void queryClient.invalidateQueries({ queryKey: historyKey })
    },
    onError: (err) => {
      if (isAiUnavailable(err)) setUnavailable(true)
    },
  })

  return (
    <div className="flex h-full flex-col rounded-card border border-hairline bg-raised p-4">
      <div className="mb-3 flex items-center gap-2">
        <span aria-hidden="true">✨</span>
        <h3 className="text-sm font-semibold text-ink">Tutor IA</h3>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto">
        <AnimatePresence initial={false}>
          {history?.map((message) => (
            <motion.div
              key={message.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className={message.role === 'tutor' ? '' : 'flex justify-end'}
            >
              <div
                className={
                  message.role === 'tutor'
                    ? 'max-w-[90%] rounded-card bg-tint-lavender p-3 text-sm text-tint-lavender-fg'
                    : 'max-w-[90%] rounded-card bg-overlay p-3 text-sm text-ink'
                }
              >
                {message.role === 'tutor' && (
                  <Badge tint="lavender" className="mb-1.5">
                    IA
                  </Badge>
                )}
                <p>{message.content}</p>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        {unavailable && (
          <Callout tone="ai">El asistente de IA no está disponible en este momento. Intenta de nuevo más tarde.</Callout>
        )}
      </div>

      <div className="mt-3 flex flex-col gap-2">
        <Textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Cuéntale al tutor en qué estás atascado..."
          rows={2}
        />
        <Button
          size="sm"
          disabled={!draft.trim() || sendHint.isPending}
          onClick={() => sendHint.mutate(draft)}
        >
          {sendHint.isPending ? <Spinner /> : 'Pedir pista'}
        </Button>
      </div>
    </div>
  )
}
