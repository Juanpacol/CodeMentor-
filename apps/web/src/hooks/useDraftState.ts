import { useCallback, useState } from 'react'

/** `useState` que sobrevive al desmontaje del componente.
 *
 * Las pestañas de `TeacherGroupDetailPage` se montan y desmontan con
 * renderizado condicional (montarlas todas dispararía las queries de las nueve
 * a la vez), así que un formulario a medio llenar se perdía con solo mirar otra
 * pestaña y volver — y al volver con los campos vacíos, enviar daba 422.
 *
 * `sessionStorage` y no `localStorage`: un borrador pertenece a la sesión de
 * trabajo. Reaparecer una semana después, en otro computador de la sala, sería
 * más desconcertante que útil.
 *
 * La clave debe incluir el `groupId` — dos grupos no comparten borrador.
 */
export function useDraftState<T>(key: string, initial: T) {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = sessionStorage.getItem(key)
      return raw === null ? initial : (JSON.parse(raw) as T)
    } catch {
      // Cuota llena, navegación privada o un JSON escrito por una versión
      // anterior del formulario. Un borrador es una comodidad: nunca una razón
      // para que la pestaña no cargue.
      return initial
    }
  })

  const set = useCallback(
    (next: T | ((prev: T) => T)) => {
      setValue((prev) => {
        const resolved = typeof next === 'function' ? (next as (p: T) => T)(prev) : next
        try {
          sessionStorage.setItem(key, JSON.stringify(resolved))
        } catch {
          // Ídem: se pierde la persistencia, no el formulario en pantalla.
        }
        return resolved
      })
    },
    [key],
  )

  return [value, set] as const
}
