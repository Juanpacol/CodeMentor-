import { AxeBuilder } from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'

/** Fase 2 (ítem 3 + 7): la única forma automatizada de cazar un supuesto de
 * modo oscuro que el grep no puede ver — un token usado con la semántica
 * equivocada, un contraste que solo falla en un modo. Corre axe DOS veces
 * por página, una por tema. Solo páginas públicas — no requieren la API/DB
 * corriendo, a diferencia de los otros 3 specs. */

async function forceTheme(page: Page, theme: 'light' | 'dark') {
  // Solo se siembra localStorage — el propio script de arranque de
  // index.html (inline, antes del primer pintado) es quien lee esta clave y
  // aplica `data-theme`/`color-scheme` sobre <html>. Manipular
  // `document.documentElement` directamente desde acá es poco confiable:
  // `addInitScript` puede ejecutarse en un punto donde `documentElement`
  // todavía es `null` (el parser aún no creó el nodo <html>), lo que hace
  // fallar esa asignación en silencio. Delegar en el boot script real
  // también prueba el camino de producción de punta a punta, no una
  // reimplementación paralela en el test.
  await page.addInitScript(`localStorage.setItem('cm-theme', ${JSON.stringify(theme)});`)
}

const PUBLIC_ROUTES = ['/', '/login', '/registro', '/recuperar'] as const

for (const theme of ['light', 'dark'] as const) {
  for (const route of PUBLIC_ROUTES) {
    test(`${route || '/'} no tiene violaciones de accesibilidad en modo ${theme}`, async ({
      page,
    }) => {
      await forceTheme(page, theme)
      await page.goto(route)
      await expect(page.locator('html')).toHaveAttribute('data-theme', theme)

      // Varias páginas públicas animan su entrada con framer-motion
      // (opacity 0→1, ~250-600ms). `reducedMotion="user"` de motion NO
      // suprime fades de opacidad (solo transform/layout), así que sin esta
      // espera axe puede capturar el DOM a mitad de la transición y reportar
      // un contraste "roto" que en realidad es un frame intermedio — no el
      // estado final ya asentado.
      await page.waitForTimeout(1200)

      const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()

      expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([])
    })
  }
}

test('el toggle cambia data-theme y persiste en localStorage', async ({ page }) => {
  await forceTheme(page, 'dark')
  await page.goto('/login')
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')

  const toggle = page.getByRole('button', { name: /Cambiar a modo/ })
  await toggle.click()

  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  const stored = await page.evaluate(() => localStorage.getItem('cm-theme'))
  expect(stored).toBe('light')
})
