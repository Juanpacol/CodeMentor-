import { forwardRef } from 'react'
import type { SelectHTMLAttributes } from 'react'

import { cn } from '../../lib/cn'

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  function Select({ className, children, ...rest }, ref) {
    return (
      <select
        ref={ref}
        className={cn(
          'h-11 w-full rounded-btn border border-hairline-strong bg-canvas px-3 text-sm text-ink ' +
            'transition-colors duration-150 focus:border-primary focus:outline-none disabled:opacity-50',
          className,
        )}
        {...rest}
      >
        {children}
      </select>
    )
  },
)
