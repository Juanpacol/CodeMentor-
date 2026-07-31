import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'

import { Badge, type TintColor } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { apiClient, unwrap } from '../../lib/api/client'
import { qk } from '../../lib/api/queries'
import type { components } from '../../lib/api/schema'

type Assignment = components['schemas']['StudentAssignmentOut']

const DAY_MS = 24 * 60 * 60 * 1000

/** "Vence en 3 días" en vez de una fecha absoluta: lo que el estudiante decide
 * con esto es qué hacer HOY, y una fecha lo obliga a calcular la resta. */
function dueLabel(dueAt: string | null): { text: string; tint: TintColor } {
  if (!dueAt) return { text: 'Sin fecha límite', tint: 'neutral' }

  const days = Math.ceil((new Date(dueAt).getTime() - Date.now()) / DAY_MS)
  if (days < 0) return { text: `Venció hace ${-days} día${days === -1 ? '' : 's'}`, tint: 'rose' }
  if (days === 0) return { text: 'Vence hoy', tint: 'rose' }
  if (days === 1) return { text: 'Vence mañana', tint: 'yellow' }
  if (days <= 7) return { text: `Vence en ${days} días`, tint: 'yellow' }
  return { text: `Vence en ${days} días`, tint: 'neutral' }
}

/** Lo que el docente asignó y al estudiante le falta.
 *
 * Solo lo pendiente: una lista que incluyera lo ya cumplido enterraría lo
 * urgente bajo el historial, que es justo lo que este panel existe para evitar.
 * El total cumplido se muestra como una línea de resumen.
 */
export function PendingAssignments() {
  const { data: assignments } = useQuery({
    queryKey: qk.assignments.me,
    queryFn: () => unwrap(apiClient.GET('/assignments/me')),
  })

  if (!assignments || assignments.length === 0) return null

  const pending = assignments.filter((a) => !a.done)
  const done = assignments.length - pending.length

  return (
    <section className="mb-8">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold text-ink">Pendientes</h2>
        {done > 0 && (
          <p className="text-xs text-ink-secondary">
            {done} de {assignments.length} ya cumplida{done === 1 ? '' : 's'}
          </p>
        )}
      </div>

      {pending.length === 0 ? (
        <Card>
          <p className="text-sm text-ink-secondary">
            🎉 Estás al día: no tienes asignaciones pendientes.
          </p>
        </Card>
      ) : (
        <div className="flex flex-col gap-2">
          {pending.map((assignment) => (
            <AssignmentRow key={assignment.id} assignment={assignment} />
          ))}
        </div>
      )}
    </section>
  )
}

function AssignmentRow({ assignment }: { assignment: Assignment }) {
  const due = dueLabel(assignment.due_at)

  return (
    <Card className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <Link
          to={`/app/grupos/${assignment.group_id}`}
          className="font-medium text-ink hover:underline"
        >
          {assignment.title}
        </Link>
        <p className="mt-0.5 text-xs text-ink-secondary">
          {assignment.group_name}
          {assignment.total_exercises > 0 && (
            <>
              {' · '}
              {assignment.solved_exercises}/{assignment.total_exercises} ejercicios
            </>
          )}
          {/* Un tema recién asignado puede no tener ejercicios todavía; decirlo
            * evita que el estudiante crea que la plataforma perdió su tarea. */}
          {assignment.total_exercises === 0 && ' · sin ejercicios todavía'}
        </p>
      </div>
      <Badge tint={due.tint}>{due.text}</Badge>
    </Card>
  )
}
