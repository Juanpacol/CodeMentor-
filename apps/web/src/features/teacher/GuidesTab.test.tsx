import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { GuidesTab } from './GuidesTab'

const FOLDER = {
  id: 'folder-1',
  group_id: 'group-1',
  name: 'Guías 10-1',
  description: null,
  auto_generate_template_id: null,
  created_at: '2026-07-20T10:00:00Z',
}

const TEMPLATE = {
  id: 'tpl-1',
  name: 'Guía de laboratorio',
  sections: [{ heading: 'Objetivos', instructions: 'Lista 3 objetivos.' }],
  tone: 'cercano',
  target_level: 'basico',
  version: 1,
  is_active: true,
  created_at: '2026-07-20T10:00:00Z',
}

const CURRICULUM = [
  {
    topic: {
      id: 'topic-1',
      institution_id: 'inst-1',
      language_id: 'lang-1',
      name: 'Ciclos',
      level: 'basico',
      order_index: 1,
      version: 1,
    },
    state: 'enabled',
    enabled_at: '2026-07-21T10:00:00Z',
    scheduled_enable_at: null,
  },
]

function guide(overrides: Record<string, unknown> = {}) {
  return {
    id: 'guide-1',
    folder_id: 'folder-1',
    template_id: 'tpl-1',
    topic_id: 'topic-1',
    title: 'Guía de laboratorio — Ciclos',
    content_md: '## Objetivos\n\n- Reconocer un ciclo.',
    origin: 'ai',
    status: 'draft',
    published_at: null,
    error_message: null,
    sources: ['Apuntes de ciclos'],
    prompt_version: 1,
    created_at: '2026-07-21T10:00:00Z',
    ...overrides,
  }
}

type Call = { url: string; method: string; body: string }

/** Enruta por URL en vez de por orden de llamada: la pestaña lanza cuatro
 * queries en paralelo y su orden de resolución no está garantizado.
 *
 * Gana la clave MÁS LARGA que coincida, no la primera: `guide-folders` es
 * prefijo de `guide-folders/folder-1/guides`, así que un `find` devolvería la
 * carpeta cuando se piden las guías. */
function stubApi(routes: Record<string, unknown>, calls?: Call[]) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      // openapi-fetch siempre pasa un Request; su `body` es un stream de un solo
      // uso, así que hay que clonarlo para poder leerlo sin consumirlo.
      const request = input as Request
      const url = typeof input === 'string' ? input : request.url
      if (calls && typeof input !== 'string') {
        calls.push({
          url,
          method: request.method,
          body: request.method === 'GET' ? '' : await request.clone().text(),
        })
      }
      const match = Object.keys(routes)
        .filter((key) => url.includes(key))
        .sort((a, b) => b.length - a.length)[0]
      return new Response(JSON.stringify(match ? routes[match] : []), { status: 200 })
    }),
  )
}

function renderTab() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <GuidesTab groupId="group-1" />
    </QueryClientProvider>,
  )
}

describe('GuidesTab', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('muestra el estado vacío cuando el grupo no tiene carpetas', async () => {
    stubApi({ 'guide-folders': [], 'guide-templates': [], curriculum: CURRICULUM })
    renderTab()

    await waitFor(() =>
      expect(screen.getByText('Aún no hay carpetas de guías')).toBeInTheDocument(),
    )
  })

  it('etiqueta un borrador como generado por IA y ofrece publicarlo', async () => {
    stubApi({
      'guide-folders': [FOLDER],
      'guide-templates': [TEMPLATE],
      curriculum: CURRICULUM,
      'folder-1/guides': [guide()],
    })
    renderTab()

    const item = await screen.findByRole('button', { name: /Guía de laboratorio — Ciclos/ })
    // La etiqueta de IA es requisito, no decoración (§9.2 / RF-35).
    expect(screen.getByText('Borrador · IA')).toBeInTheDocument()

    await userEvent.click(item)

    expect(await screen.findByRole('button', { name: 'Publicar' })).toBeInTheDocument()
    // El docente puede verificar de qué material salió antes de publicar.
    expect(screen.getByText('Apuntes de ciclos')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 2, name: 'Objetivos' })).toBeInTheDocument()
  })

  it('una guía publicada no ofrece el botón de publicar', async () => {
    stubApi({
      'guide-folders': [FOLDER],
      'guide-templates': [TEMPLATE],
      curriculum: CURRICULUM,
      'folder-1/guides': [guide({ status: 'published', published_at: '2026-07-22T10:00:00Z' })],
    })
    renderTab()

    await userEvent.click(
      await screen.findByRole('button', { name: /Guía de laboratorio — Ciclos/ }),
    )

    // El estado aparece en la fila de la lista y en el diálogo; se acota al
    // diálogo, que es lo que este test abrió.
    const dialog = within(screen.getByRole('dialog'))
    expect(dialog.getByText('Publicada')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Publicar' })).not.toBeInTheDocument()
    expect(dialog.getByRole('button', { name: 'Archivar' })).toBeInTheDocument()
    // Publicada: solo se archiva, nunca se borra (§9.2).
    expect(dialog.queryByRole('button', { name: 'Quitar' })).not.toBeInTheDocument()
  })

  it('quitar un borrador pide confirmación antes de llamar al backend', async () => {
    const calls: Call[] = []
    stubApi(
      {
        'guide-folders': [FOLDER],
        'guide-templates': [TEMPLATE],
        curriculum: CURRICULUM,
        'folder-1/guides': [guide()],
      },
      calls,
    )
    renderTab()

    await userEvent.click(
      await screen.findByRole('button', { name: /Guía de laboratorio — Ciclos/ }),
    )
    const dialog = within(screen.getByRole('dialog'))
    await userEvent.click(dialog.getByRole('button', { name: 'Quitar' }))

    // Un clic no basta: primero pide confirmar.
    expect(dialog.getByText(/No se puede deshacer/)).toBeInTheDocument()
    expect(calls.some((call) => call.method === 'DELETE')).toBe(false)

    await userEvent.click(dialog.getByRole('button', { name: 'Sí, quitar' }))

    await waitFor(() => expect(calls.some((call) => call.method === 'DELETE')).toBe(true))
  })

  it('muestra el motivo cuando la generación falló', async () => {
    stubApi({
      'guide-folders': [FOLDER],
      'guide-templates': [TEMPLATE],
      curriculum: CURRICULUM,
      'folder-1/guides': [
        guide({
          status: 'failed',
          content_md: '',
          sources: null,
          error_message: 'Alcanzaste el límite diario de uso del asistente de IA.',
        }),
      ],
    })
    renderTab()

    await userEvent.click(
      await screen.findByRole('button', { name: /Guía de laboratorio — Ciclos/ }),
    )

    expect(screen.getByText(/límite diario/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Publicar' })).not.toBeInTheDocument()
  })

  it('activar la autogeneración envía la plantilla elegida al backend', async () => {
    const calls: Call[] = []
    stubApi(
      {
        'guide-folders': [FOLDER],
        'guide-templates': [TEMPLATE],
        curriculum: CURRICULUM,
        'folder-1/guides': [],
      },
      calls,
    )
    renderTab()

    const select = await screen.findByLabelText('Autogenerar al habilitar un tema')
    await userEvent.selectOptions(select, 'tpl-1')

    await waitFor(() => expect(calls.some((c) => c.method === 'PATCH')).toBe(true))
    const patch = calls.find((c) => c.method === 'PATCH')!
    expect(patch.url).toContain('/guide-folders/folder-1')
    expect(JSON.parse(patch.body)).toEqual({ auto_generate_template_id: 'tpl-1' })
  })
})
