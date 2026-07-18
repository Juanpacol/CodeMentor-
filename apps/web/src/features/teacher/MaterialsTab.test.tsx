import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { MaterialsTab } from './MaterialsTab'

const CURRICULUM_RESPONSE = [
  {
    topic: { id: 'topic-1', name: 'Ciclos', language_id: 'lang-1', level: 'basico', order_index: 1 },
    state: 'enabled',
    enabled_at: new Date().toISOString(),
    scheduled_enable_at: null,
  },
]

const DOCUMENTS_RESPONSE = [
  {
    id: 'doc-1',
    title: 'Guía de ciclos',
    source_type: 'teacher_material',
    topic_id: 'topic-1',
    chunk_count: 3,
    created_at: new Date().toISOString(),
  },
]

function renderTab() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MaterialsTab groupId="group-1" />
    </QueryClientProvider>,
  )
}

describe('MaterialsTab', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('lists documents with their topic name', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = input instanceof Request ? input.url : String(input)
        if (url.includes('/ai/rag/documents')) {
          return new Response(JSON.stringify(DOCUMENTS_RESPONSE), { status: 200 })
        }
        return new Response(JSON.stringify(CURRICULUM_RESPONSE), { status: 200 })
      }),
    )

    renderTab()

    await waitFor(() => expect(screen.getByText('Guía de ciclos')).toBeInTheDocument())
    expect(screen.getByText(/Ciclos · 3 fragmento/)).toBeInTheDocument()
  })

  it('shows an empty state when there is no material yet', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = input instanceof Request ? input.url : String(input)
        if (url.includes('/ai/rag/documents')) {
          return new Response(JSON.stringify([]), { status: 200 })
        }
        return new Response(JSON.stringify([]), { status: 200 })
      }),
    )

    renderTab()

    await waitFor(() =>
      expect(screen.getByText('Aún no hay material cargado')).toBeInTheDocument(),
    )
  })

  it('opens the upload dialog', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify([]), { status: 200 })),
    )

    renderTab()
    await waitFor(() =>
      expect(screen.getByText('Aún no hay material cargado')).toBeInTheDocument(),
    )

    fireEvent.click(screen.getByText('Cargar material'))
    expect(screen.getByText('General (sin tema)')).toBeInTheDocument()
  })
})
