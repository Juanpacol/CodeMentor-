import CodeMirror from '@uiw/react-codemirror'

import { getCodeMirrorExtensions } from '../../lib/codemirror/getExtensions'
import { useTheme } from '../../lib/theme'
import type { ExerciseRendererProps } from './types'

interface LiveCodeAnswer {
  code: string
}

export function LiveCodeRenderer({
  content,
  value,
  onChange,
  disabled,
}: ExerciseRendererProps<LiveCodeAnswer>) {
  const statement = String(content.statement ?? '')
  const starterCode = String(content.starter_code ?? '')
  const language = String(content.language ?? 'python')
  const code = value?.code ?? starterCode
  const theme = useTheme()

  return (
    <div>
      <p className="mb-4 text-base text-ink">{statement}</p>
      <div className="overflow-hidden rounded-card border border-hairline-strong">
        <CodeMirror
          value={code}
          height="260px"
          theme={theme}
          editable={!disabled}
          extensions={getCodeMirrorExtensions(language)}
          onChange={(next) => onChange({ code: next })}
        />
      </div>
    </div>
  )
}
