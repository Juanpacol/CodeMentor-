import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { motion } from 'motion/react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Dialog } from '../../components/ui/Dialog'
import { EmptyState } from '../../components/ui/EmptyState'
import { Input, Label } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { pushToast } from '../../components/ui/toastStore'
import { apiClient, ApiError, unwrap } from '../../lib/api/client'
import { qk } from '../../lib/api/queries'
import { staggerContainer, staggerItem } from '../../lib/motion'

function CreateGroupDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [gradeOrShift, setGradeOrShift] = useState('')
  const [error, setError] = useState<string | null>(null)

  const create = useMutation({
    mutationFn: () =>
      unwrap(
        apiClient.POST('/groups', {
          body: { name, grade_or_shift: gradeOrShift || undefined },
        }),
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.groups.mine })
      setName('')
      setGradeOrShift('')
      onClose()
    },
    onError: (err) => setError(err instanceof ApiError ? err.detail : 'No se pudo crear el grupo'),
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    create.mutate()
  }

  return (
    <Dialog open={open} onClose={onClose} title="Crear grupo">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div>
          <Label htmlFor="name">Nombre</Label>
          <Input id="name" required value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <Label htmlFor="grade">Grado / jornada (opcional)</Label>
          <Input id="grade" value={gradeOrShift} onChange={(e) => setGradeOrShift(e.target.value)} />
        </div>
        {error && <p className="text-sm text-error">{error}</p>}
        <Button type="submit" disabled={create.isPending} className="w-full">
          {create.isPending ? 'Creando...' : 'Crear grupo'}
        </Button>
      </form>
    </Dialog>
  )
}

export function TeacherDashboardPage() {
  const [createOpen, setCreateOpen] = useState(false)
  const { data: groups, isLoading } = useQuery({
    queryKey: qk.groups.mine,
    queryFn: () => unwrap(apiClient.GET('/groups/mine')),
  })

  function copyInviteCode(code: string) {
    void navigator.clipboard.writeText(code)
    pushToast('Código copiado', 'success')
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-ink">Grupos</h1>
        <Button onClick={() => setCreateOpen(true)}>Crear grupo</Button>
      </div>

      {isLoading && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
      )}

      {!isLoading && groups?.length === 0 && (
        <EmptyState
          emoji="👩‍🏫"
          title="Todavía no has creado ningún grupo"
          action={<Button onClick={() => setCreateOpen(true)}>Crear grupo</Button>}
        />
      )}

      {!isLoading && groups && groups.length > 0 && (
        <motion.div
          variants={staggerContainer}
          initial="initial"
          animate="animate"
          className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3"
        >
          {groups.map((group) => (
            <motion.div key={group.id} variants={staggerItem}>
              <Card className="flex h-full flex-col justify-between">
                <div>
                  <Link
                    to={`/app/docente/grupos/${group.id}`}
                    className="text-lg font-semibold text-ink hover:text-primary"
                  >
                    {group.name}
                  </Link>
                  {group.grade_or_shift && (
                    <p className="mt-1 text-sm text-ink-secondary">{group.grade_or_shift}</p>
                  )}
                </div>
                <button
                  onClick={() => copyInviteCode(group.invite_code)}
                  className="mt-4 self-start rounded-btn bg-overlay px-3 py-1.5 font-mono text-xs text-ink-secondary hover:text-ink"
                >
                  {group.invite_code} · copiar
                </button>
              </Card>
            </motion.div>
          ))}
        </motion.div>
      )}

      <CreateGroupDialog open={createOpen} onClose={() => setCreateOpen(false)} />
    </div>
  )
}
