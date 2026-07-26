import { Suspense, type ReactNode } from 'react'

import { Spinner } from '../ui/Spinner'

export function PageFallback() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center">
      <Spinner className="size-6" />
    </div>
  )
}

export function suspended(element: ReactNode) {
  return <Suspense fallback={<PageFallback />}>{element}</Suspense>
}
