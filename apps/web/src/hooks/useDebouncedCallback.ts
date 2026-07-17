import { useEffect, useRef } from 'react'

/** Devuelve una versión "debounced" de `callback` — usada para el
 * autoguardado de respuestas de evaluación (cada cambio dispara un timer
 * de `delayMs`; solo la última invocación dentro de esa ventana llega a
 * ejecutarse). Siempre llama a la versión más reciente del callback aunque
 * el componente se re-renderice entre el cambio y el disparo. */
export function useDebouncedCallback<Args extends unknown[]>(
  callback: (...args: Args) => void,
  delayMs: number,
): (...args: Args) => void {
  const callbackRef = useRef(callback)
  callbackRef.current = callback
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
    }
  }, [])

  return (...args: Args) => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    timeoutRef.current = setTimeout(() => callbackRef.current(...args), delayMs)
  }
}
