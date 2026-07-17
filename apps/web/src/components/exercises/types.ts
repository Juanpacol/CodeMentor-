export interface ExerciseRendererProps<TAnswer = Record<string, unknown>> {
  content: Record<string, unknown>
  value: TAnswer | undefined
  onChange: (value: TAnswer) => void
  disabled?: boolean
}
