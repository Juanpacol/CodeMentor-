import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { EmptyState } from '../../components/ui/EmptyState'
import { FieldError, Input, Label } from '../../components/ui/Input'
import { apiClient, ApiError, unwrap } from '../../lib/api/client'
import { qk } from '../../lib/api/queries'

export function AcademicPeriodsPage() {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [error, setError] = useState<string | null>(null)

  const { data: periods, isLoading } = useQuery({
    queryKey: qk.academicPeriods,
    queryFn: () => unwrap(apiClient.GET('/academic-periods')),
  })

  const create = useMutation({
    mutationFn: () =>
      unwrap(
        apiClient.POST('/academic-periods', {
          body: { name, start_date: startDate, end_date: endDate },
        }),
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.academicPeriods })
      setName('')
      setStartDate('')
      setEndDate('')
    },
    onError: (err) => setError(err instanceof ApiError ? err.detail : 'No se pudo crear el periodo'),
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    create.mutate()
  }

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="mb-6 text-2xl font-semibold text-ink">Periodos académicos</h1>

      <Card className="mb-8">
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <Label htmlFor="period-name">Nombre</Label>
            <Input
              id="period-name"
              required
              placeholder="Periodo 1 - 2026"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="start">Inicio</Label>
              <Input
                id="start"
                type="date"
                required
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="end">Fin</Label>
              <Input
                id="end"
                type="date"
                required
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </div>
          </div>
          <FieldError>{error}</FieldError>
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? 'Creando...' : 'Crear periodo'}
          </Button>
        </form>
      </Card>

      {!isLoading && periods?.length === 0 && (
        <EmptyState emoji="🗓️" title="No hay periodos académicos creados" />
      )}

      <div className="flex flex-col gap-2">
        {periods?.map((period) => (
          <Card key={period.id} className="flex items-center justify-between">
            <span className="font-medium text-ink">{period.name}</span>
            <span className="text-sm text-ink-secondary">
              {period.start_date} — {period.end_date}
            </span>
          </Card>
        ))}
      </div>
    </div>
  )
}
