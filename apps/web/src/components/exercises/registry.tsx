import { ArguedResponseRenderer } from './ArguedResponseRenderer'
import { FillCodeRenderer } from './FillCodeRenderer'
import { FindErrorRenderer } from './FindErrorRenderer'
import { LiveCodeRenderer } from './LiveCodeRenderer'
import { MultipleChoiceRenderer } from './MultipleChoiceRenderer'
import { OrderLinesRenderer } from './OrderLinesRenderer'
import { TraceVariablesRenderer } from './TraceVariablesRenderer'
import { TrueFalseRenderer } from './TrueFalseRenderer'
import type { ExerciseRendererProps } from './types'

export type ExerciseType =
  | 'true_false'
  | 'multiple_choice'
  | 'fill_code'
  | 'find_error'
  | 'trace_variables'
  | 'order_lines'
  | 'argued_response'
  | 'live_code'

// RE-05 en el frontend: agregar un noveno tipo es una entrada más en este
// registro + un componente, nunca tocar el resto de la práctica/evaluación.
export const exerciseRenderers: Record<
  ExerciseType,
  (props: ExerciseRendererProps<never>) => React.ReactElement
> = {
  true_false: TrueFalseRenderer as never,
  multiple_choice: MultipleChoiceRenderer as never,
  fill_code: FillCodeRenderer as never,
  find_error: FindErrorRenderer as never,
  trace_variables: TraceVariablesRenderer as never,
  order_lines: OrderLinesRenderer as never,
  argued_response: ArguedResponseRenderer as never,
  live_code: LiveCodeRenderer as never,
}

export const EXERCISE_TYPE_LABELS: Record<ExerciseType, string> = {
  true_false: 'Verdadero o falso',
  multiple_choice: 'Selección múltiple',
  fill_code: 'Completar código',
  find_error: 'Encontrar el error',
  trace_variables: 'Trazado de variables',
  order_lines: 'Ordenar líneas',
  argued_response: 'Respuesta argumentada',
  live_code: 'Reto de código en vivo',
}
