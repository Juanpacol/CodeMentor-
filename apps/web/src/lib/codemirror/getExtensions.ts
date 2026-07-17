import { python } from '@codemirror/lang-python'
import type { Extension } from '@codemirror/state'

import { pseintLanguage } from './pseint'

/** Elige la extensión de CodeMirror según `syntax_mode`/`language` — los
 * lenguajes son datos configurables (RE-06), así que el frontend nunca
 * debe tener un switch cerrado de "los lenguajes que existen hoy": un
 * `syntax_mode` desconocido cae a texto plano en vez de romper. */
export function getCodeMirrorExtensions(syntaxMode: string): Extension[] {
  switch (syntaxMode.toLowerCase()) {
    case 'pseint':
      return [pseintLanguage]
    case 'python':
      return [python()]
    default:
      return []
  }
}
