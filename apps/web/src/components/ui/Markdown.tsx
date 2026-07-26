import DOMPurify from 'dompurify'
import { marked } from 'marked'
import { useMemo } from 'react'

import { cn } from '../../lib/cn'

/** Etiquetas permitidas en una guía. Allowlist y no denylist: el contenido lo
 * escribió un LLM, así que la pregunta correcta es "qué necesita una guía" y no
 * "qué podría salir mal".
 *
 * Notas sobre lo que NO está:
 * - `img`: la CSP de producción es `img-src 'self' data:` (ver vercel.json), así
 *   que una imagen externa se bloquearía y el estudiante vería un hueco roto. La
 *   plantilla del prompt ya le pide al modelo que no emita `![]()`; esto es la
 *   red por si igual lo hace.
 * - `h1`: el título de la guía ya es el h1 de la página; permitirlo rompería la
 *   jerarquía de encabezados para un lector de pantalla.
 * - `style` como atributo: con `style-src 'self'` los estilos en línea se
 *   ignorarían de todos modos, y son el vector clásico de este tipo de render. */
const ALLOWED_TAGS = [
  'h2',
  'h3',
  'h4',
  'p',
  'ul',
  'ol',
  'li',
  'code',
  'pre',
  'strong',
  'em',
  'blockquote',
  'a',
  'hr',
  'br',
  'table',
  'thead',
  'tbody',
  'tr',
  'th',
  'td',
]

const ALLOWED_ATTR = ['href', 'title']

/** Renderiza el markdown de una guía. `dangerouslySetInnerHTML` es intencional y
 * seguro acá porque la sanitización pasa por DOMPurify con la allowlist de
 * arriba — sin ella, un `body_md` con un `<script>` (por prompt injection en el
 * material del curso, p.ej.) se ejecutaría. */
export function Markdown({ md, className }: { md: string; className?: string }) {
  const html = useMemo(() => {
    // `marked.parse` es sincrónico mientras no se registren extensiones async;
    // el cast evita el `string | Promise<string>` de su firma pública.
    const raw = marked.parse(md, { async: false }) as string
    return DOMPurify.sanitize(raw, { ALLOWED_TAGS, ALLOWED_ATTR })
  }, [md])

  return (
    <div
      className={cn('guide-content', className)}
      // eslint-disable-next-line react/no-danger -- sanitizado con DOMPurify arriba
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}
