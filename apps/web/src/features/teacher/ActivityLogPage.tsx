import { useState } from 'react'

import { Tabs } from '../../components/ui/Tabs'
import { AuditLogTab } from './AuditLogTab'
import { ErrorLogTab } from './ErrorLogTab'

export function ActivityLogPage() {
  const [tab, setTab] = useState('errores')

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold text-ink">Actividad y errores</h1>

      <Tabs
        className="mb-6"
        value={tab}
        onChange={setTab}
        tabs={[
          { value: 'errores', label: 'Errores' },
          { value: 'auditoria', label: 'Auditoría' },
        ]}
      />

      {tab === 'errores' && <ErrorLogTab />}
      {tab === 'auditoria' && <AuditLogTab />}
    </div>
  )
}
