import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Markdown } from './Markdown'

describe('Markdown', () => {
  it('renderiza encabezados, listas y bloques de código de una guía', () => {
    const { container } = render(
      <Markdown md={'## Objetivos\n\n- Uno\n- Dos\n\n```\nEscribir "hola"\n```'} />,
    )

    expect(screen.getByRole('heading', { level: 2, name: 'Objetivos' })).toBeInTheDocument()
    expect(container.querySelectorAll('li')).toHaveLength(2)
    expect(container.querySelector('pre code')?.textContent).toContain('Escribir "hola"')
  })

  it('elimina scripts y manejadores de eventos del contenido del modelo', () => {
    // El `body_md` lo escribió un LLM sobre material que puede venir de un
    // archivo subido: sin sanitizar, esto se ejecutaría en el navegador del
    // estudiante.
    const { container } = render(
      <Markdown md={'<script>window.robado = 1</script>\n\n<p onclick="alert(1)">texto</p>'} />,
    )

    expect(container.querySelector('script')).toBeNull()
    expect(container.innerHTML).not.toContain('onclick')
    expect(container.innerHTML).not.toContain('window.robado')
  })

  it('descarta imágenes, que la CSP de producción bloquearía', () => {
    // `img-src 'self' data:` en vercel.json: una imagen remota se vería como un
    // hueco roto, así que no se renderiza en absoluto.
    const { container } = render(<Markdown md={'![gato](https://ejemplo.com/gato.png)'} />)

    expect(container.querySelector('img')).toBeNull()
  })

  it('no emite h1: el título de la guía ya ocupa ese nivel en la página', () => {
    const { container } = render(<Markdown md={'# Título que no debería existir'} />)

    expect(container.querySelector('h1')).toBeNull()
  })

  it('conserva enlaces con su href pero descarta atributos no permitidos', () => {
    const { container } = render(
      <Markdown md={'<a href="https://docs.python.org" target="_blank" style="color:red">docs</a>'} />,
    )

    const link = container.querySelector('a')
    expect(link?.getAttribute('href')).toBe('https://docs.python.org')
    expect(link?.getAttribute('style')).toBeNull()
    expect(link?.getAttribute('target')).toBeNull()
  })
})
