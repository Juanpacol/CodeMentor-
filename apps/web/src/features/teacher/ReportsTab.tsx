import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { Button } from '../../components/ui/Button'
import { Select } from '../../components/ui/Select'
import { pushToast } from '../../components/ui/toastStore'
import { apiClient, unwrap } from '../../lib/api/client'
import { getAccessToken } from '../../lib/api/tokens'
import { qk } from '../../lib/api/queries'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function downloadReport(reportJobId: string, format: string, groupId: string) {
  const res = await fetch(`${API_URL}/reports/${reportJobId}/download`, {
    headers: { Authorization: `Bearer ${getAccessToken()}` },
  })
  if (!res.ok) {
    pushToast('No se pudo descargar el reporte', 'error')
    return
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `reporte-${groupId}.${format}`
  a.click()
  URL.revokeObjectURL(url)
}

export function ReportsTab({ groupId }: { groupId: string }) {
  const [format, setFormat] = useState<'xlsx' | 'pdf'>('xlsx')
  const [periodId, setPeriodId] = useState('')
  const [jobId, setJobId] = useState<string | null>(null)

  const { data: periods } = useQuery({
    queryKey: qk.academicPeriods,
    queryFn: () => unwrap(apiClient.GET('/academic-periods')),
  })

  const request = useMutation({
    mutationFn: () =>
      unwrap(
        apiClient.POST('/groups/{group_id}/reports', {
          params: { path: { group_id: groupId } },
          body: { format, period_id: periodId || undefined },
        }),
      ),
    onSuccess: (job) => setJobId(job.id),
  })

  const { data: job } = useQuery({
    queryKey: qk.reports.job(jobId ?? ''),
    queryFn: () =>
      unwrap(apiClient.GET('/reports/{report_job_id}', { params: { path: { report_job_id: jobId! } } })),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'done' || status === 'failed' ? false : 2000
    },
  })

  return (
    <div className="max-w-md">
      <div className="flex flex-col gap-4">
        <div>
          <label className="mb-1.5 block text-sm font-medium text-ink-secondary">Formato</label>
          <Select value={format} onChange={(e) => setFormat(e.target.value as 'xlsx' | 'pdf')}>
            <option value="xlsx">Excel (.xlsx)</option>
            <option value="pdf">PDF</option>
          </Select>
        </div>
        {periods && periods.length > 0 && (
          <div>
            <label className="mb-1.5 block text-sm font-medium text-ink-secondary">
              Periodo académico (opcional)
            </label>
            <Select value={periodId} onChange={(e) => setPeriodId(e.target.value)}>
              <option value="">Todo el historial</option>
              {periods.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </Select>
          </div>
        )}
        <Button disabled={request.isPending} onClick={() => request.mutate()}>
          {request.isPending ? 'Solicitando...' : 'Generar reporte'}
        </Button>
      </div>

      {job && (
        <div className="mt-6 rounded-card border border-hairline bg-raised p-4">
          <p className="text-sm text-ink">
            Estado:{' '}
            {job.status === 'pending' || job.status === 'processing'
              ? 'Generando...'
              : job.status === 'done'
                ? 'Listo'
                : 'Falló'}
          </p>
          {job.status === 'done' && (
            <Button
              size="sm"
              className="mt-3"
              onClick={() => downloadReport(job.id, job.format, groupId)}
            >
              Descargar
            </Button>
          )}
          {job.status === 'failed' && job.error_message && (
            <p className="mt-2 text-sm text-error">{job.error_message}</p>
          )}
        </div>
      )}
    </div>
  )
}
