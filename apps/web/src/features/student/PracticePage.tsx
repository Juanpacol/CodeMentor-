import { useMutation, useQuery } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'motion/react'
import { useMemo, useState } from 'react'
import { useParams } from 'react-router'

import { exerciseRenderers, EXERCISE_TYPE_LABELS } from '../../components/exercises/registry'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { EmptyState } from '../../components/ui/EmptyState'
import { PillTabs } from '../../components/ui/Tabs'
import { Tag } from '../../components/ui/Tag'
import { apiClient, unwrap } from '../../lib/api/client'
import { qk } from '../../lib/api/queries'
import { PracticeHistoryPanel } from './PracticeHistoryPanel'
import { TutorChatPanel } from './TutorChatPanel'

const MASTERY_LABEL: Record<string, string> = {
  new: 'Nuevo',
  practicing: 'Practicando',
  mastered: 'Dominado',
}

export function PracticePage() {
  const { groupId } = useParams<{ groupId: string }>()
  const [languageId, setLanguageId] = useState<string>('all')
  const [topicId, setTopicId] = useState<string>('all')
  const [status, setStatus] = useState<string>('all')
  const [mastery, setMastery] = useState<string>('all')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [answer, setAnswer] = useState<Record<string, unknown>>({})
  const [attemptNumber, setAttemptNumber] = useState(1)
  const [result, setResult] = useState<{ score: number; correct: boolean; needs_manual_review: boolean } | null>(
    null,
  )

  const { data: languages } = useQuery({
    queryKey: qk.languages,
    queryFn: () => unwrap(apiClient.GET('/languages')),
  })

  const { data: curriculum } = useQuery({
    queryKey: qk.curriculum(groupId!),
    queryFn: () =>
      unwrap(apiClient.GET('/groups/{group_id}/curriculum', { params: { path: { group_id: groupId! } } })),
    enabled: Boolean(groupId),
  })

  const filterArgs = {
    topicId: topicId === 'all' ? undefined : topicId,
    status: status === 'all' ? undefined : status,
    mastery: mastery === 'all' ? undefined : mastery,
  }

  const { data: exercises, isLoading } = useQuery({
    queryKey: qk.practice(groupId!, filterArgs),
    queryFn: () =>
      unwrap(
        apiClient.GET('/practice', {
          params: {
            query: {
              group_id: groupId!,
              topic_id: filterArgs.topicId,
              status: filterArgs.status as 'pending' | 'done' | undefined,
              mastery: filterArgs.mastery as 'new' | 'practicing' | 'mastered' | undefined,
            },
          },
        }),
      ),
    enabled: Boolean(groupId),
  })

  const filtered = useMemo(
    () =>
      languageId === 'all'
        ? (exercises ?? [])
        : (exercises ?? []).filter((e) => e.language_id === languageId),
    [exercises, languageId],
  )

  const selected = filtered.find((e) => e.id === selectedId) ?? null

  const submit = useMutation({
    mutationFn: () =>
      unwrap(
        apiClient.POST('/practice/{exercise_id}/submit', {
          params: { path: { exercise_id: selected!.id } },
          body: { group_id: groupId!, answer },
        }),
      ),
    onSuccess: (data) => {
      setResult(data)
      setAttemptNumber((n) => n + 1)
    },
  })

  function openExercise(id: string) {
    setSelectedId(id)
    setAnswer({})
    setResult(null)
    setAttemptNumber(1)
  }

  if (selected) {
    const Renderer = exerciseRenderers[selected.type]
    return (
      <div>
        <button
          onClick={() => setSelectedId(null)}
          className="mb-4 text-sm text-ink-secondary hover:text-ink"
        >
          ← Volver a la lista
        </button>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
          <Card>
            <div className="mb-4 flex items-center gap-2">
              <h2 className="text-lg font-semibold text-ink">{selected.title}</h2>
              <Tag>{EXERCISE_TYPE_LABELS[selected.type]}</Tag>
            </div>
            <Renderer
              content={selected.content}
              value={answer as never}
              onChange={(v) => setAnswer(v as Record<string, unknown>)}
              disabled={submit.isPending}
            />

            <AnimatePresence>
              {result && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className={`mt-4 rounded-card p-4 text-sm ${
                    result.correct
                      ? 'bg-tint-mint text-tint-mint-fg'
                      : result.needs_manual_review
                        ? 'bg-tint-sky text-tint-sky-fg'
                        : 'bg-tint-rose text-tint-rose-fg'
                  }`}
                >
                  {result.needs_manual_review
                    ? 'Tu respuesta quedó registrada para revisión de tu docente.'
                    : result.correct
                      ? `¡Correcto! Puntaje: ${Math.round(result.score * 100)}%`
                      : `Puntaje: ${Math.round(result.score * 100)}% — sigue practicando.`}
                </motion.div>
              )}
            </AnimatePresence>

            <Button className="mt-5" disabled={submit.isPending} onClick={() => submit.mutate()}>
              {submit.isPending ? 'Enviando...' : 'Enviar respuesta'}
            </Button>

            <PracticeHistoryPanel exerciseId={selected.id} key={`history-${selected.id}-${attemptNumber}`} />
          </Card>
          <TutorChatPanel groupId={groupId!} exerciseId={selected.id} key={`${selected.id}-${attemptNumber}`} />
        </div>
      </div>
    )
  }

  return (
    <div>
      <h1 className="mb-4 text-2xl font-semibold text-ink">Práctica libre</h1>

      {languages && languages.length > 0 && (
        <PillTabs
          className="mb-3"
          value={languageId}
          onChange={setLanguageId}
          tabs={[{ value: 'all', label: 'Todos' }, ...languages.map((l) => ({ value: l.id, label: l.name }))]}
        />
      )}

      {curriculum && curriculum.length > 0 && (
        <PillTabs
          className="mb-3"
          value={topicId}
          onChange={setTopicId}
          tabs={[
            { value: 'all', label: 'Todos los temas' },
            ...curriculum.map((c) => ({ value: c.topic.id, label: c.topic.name })),
          ]}
        />
      )}

      <div className="mb-6 flex flex-wrap gap-4">
        <PillTabs
          value={status}
          onChange={setStatus}
          tabs={[
            { value: 'all', label: 'Todos' },
            { value: 'pending', label: 'Pendientes' },
            { value: 'done', label: 'Resueltos' },
          ]}
        />
        <PillTabs
          value={mastery}
          onChange={setMastery}
          tabs={[
            { value: 'all', label: 'Cualquier dominio' },
            { value: 'new', label: MASTERY_LABEL.new },
            { value: 'practicing', label: MASTERY_LABEL.practicing },
            { value: 'mastered', label: MASTERY_LABEL.mastered },
          ]}
        />
      </div>

      {!isLoading && filtered.length === 0 && (
        <EmptyState emoji="🧩" title="No hay ejercicios disponibles con este filtro" />
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {filtered.map((exercise) => (
          <button key={exercise.id} onClick={() => openExercise(exercise.id)} className="text-left">
            <Card interactive>
              <div className="mb-2 flex items-center justify-between gap-2">
                <Tag>{EXERCISE_TYPE_LABELS[exercise.type]}</Tag>
                <div className="flex items-center gap-2">
                  <Tag>{MASTERY_LABEL[exercise.mastery_level]}</Tag>
                  {exercise.done && <Tag>✓ Resuelto</Tag>}
                </div>
              </div>
              <h3 className="font-medium text-ink">{exercise.title}</h3>
            </Card>
          </button>
        ))}
      </div>
    </div>
  )
}
