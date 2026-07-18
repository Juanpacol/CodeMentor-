import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ActivityLogPage } from './ActivityLogPage'

const ERRORS_RESPONSE = {
  items: [
    {
      id: 'err-1',
      institution_id: 'inst-1',
      user_id: null,
      path: '/algo',
      method: 'GET',
      status_code: 500,
      exception_type: 'RuntimeError',
      message: 'algo se rompió',
      stacktrace: null,
      created_at: new Date().toISOString(),
    },
  ],
  total: 1,
  page: 1,
  page_size: 25,
}

const AUDIT_RESPONSE = {
  items: [
    {
      id: 'audit-1',
      actor_user_id: 'user-1',
      action: 'role_changed',
      target_type: 'User',
      target_id: 'abc',
      details: { from: 'student', to: 'teacher' },
      created_at: new Date().toISOString(),
    },
  ],
  total: 1,
  page: 1,
  page_size: 25,
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <ActivityLogPage />
    </QueryClientProvider>,
  )
}

describe('ActivityLogPage', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('shows the error tab by default and switches to the audit tab', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = input instanceof Request ? input.url : String(input)
        if (url.includes('/observability/audit')) {
          return new Response(JSON.stringify(AUDIT_RESPONSE), { status: 200 })
        }
        return new Response(JSON.stringify(ERRORS_RESPONSE), { status: 200 })
      }),
    )

    renderPage()

    await waitFor(() => expect(screen.getByText('algo se rompió')).toBeInTheDocument())
    expect(screen.getByText('RuntimeError:', { exact: false })).toBeInTheDocument()

    fireEvent.click(screen.getByText('Auditoría'))
    await waitFor(() => expect(screen.getByText('role_changed')).toBeInTheDocument())
  })

  it('shows an empty state when there are no errors', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({ items: [], total: 0, page: 1, page_size: 25 }),
            { status: 200 },
          ),
      ),
    )

    renderPage()

    await waitFor(() =>
      expect(screen.getByText('Sin errores registrados')).toBeInTheDocument(),
    )
  })
})
