import { useSyncExternalStore } from 'react'

export type Theme = 'light' | 'dark'

const STORAGE_KEY = 'cm-theme'

/** El script inline de index.html ya escribió `data-theme` en <html> antes
 * del primer pintado (ver ese archivo) — acá solo leemos lo que dejó, para
 * que el store y el DOM nunca discrepen en el primer render. */
function read(): Theme {
  return document.documentElement.dataset.theme === 'light' ? 'light' : 'dark'
}

let theme: Theme = read()
const listeners = new Set<() => void>()

function emit() {
  for (const listener of listeners) listener()
}

export function setTheme(next: Theme): void {
  theme = next
  document.documentElement.dataset.theme = next
  document.documentElement.style.colorScheme = next
  try {
    localStorage.setItem(STORAGE_KEY, next)
  } catch {
    // modo privado / almacenamiento bloqueado: el tema sigue funcionando
    // para esta sesión, solo no persiste entre recargas.
  }
  emit()
}

export function toggleTheme(): void {
  setTheme(theme === 'dark' ? 'light' : 'dark')
}

/** Sigue la preferencia del sistema SOLO mientras el usuario no haya elegido
 * explícitamente con el toggle — una vez que lo usa, esa decisión persiste en
 * localStorage y gana sobre cualquier cambio posterior de `prefers-color-scheme`. */
export function watchSystemTheme(): () => void {
  const mq = window.matchMedia('(prefers-color-scheme: light)')
  const onChange = (e: MediaQueryListEvent) => {
    try {
      if (localStorage.getItem(STORAGE_KEY)) return
    } catch {
      // si localStorage no es legible tampoco podemos saber si hay una
      // elección previa — seguir al sistema es el fallback razonable.
    }
    setTheme(e.matches ? 'light' : 'dark')
  }
  mq.addEventListener('change', onChange)
  return () => mq.removeEventListener('change', onChange)
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function getSnapshot(): Theme {
  return theme
}

export function useTheme(): Theme {
  return useSyncExternalStore(subscribe, getSnapshot, () => 'dark')
}
