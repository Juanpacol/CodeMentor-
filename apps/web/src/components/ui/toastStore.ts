import { useSyncExternalStore } from 'react'

export interface Toast {
  id: string
  message: string
  tone: 'default' | 'error' | 'success'
}

let toasts: Toast[] = []
const listeners = new Set<() => void>()

function emit() {
  for (const listener of listeners) listener()
}

export function pushToast(message: string, tone: Toast['tone'] = 'default') {
  const id = crypto.randomUUID()
  toasts = [...toasts, { id, message, tone }]
  emit()
  setTimeout(() => dismissToast(id), 4000)
}

export function dismissToast(id: string) {
  toasts = toasts.filter((t) => t.id !== id)
  emit()
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function getSnapshot() {
  return toasts
}

export function useToasts(): Toast[] {
  return useSyncExternalStore(subscribe, getSnapshot)
}
