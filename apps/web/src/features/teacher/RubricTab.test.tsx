import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { RubricTab } from './RubricTab'

const LANGUAGES = [
  { id: 'lang-1', name: 'PSeInt', slug: 'pseint', syntax_mode: 'pseint', is_active: true },
]

const TEMPLATES = [
  {
    id: 'tpl-1',
    name: 'Guía de laboratorio',
    sections: [{ heading: 'Objetivos', instructions: 'Lista 3 objetivos.' }],
    tone: 'cercano',
    target_level: 'basico',
    version: 1,
    is_active: true,
    created_at: '2026-07-20T10:00:00Z',
  },
]

function run(overrides: Record<string, unknown> = {}) {
  return {
    id: 'run-1',
    group_id: 'group-1',
    folder_id: 'folder-1',
    template_id: 'tpl-1',
    language_id: 'lang-1',
    name: 'Temario primer periodo',
    exercise_types: ['multiple_choice'],
    acquire_content: true,
    status: 'running',
    error_message: null,
    completed_at: null,
    created_at: '2026-07-26T10:00:00Z',
    ...overrides,
  }
}

function item(overrides: Record<string, unknown> = {}) {
  return {
    id: 'item-1',
    topic_name: 'Estructuras condicionales',
    level: 'basico',
    order_index: 0,
    topic_id: null,
    guide_id: null,
    sources_ingested: 0,
    exercises_created: 0,
    status: 'pending',
    error_message: null,
    ...overrides,
  }
}

type Call = { url: string; method: string; body: string }

/** Misma estrategia que `GuidesTab.test.tsx`: enruta por URL (las queries salen
 * en paralelo) y gana la clave más larga, porque `rubric-runs` es prefijo de
 * `rubric-runs/run-1`. */
function stubApi(routes: Record<string, unknown>, calls?: Call[]) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
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
      <RubricTab groupId="group-1" />
    </QueryClientProvider>,
  )
}

describe('RubricTab', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('muestra el estado vacío cuando no hay corridas', async () => {
    stubApi({ 'rubric-runs': [], languages: LANGUAGES, 'guide-templates': TEMPLATES })
    renderTab()

    await waitFor(() =>
      expect(screen.getByText('Todavía no has generado ningún temario')).toBeInTheDocument(),
    )
  })

  it('advierte que todo queda como borrador', async () => {
    // §9.2: la plataforma nunca publica contenido de IA sola. Si esta promesa
    // desaparece de la UI, el docente cree que el temario ya está en vivo.
    stubApi({ 'rubric-runs': [], languages: LANGUAGES, 'guide-templates': TEMPLATES })
    renderTab()

    await waitFor(() => expect(screen.getByText(/borrador/)).toBeInTheDocument())
  })

  it('envía la rúbrica con un tema por línea y el nivel por sufijo', async () => {
    const calls: Call[] = []
    stubApi(
      {
        'rubric-runs': [],
        languages: LANGUAGES,
        'guide-templates': TEMPLATES,
      },
      calls,
    )
    renderTab()
    await waitFor(() => expect(screen.getByLabelText('Lenguaje')).toBeInTheDocument())

    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Nombre de la rúbrica'), 'Temario 1')
    await user.type(screen.getByLabelText('Carpeta de guías'), 'Guías 10-A')
    await user.selectOptions(screen.getByLabelText('Lenguaje'), 'lang-1')
    await user.selectOptions(screen.getByLabelText('Plantilla de guía'), 'tpl-1')
    await user.type(
      screen.getByLabelText('Temas, uno por línea'),
      'Condicionales\nCiclos | intermedio',
    )
    await user.click(screen.getByRole('button', { name: 'Generar contenido' }))

    await waitFor(() => {
      const post = calls.find((call) => call.method === 'POST')
      expect(post).toBeDefined()
      const body = JSON.parse(post!.body)
      expect(body.items).toEqual([
        { topic_name: 'Condicionales', level: 'basico', extra_urls: [] },
        { topic_name: 'Ciclos', level: 'intermedio', extra_urls: [] },
      ])
    })
  })

  it('rechaza más de 15 temas antes de enviar', async () => {
    // El backend responde 409; avisar acá evita que el docente escriba 30 temas
    // y solo se entere al final.
    stubApi({ 'rubric-runs': [], languages: LANGUAGES, 'guide-templates': TEMPLATES })
    renderTab()
    await waitFor(() => expect(screen.getByLabelText('Temas, uno por línea')).toBeInTheDocument())

    const user = userEvent.setup()
    const temas = Array.from({ length: 16 }, (_, i) => `Tema ${i + 1}`).join('\n')
    await user.type(screen.getByLabelText('Temas, uno por línea'), temas)

    expect(screen.getByText(/Máximo 15 temas por corrida/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Generar contenido' })).toBeDisabled()
  })

  it('muestra el progreso por tema de la corrida en curso', async () => {
    stubApi({
      'rubric-runs': [run()],
      'rubric-runs/run-1': {
        run: run(),
        items: [
          item({ status: 'done', sources_ingested: 2, exercises_created: 3 }),
          item({ id: 'item-2', topic_name: 'Ciclos', status: 'writing_guide' }),
        ],
      },
      languages: LANGUAGES,
      'guide-templates': TEMPLATES,
    })
    renderTab()

    await waitFor(() => expect(screen.getByText('Listo')).toBeInTheDocument())
    expect(screen.getByText('Redactando guía…')).toBeInTheDocument()
    expect(screen.getByText('2 fuentes')).toBeInTheDocument()
    expect(screen.getByText('3 ejercicios')).toBeInTheDocument()
  })

  it('distingue una corrida parcial de una completa', async () => {
    // 8 de 10 temas es el resultado común bajo el tier gratuito: la UI no puede
    // presentarlo como éxito total.
    stubApi({
      'rubric-runs': [run({ status: 'partial', error_message: 'Alcanzaste el límite diario' })],
      'rubric-runs/run-1': {
        run: run({ status: 'partial', error_message: 'Alcanzaste el límite diario' }),
        items: [item({ status: 'done' }), item({ id: 'item-2', status: 'failed' })],
      },
      languages: LANGUAGES,
      'guide-templates': TEMPLATES,
    })
    renderTab()

    // Una corrida terminada no se abre sola —solo la que sigue viva—, así que el
    // detalle se pide con clic, igual que haría el docente al volver después.
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Temario primer periodo/ })).toBeInTheDocument(),
    )
    await userEvent.setup().click(screen.getByRole('button', { name: /Temario primer periodo/ }))

    await waitFor(() =>
      expect(screen.getByText('Alcanzaste el límite diario')).toBeInTheDocument(),
    )
    expect(screen.getAllByText('Completada parcialmente').length).toBeGreaterThan(0)
  })
})
