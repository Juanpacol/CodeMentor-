import { ChartCard } from './ChartCard'

export interface ActivityDay {
  /** ISO `YYYY-MM-DD`, ya en la zona horaria del estudiante. */
  date: string
  submissions: number
  correct: number
}

const CELL = 11
const GAP = 3
const STEP = CELL + GAP
const WEEKDAY_LABEL_WIDTH = 24
const MONTH_LABEL_HEIGHT = 14

const MONTHS = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
/** Semana de lunes a domingo: es la convención en Colombia, y el fin de semana
 * queda junto abajo en vez de partido entre la primera y la última fila. */
const WEEKDAYS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']

/** Formato local, NO `toISOString()`: ese convierte a UTC, y en Colombia
 * (UTC-5) un `Date` de medianoche local se serializa como el día anterior —
 * todas las celdas quedarían corridas un día. */
function toKey(date: Date) {
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}

/** Medianoche local, para que comparar "¿es futuro?" no dependa de la hora a la
 * que el estudiante abra la página. */
function atMidnight(date: Date) {
  const copy = new Date(date)
  copy.setHours(0, 0, 0, 0)
  return copy
}

/** Cuatro niveles sobre la rampa `--color-ordinal-*`, que ya está validada como
 * secuencial (un solo tono, luminosidad monótona, ΔL ≥ 0.06). Relativos al día
 * más activo y no a umbrales fijos: quien resuelve 3 ejercicios al día merece
 * ver su constancia igual que quien resuelve 30. */
function level(submissions: number, max: number) {
  if (submissions <= 0) return 0
  return Math.min(4, Math.ceil((submissions / max) * 4))
}

function fill(lvl: number) {
  return lvl === 0 ? 'var(--color-hairline)' : `var(--color-ordinal-${lvl})`
}

export function ContributionHeatmap({
  days,
  today: todayInput,
  weeks = 27,
}: {
  days: ActivityDay[]
  /** Se inyecta en vez de leer el reloj adentro: hace el componente
   * determinista para los tests y respeta la zona del estudiante. */
  today: Date
  weeks?: number
}) {
  const today = atMidnight(todayInput)
  const byDate = new Map(days.map((day) => [day.date, day]))
  const max = Math.max(1, ...days.map((day) => day.submissions))

  // El último día de la rejilla es el domingo de esta semana, para que la
  // columna de hoy quede completa y no a medias.
  const end = new Date(today)
  end.setDate(end.getDate() + (6 - dayIndex(today)))
  const start = new Date(end)
  start.setDate(start.getDate() - (weeks * 7 - 1))

  const columns: { key: string; cells: (ActivityDay | null)[]; monthLabel: string | null }[] = []
  const cursor = new Date(start)
  let lastMonth = -1

  for (let week = 0; week < weeks; week += 1) {
    const cells: (ActivityDay | null)[] = []
    let monthLabel: string | null = null
    for (let row = 0; row < 7; row += 1) {
      const key = toKey(cursor)
      // Los días futuros de la última columna se dejan vacíos, no en gris de
      // "sin actividad": todavía no han pasado.
      cells.push(cursor > today ? null : (byDate.get(key) ?? { date: key, submissions: 0, correct: 0 }))
      if (row === 0 && cursor.getMonth() !== lastMonth) {
        lastMonth = cursor.getMonth()
        monthLabel = MONTHS[lastMonth]
      }
      cursor.setDate(cursor.getDate() + 1)
    }
    columns.push({ key: `w${week}`, cells, monthLabel })
  }

  const width = WEEKDAY_LABEL_WIDTH + weeks * STEP
  const height = MONTH_LABEL_HEIGHT + 7 * STEP

  const activos = days.filter((day) => day.submissions > 0)

  return (
    <ChartCard
      title="Actividad diaria"
      tableHeaders={['Día', 'Ejercicios', 'Aciertos']}
      // Obligatoria en este repo, y acá con más razón: el color por sí solo no
      // comunica "cuántos", solo "más o menos".
      tableRows={activos.map((day) => [day.date, String(day.submissions), String(day.correct)])}
    >
      <div className="overflow-x-auto">
        <svg
          width={width}
          height={height}
          role="img"
          aria-label={`Mapa de actividad: ${activos.length} días con práctica en las últimas ${weeks} semanas`}
        >
          {WEEKDAYS.map((label, row) =>
            // Solo lunes, miércoles y viernes: con los siete, las etiquetas se
            // encima unas con otras a este tamaño de celda.
            row % 2 === 0 ? (
              <text
                key={label}
                x={0}
                y={MONTH_LABEL_HEIGHT + row * STEP + CELL - 1}
                className="fill-[var(--color-chart-axis)] text-[9px]"
              >
                {label}
              </text>
            ) : null,
          )}

          {columns.map((column, index) =>
            column.monthLabel ? (
              <text
                key={`m${column.key}`}
                x={WEEKDAY_LABEL_WIDTH + index * STEP}
                y={MONTH_LABEL_HEIGHT - 4}
                className="fill-[var(--color-chart-axis)] text-[9px]"
              >
                {column.monthLabel}
              </text>
            ) : null,
          )}

          {columns.map((column, index) =>
            column.cells.map((cell, row) =>
              cell === null ? null : (
                <rect
                  key={`${column.key}-${row}`}
                  x={WEEKDAY_LABEL_WIDTH + index * STEP}
                  y={MONTH_LABEL_HEIGHT + row * STEP}
                  width={CELL}
                  height={CELL}
                  rx={2}
                  fill={fill(level(cell.submissions, max))}
                >
                  <title>
                    {cell.date}: {cell.submissions} ejercicio
                    {cell.submissions === 1 ? '' : 's'}, {cell.correct} correcto
                    {cell.correct === 1 ? '' : 's'}
                  </title>
                </rect>
              ),
            ),
          )}
        </svg>
      </div>

      <div className="mt-2 flex items-center gap-1.5 text-xs text-ink-secondary">
        <span>Menos</span>
        {[0, 1, 2, 3, 4].map((lvl) => (
          <span
            key={lvl}
            className="inline-block size-3 rounded-[2px]"
            style={{ backgroundColor: fill(lvl) }}
          />
        ))}
        <span>Más</span>
      </div>
    </ChartCard>
  )
}

/** Lunes = 0 … domingo = 6. `getDay()` devuelve domingo = 0, que dejaría la
 * semana empezando en domingo. */
function dayIndex(date: Date) {
  return (date.getDay() + 6) % 7
}
