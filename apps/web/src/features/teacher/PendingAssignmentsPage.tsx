import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { EmptyState } from '../../components/ui/EmptyState'
import { Label } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { apiClient, unwrap } from '../../lib/api/client'
import { qk } from '../../lib/api/queries'
import { AssignmentsTab } from './AssignmentsTab'

/** Acceso global a "asignar pendientes" desde el perfil del docente, sin tener
 * que entrar primero al detalle de un grupo — el mismo formulario que ya
 * existe en la pestaña de Asignaciones de cada grupo, con un selector de
 * grupo arriba en vez de tomarlo de la URL. */
export function PendingAssignmentsPage() {
  const [groupId, setGroupId] = useState('')

  const { data: groups } = useQuery({
    queryKey: qk.groups.mine,
    queryFn: () => unwrap(apiClient.GET('/groups/mine')),
  })

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-6 text-2xl font-semibold text-ink">Pendientes</h1>

      <div className="mb-6 flex flex-col gap-1">
        <Label htmlFor="pending-group">Grupo</Label>
        <Select id="pending-group" value={groupId} onChange={(e) => setGroupId(e.target.value)}>
          <option value="">Selecciona un grupo</option>
          {groups?.map((g) => (
            <option key={g.id} value={g.id}>
              {g.name}
            </option>
          ))}
        </Select>
      </div>

      {groupId ? (
        <AssignmentsTab groupId={groupId} />
      ) : (
        <EmptyState
          emoji="📋"
          title="Elige un grupo"
          description="Selecciona un grupo arriba para asignar un taller, un examen o ejercicios."
        />
      )}
    </div>
  )
}
