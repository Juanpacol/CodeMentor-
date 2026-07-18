import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useParams } from 'react-router-dom'

import { Tabs } from '../../components/ui/Tabs'
import { apiClient, unwrap } from '../../lib/api/client'
import { qk } from '../../lib/api/queries'
import { AgentsTab } from './AgentsTab'
import { AnalyticsTab } from './AnalyticsTab'
import { CurriculumTab } from './CurriculumTab'
import { GradebookTab } from './GradebookTab'
import { MaterialsTab } from './MaterialsTab'
import { MembersTab } from './MembersTab'
import { ReportsTab } from './ReportsTab'

export function TeacherGroupDetailPage() {
  const { groupId } = useParams<{ groupId: string }>()
  const [tab, setTab] = useState('temario')

  const { data: groups } = useQuery({
    queryKey: qk.groups.mine,
    queryFn: () => unwrap(apiClient.GET('/groups/mine')),
  })
  const group = groups?.find((g) => g.id === groupId)

  if (!groupId) return null

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold text-ink">{group?.name ?? 'Grupo'}</h1>

      <Tabs
        className="mb-6"
        value={tab}
        onChange={setTab}
        tabs={[
          { value: 'temario', label: 'Temario' },
          { value: 'miembros', label: 'Miembros' },
          { value: 'agentes', label: 'Agentes IA' },
          { value: 'analitica', label: 'Analítica' },
          { value: 'calificaciones', label: 'Calificaciones' },
          { value: 'material', label: 'Material de apoyo' },
          { value: 'reportes', label: 'Reportes' },
        ]}
      />

      {tab === 'temario' && <CurriculumTab groupId={groupId} />}
      {tab === 'miembros' && <MembersTab groupId={groupId} />}
      {tab === 'agentes' && <AgentsTab groupId={groupId} />}
      {tab === 'analitica' && <AnalyticsTab groupId={groupId} />}
      {tab === 'calificaciones' && <GradebookTab groupId={groupId} />}
      {tab === 'material' && <MaterialsTab groupId={groupId} />}
      {tab === 'reportes' && <ReportsTab groupId={groupId} />}
    </div>
  )
}
