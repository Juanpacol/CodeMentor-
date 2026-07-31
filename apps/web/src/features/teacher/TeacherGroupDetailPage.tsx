import { useQuery } from '@tanstack/react-query'
import { Link, useParams, useSearchParams } from 'react-router'

import { Tabs } from '../../components/ui/Tabs'
import { apiClient, unwrap } from '../../lib/api/client'
import { qk } from '../../lib/api/queries'
import { AnalyticsTab } from './AnalyticsTab'
import { AssignmentsTab } from './AssignmentsTab'
import { CurriculumTab } from './CurriculumTab'
import { GradebookTab } from './GradebookTab'
import { GuidesTab } from './GuidesTab'
import { MaterialsTab } from './MaterialsTab'
import { MembersTab } from './MembersTab'
import { ReportsTab } from './ReportsTab'
import { RubricTab } from './RubricTab'

export function TeacherGroupDetailPage() {
  const { groupId } = useParams<{ groupId: string }>()
  // La pestaña vive en la URL y no en `useState` para que refrescar, compartir
  // el enlace o volver con el botón atrás caigan donde el docente estaba.
  // `replace` para no llenar el historial con cada clic de pestaña.
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') ?? 'temario'
  const setTab = (value: string) => setSearchParams({ tab: value }, { replace: true })

  const { data: groups } = useQuery({
    queryKey: qk.groups.mine,
    queryFn: () => unwrap(apiClient.GET('/groups/mine')),
  })
  const group = groups?.find((g) => g.id === groupId)

  if (!groupId) return null

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold text-ink">{group?.name ?? 'Grupo'}</h1>
        {/* El banco vive fuera del detalle de grupo (es de toda la institución,
          * no de un grupo), y por eso los docentes no encontraban cómo crear
          * ejercicios propios: buscaban entre estas pestañas. */}
        <Link
          to="/app/docente/ejercicios"
          className="text-sm text-ink-secondary underline hover:text-ink"
        >
          Banco de ejercicios ↗
        </Link>
      </div>

      <Tabs
        className="mb-6"
        value={tab}
        onChange={setTab}
        tabs={[
          { value: 'temario', label: 'Temario' },
          { value: 'asignaciones', label: 'Asignaciones' },
          { value: 'rubrica', label: 'Rúbrica' },
          { value: 'miembros', label: 'Miembros' },
          { value: 'analitica', label: 'Analítica' },
          { value: 'calificaciones', label: 'Calificaciones' },
          { value: 'guias', label: 'Guías' },
          { value: 'material', label: 'Material de apoyo' },
          { value: 'reportes', label: 'Reportes' },
        ]}
      />

      {tab === 'temario' && <CurriculumTab groupId={groupId} />}
      {tab === 'asignaciones' && <AssignmentsTab groupId={groupId} />}
      {tab === 'rubrica' && <RubricTab groupId={groupId} />}
      {tab === 'miembros' && <MembersTab groupId={groupId} />}
      {tab === 'analitica' && <AnalyticsTab groupId={groupId} />}
      {tab === 'calificaciones' && <GradebookTab groupId={groupId} />}
      {tab === 'guias' && <GuidesTab groupId={groupId} />}
      {tab === 'material' && <MaterialsTab groupId={groupId} />}
      {tab === 'reportes' && <ReportsTab groupId={groupId} />}
    </div>
  )
}
