import { useQuery, useQueryClient } from '@tanstack/react-query'
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
import { useTilt } from '../../hooks/useTilt'
import { apiClient, ApiError, unwrap } from '../../lib/api/client'
import { staggerContainer, staggerItem } from '../../lib/motion'
import { qk } from '../../lib/api/queries'

function JoinGroupDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient()
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await unwrap(apiClient.POST('/groups/join', { body: { invite_code: code } }))
      await queryClient.invalidateQueries({ queryKey: qk.groups.mine })
      pushToast('Te uniste al grupo correctamente', 'success')
      setCode('')
      onClose()
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'No se pudo unir al grupo')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="Unirme a un grupo">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div>
          <Label htmlFor="invite_code">Código de invitación</Label>
          <Input
            id="invite_code"
            required
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            placeholder="ABC123"
          />
        </div>
        {error && <p className="text-sm text-error">{error}</p>}
        <Button type="submit" disabled={loading} className="w-full">
          {loading ? 'Uniendo...' : 'Unirme'}
        </Button>
      </form>
    </Dialog>
  )
}

function GroupCard({ group }: { group: { id: string; name: string; grade_or_shift: string | null } }) {
  const tilt = useTilt<HTMLAnchorElement>()
  return (
    <motion.div variants={staggerItem}>
      <Link
        to={`/app/grupos/${group.id}`}
        ref={tilt.ref}
        onPointerMove={tilt.onPointerMove}
        onPointerLeave={tilt.onPointerLeave}
        style={{ transformStyle: 'preserve-3d', willChange: 'transform' }}
        className="block transition-transform duration-150 ease-out"
      >
        <Card interactive>
          <h3 className="text-lg font-semibold text-ink">{group.name}</h3>
          {group.grade_or_shift && (
            <p className="mt-1 text-sm text-ink-secondary">{group.grade_or_shift}</p>
          )}
        </Card>
      </Link>
    </motion.div>
  )
}

export function StudentDashboardPage() {
  const [joinOpen, setJoinOpen] = useState(false)
  const { data: groups, isLoading } = useQuery({
    queryKey: qk.groups.mine,
    queryFn: () => unwrap(apiClient.GET('/groups/mine')),
  })

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-ink">Mis grupos</h1>
        <Button onClick={() => setJoinOpen(true)}>Unirme con código</Button>
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
          emoji="🎒"
          title="Todavía no perteneces a ningún grupo"
          description="Pídele a tu docente el código de invitación de tu grupo."
          action={<Button onClick={() => setJoinOpen(true)}>Unirme con código</Button>}
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
            <GroupCard key={group.id} group={group} />
          ))}
        </motion.div>
      )}

      <JoinGroupDialog open={joinOpen} onClose={() => setJoinOpen(false)} />
    </div>
  )
}
