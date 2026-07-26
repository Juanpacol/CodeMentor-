import type { ReactNode } from 'react'

import { cn } from '../../lib/cn'
import { Card } from './Card'

interface ChartCardProps {
  title: string
  /** Leyenda opcional — solo hace falta con más de una serie; con una sola,
   * el título ya la nombra (ver BarList). */
  legend?: ReactNode
  children: ReactNode
  tableHeaders: string[]
  tableRows: ReactNode[][]
  className?: string
}

/** Card + título + el gráfico + una tabla `<details>` de respaldo — nunca
 * opcional. La paleta categórica del modo claro tiene 3 de 6 slots con WARN
 * de contraste (<3:1 sobre la superficie), así que esta tabla es el canal de
 * relevo real, no un extra: cualquier dato que un color no comunique bien
 * sigue disponible como texto/tabla normal. */
export function ChartCard({ title, legend, children, tableHeaders, tableRows, className }: ChartCardProps) {
  return (
    <Card className={cn(className)}>
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-ink">{title}</h3>
        {legend}
      </div>
      {children}
      <details className="mt-4">
        <summary className="cursor-pointer text-xs text-ink-secondary hover:text-ink">
          Ver datos
        </summary>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-hairline">
                {tableHeaders.map((header) => (
                  <th key={header} scope="col" className="py-1.5 pr-4 font-medium text-ink-secondary">
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tableRows.map((row, i) => (
                <tr key={i} className="border-b border-hairline last:border-0">
                  {row.map((cell, j) => (
                    <td key={j} className="py-1.5 pr-4 text-ink">
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </Card>
  )
}
