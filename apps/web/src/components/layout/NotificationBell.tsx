import { useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'motion/react'
import { useState } from 'react'

import { apiClient, unwrap } from '../../lib/api/client'
import { qk } from '../../lib/api/queries'
import { Button } from '../ui/Button'

/** Ítem 5 (notificaciones inteligentes): campana con contador de no leídas y
 * un panel simple — sin tiempo real, el polling normal de React Query basta. */
export function NotificationBell() {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone

  const { data } = useQuery({
    queryKey: qk.notifications,
    queryFn: () =>
      unwrap(apiClient.GET('/notifications', { params: { query: { tz: timeZone } } })),
    refetchInterval: 60_000,
  })

  async function markRead(id: string) {
    await unwrap(apiClient.POST('/notifications/{notification_id}/read', { params: { path: { notification_id: id } } }))
    await queryClient.invalidateQueries({ queryKey: qk.notifications })
  }

  async function markAllRead() {
    await apiClient.POST('/notifications/read-all')
    await queryClient.invalidateQueries({ queryKey: qk.notifications })
  }

  const unreadCount = data?.unread_count ?? 0

  return (
    <div className="relative">
      <button
        aria-label="Notificaciones"
        onClick={() => setOpen((v) => !v)}
        className="relative rounded-btn p-2 text-ink-secondary hover:bg-hover hover:text-ink"
      >
        <span aria-hidden="true">🔔</span>
        {unreadCount > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex size-4 items-center justify-center rounded-full bg-tint-rose text-[10px] text-tint-rose-fg">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      <AnimatePresence>
        {open && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} role="presentation" />
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.12 }}
              className="absolute right-0 z-50 mt-2 w-80 max-w-[90vw] rounded-card border border-hairline bg-surface p-3 shadow-lg"
            >
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-ink">Notificaciones</h3>
                {unreadCount > 0 && (
                  <Button variant="ghost" size="sm" onClick={() => void markAllRead()}>
                    Marcar todas
                  </Button>
                )}
              </div>

              {(!data || data.items.length === 0) && (
                <p className="py-4 text-center text-sm text-ink-secondary">Sin notificaciones</p>
              )}

              <ul className="flex max-h-80 flex-col gap-1 overflow-y-auto">
                {data?.items.map((n) => (
                  <li key={n.id}>
                    <button
                      onClick={() => !n.read_at && void markRead(n.id)}
                      className={`w-full rounded-btn p-2 text-left text-sm ${
                        n.read_at ? 'text-ink-secondary' : 'bg-hover text-ink'
                      }`}
                    >
                      <p className="font-medium">{n.title}</p>
                      <p className="text-xs">{n.body}</p>
                    </button>
                  </li>
                ))}
              </ul>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}
