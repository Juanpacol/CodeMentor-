import { useEffect, useRef, useState } from 'react'

interface UseCountdownResult {
  secondsLeft: number | null
  expired: boolean
}

function computeSecondsLeft(deadline: string): number {
  return Math.max(0, Math.round((new Date(deadline).getTime() - Date.now()) / 1000))
}

/** Cuenta regresiva contra un `deadline` absoluto que devuelve el servidor
 * (nunca una duración calculada localmente) — evita que el reloj o la
 * pestaña dormida del cliente desincronicen el tiempo real de la
 * evaluación. `deadline` nulo significa evaluación sin límite de tiempo.
 * Al llegar a 0 se llama a `onExpire` exactamente una vez, desde un efecto
 * (nunca durante el render, para no violar las reglas de renderizado
 * puro de React ni arriesgar una doble llamada bajo modo concurrente). */
export function useCountdown(deadline: string | null, onExpire?: () => void): UseCountdownResult {
  const [secondsLeft, setSecondsLeft] = useState<number | null>(() =>
    deadline ? computeSecondsLeft(deadline) : null,
  )
  const firedRef = useRef(false)
  const onExpireRef = useRef(onExpire)
  onExpireRef.current = onExpire

  useEffect(() => {
    firedRef.current = false
    if (!deadline) {
      setSecondsLeft(null)
      return
    }
    setSecondsLeft(computeSecondsLeft(deadline))
    const interval = setInterval(() => setSecondsLeft(computeSecondsLeft(deadline)), 1000)
    return () => clearInterval(interval)
  }, [deadline])

  useEffect(() => {
    if (secondsLeft !== null && secondsLeft <= 0 && !firedRef.current) {
      firedRef.current = true
      onExpireRef.current?.()
    }
  }, [secondsLeft])

  return { secondsLeft, expired: secondsLeft !== null && secondsLeft <= 0 }
}
