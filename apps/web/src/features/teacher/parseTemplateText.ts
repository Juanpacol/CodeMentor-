export type ParsedSection = { heading: string; instructions: string }

/** Convierte un formato de guía pegado o subido en secciones editables.
 *
 * Existe porque armar una plantilla obligaba a crear las secciones fila por
 * fila, y el docente casi siempre YA tiene el formato escrito en Word o en un
 * documento compartido — igual que `parseTopics` en `RubricTab`, que nació de
 * que el temario ya existía en otro lado.
 *
 * Dos formas de reconocer una sección, en orden de confianza:
 *
 * 1. **Encabezados markdown** (`#`, `##`, …). Si el texto trae aunque sea uno,
 *    manda esa estructura: es explícita y no hay que adivinar.
 * 2. **Bloques separados por línea en blanco**, con la primera línea como
 *    título y el resto como instrucciones. Es la forma de los formatos
 *    institucionales pegados desde Word.
 *
 * El resultado es un punto de partida editable, nunca algo que se guarde
 * directo: el `heading` sin cuerpo o unas instrucciones demasiado cortas son
 * casos normales que el docente completa antes de guardar.
 */
export function parseTemplateText(raw: string): ParsedSection[] {
  const text = raw.replace(/\r\n/g, '\n').trim()
  if (!text) return []

  return /^#{1,6}\s+/m.test(text) ? parseByHeadings(text) : parseByBlocks(text)
}

function parseByHeadings(text: string): ParsedSection[] {
  const sections: ParsedSection[] = []
  let current: ParsedSection | null = null

  for (const line of text.split('\n')) {
    const heading = /^#{1,6}\s+(.*)$/.exec(line)
    if (heading) {
      if (current) sections.push(current)
      current = { heading: heading[1].trim(), instructions: '' }
      continue
    }
    // Texto antes del primer encabezado: es el título del documento, no una
    // sección. Descartarlo evita una fila basura que el docente tendría que
    // borrar siempre.
    if (current) current.instructions += `${line}\n`
  }
  if (current) sections.push(current)

  return sections.map(clean).filter((section) => section.heading.length > 0)
}

function parseByBlocks(text: string): ParsedSection[] {
  return text
    .split(/\n\s*\n/)
    .map((block) => {
      const [first, ...rest] = block.split('\n')
      return { heading: first.trim(), instructions: rest.join('\n') }
    })
    .map(clean)
    .filter((section) => section.heading.length > 0)
}

function clean(section: ParsedSection): ParsedSection {
  return {
    // Los formatos de Word suelen traer viñetas y numeración pegadas al título.
    heading: section.heading.replace(/^[•\-*\d.\s]+/, '').trim().slice(0, 200),
    instructions: section.instructions.trim().slice(0, 1000),
  }
}
