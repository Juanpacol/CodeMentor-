import type { HTMLAttributes } from 'react'

import { cn } from '../../lib/cn'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  interactive?: boolean
}

export function Card({ interactive, className, children, ...rest }: CardProps) {
  return (
    <div
      className={cn(
        'rounded-card border border-hairline bg-raised p-6',
        interactive &&
          'transition-[transform,border-color] duration-150 ease-out hover:-translate-y-0.5 hover:border-hairline-strong',
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  )
}
