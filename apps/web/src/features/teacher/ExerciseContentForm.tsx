import { useState } from 'react'

import { Button } from '../../components/ui/Button'
import { FieldError, Input, Textarea } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import type { ExerciseType } from '../../components/exercises/registry'

interface Props {
  type: ExerciseType
  value: Record<string, unknown>
  onChange: (value: Record<string, unknown>) => void
}

function DynamicList({
  items,
  onChange,
  placeholder,
}: {
  items: string[]
  onChange: (items: string[]) => void
  placeholder: string
}) {
  return (
    <div className="flex flex-col gap-2">
      {items.map((item, i) => (
        <div key={i} className="flex gap-2">
          <Input
            value={item}
            placeholder={`${placeholder} ${i + 1}`}
            onChange={(e) => {
              const next = [...items]
              next[i] = e.target.value
              onChange(next)
            }}
          />
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => onChange(items.filter((_, idx) => idx !== i))}
          >
            ✕
          </Button>
        </div>
      ))}
      <Button type="button" variant="secondary" size="sm" onClick={() => onChange([...items, ''])}>
        + agregar
      </Button>
    </div>
  )
}

/** Formulario de autoría por tipo de ejercicio (RE-05 también del lado del
 * autor) — deliberadamente más simple que los renderers de práctica: aquí
 * el docente escribe la clave de respuesta, no la resuelve. Para los dos
 * campos más "estructurales" (expected_trace, test_cases) un textarea JSON
 * es más honesto que fingir una UI dedicada para un caso de uso poco
 * frecuente. */
export function ExerciseContentForm({ type, value, onChange }: Props) {
  const [jsonError, setJsonError] = useState<string | null>(null)

  function set(patch: Record<string, unknown>) {
    onChange({ ...value, ...patch })
  }

  function setJsonField(field: string, raw: string) {
    try {
      set({ [field]: raw.trim() ? JSON.parse(raw) : undefined })
      setJsonError(null)
    } catch {
      setJsonError(`"${field}" no es JSON válido`)
    }
  }

  switch (type) {
    case 'true_false':
      return (
        <div className="flex flex-col gap-3">
          <Textarea
            placeholder="Enunciado"
            value={String(value.statement ?? '')}
            onChange={(e) => set({ statement: e.target.value })}
          />
          <label className="flex items-center gap-2 text-sm text-ink">
            <input
              type="checkbox"
              checked={Boolean(value.answer)}
              onChange={(e) => set({ answer: e.target.checked })}
            />
            El enunciado es verdadero
          </label>
        </div>
      )

    case 'multiple_choice': {
      const options = Array.isArray(value.options) ? (value.options as string[]) : ['']
      return (
        <div className="flex flex-col gap-3">
          <Textarea
            placeholder="Enunciado"
            value={String(value.statement ?? '')}
            onChange={(e) => set({ statement: e.target.value })}
          />
          <DynamicList items={options} onChange={(next) => set({ options: next })} placeholder="Opción" />
          <div>
            <label className="mb-1.5 block text-sm text-ink-secondary">Opción correcta</label>
            <Select
              value={String(value.answer_index ?? '')}
              onChange={(e) => set({ answer_index: Number(e.target.value) })}
            >
              <option value="">Selecciona</option>
              {options.map((opt, i) => (
                <option key={i} value={i}>
                  {opt || `Opción ${i + 1}`}
                </option>
              ))}
            </Select>
          </div>
        </div>
      )
    }

    case 'fill_code': {
      const blanks = Array.isArray(value.blanks) ? (value.blanks as string[]) : ['']
      return (
        <div className="flex flex-col gap-3">
          <Textarea
            placeholder="Enunciado"
            value={String(value.statement ?? '')}
            onChange={(e) => set({ statement: e.target.value })}
          />
          <div>
            <label className="mb-1.5 block text-sm text-ink-secondary">
              Código con espacios marcados como ___
            </label>
            <Textarea
              placeholder={'___ saludar():\n    print("Hola")'}
              value={String(value.code_template ?? '')}
              onChange={(e) => set({ code_template: e.target.value })}
              className="font-mono"
            />
          </div>
          <label className="block text-sm text-ink-secondary">
            Respuesta correcta de cada espacio, en orden
          </label>
          <DynamicList items={blanks} onChange={(next) => set({ blanks: next })} placeholder="Espacio" />
        </div>
      )
    }

    case 'find_error':
      return (
        <div className="flex flex-col gap-3">
          <Textarea
            placeholder="Enunciado"
            value={String(value.statement ?? '')}
            onChange={(e) => set({ statement: e.target.value })}
          />
          <Textarea
            placeholder="Código con el error"
            value={String(value.code ?? '')}
            onChange={(e) => set({ code: e.target.value })}
            className="font-mono"
          />
          <Input
            type="number"
            min={1}
            placeholder="Línea con el error (1-indexada)"
            value={String(value.error_line ?? '')}
            onChange={(e) => set({ error_line: Number(e.target.value) })}
          />
          <Select
            value={String(value.error_kind ?? '')}
            onChange={(e) => set({ error_kind: e.target.value || undefined })}
          >
            <option value="">Sin tipo de error específico</option>
            <option value="sintaxis">Sintaxis</option>
            <option value="logica">Lógica</option>
            <option value="tipos">Tipos</option>
          </Select>
        </div>
      )

    case 'trace_variables':
      return (
        <div className="flex flex-col gap-3">
          <Textarea
            placeholder="Enunciado"
            value={String(value.statement ?? '')}
            onChange={(e) => set({ statement: e.target.value })}
          />
          <Textarea
            placeholder="Código a trazar (opcional)"
            value={String(value.code ?? '')}
            onChange={(e) => set({ code: e.target.value })}
            className="font-mono"
          />
          <div>
            <label className="mb-1.5 block text-sm text-ink-secondary">
              Trazado esperado (JSON: lista de objetos variable→valor por paso)
            </label>
            <Textarea
              placeholder='[{"contador": 1}, {"contador": 3}]'
              defaultValue={JSON.stringify(value.expected_trace ?? [], null, 2)}
              onChange={(e) => setJsonField('expected_trace', e.target.value)}
              className="font-mono"
            />
            <FieldError>{jsonError}</FieldError>
          </div>
        </div>
      )

    case 'order_lines': {
      const lines = Array.isArray(value.lines) ? (value.lines as string[]) : ['']
      return (
        <div className="flex flex-col gap-3">
          <Textarea
            placeholder="Enunciado"
            value={String(value.statement ?? '')}
            onChange={(e) => set({ statement: e.target.value })}
          />
          <label className="block text-sm text-ink-secondary">
            Líneas de código (en el orden en que se mostrarán al estudiante)
          </label>
          <DynamicList items={lines} onChange={(next) => set({ lines: next })} placeholder="Línea" />
          <div>
            <label className="mb-1.5 block text-sm text-ink-secondary">
              Orden correcto (índices separados por coma, ej. 1,0,2)
            </label>
            <Input
              placeholder="1,0,2"
              defaultValue={(value.correct_order as number[] | undefined)?.join(',') ?? ''}
              onChange={(e) => {
                const parsed = e.target.value
                  .split(',')
                  .map((s) => s.trim())
                  .filter(Boolean)
                  .map(Number)
                set({ correct_order: parsed })
              }}
            />
          </div>
        </div>
      )
    }

    case 'argued_response':
      return (
        <Textarea
          placeholder="Pregunta o consigna"
          value={String(value.prompt ?? '')}
          onChange={(e) => set({ prompt: e.target.value })}
        />
      )

    case 'live_code':
      return (
        <div className="flex flex-col gap-3">
          <Textarea
            placeholder="Enunciado"
            value={String(value.statement ?? '')}
            onChange={(e) => set({ statement: e.target.value })}
          />
          <div className="grid grid-cols-2 gap-3">
            <Input
              placeholder="Lenguaje (ej. python)"
              value={String(value.language ?? 'python')}
              onChange={(e) => set({ language: e.target.value })}
            />
            <Input
              placeholder="Versión (ej. 3.10.0)"
              value={String(value.version ?? '3.10.0')}
              onChange={(e) => set({ version: e.target.value })}
            />
          </div>
          <Textarea
            placeholder="Código inicial para el estudiante"
            value={String(value.starter_code ?? '')}
            onChange={(e) => set({ starter_code: e.target.value })}
            className="font-mono"
          />
          <div>
            <label className="mb-1.5 block text-sm text-ink-secondary">
              Casos de prueba (JSON: lista de {'{stdin, expected_stdout}'})
            </label>
            <Textarea
              placeholder='[{"stdin": "2\\n3\\n", "expected_stdout": "5\\n"}]'
              defaultValue={JSON.stringify(value.test_cases ?? [], null, 2)}
              onChange={(e) => setJsonField('test_cases', e.target.value)}
              className="font-mono"
            />
            <FieldError>{jsonError}</FieldError>
          </div>
        </div>
      )

    default:
      return null
  }
}
