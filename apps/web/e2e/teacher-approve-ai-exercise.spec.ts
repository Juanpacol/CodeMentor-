import { expect, test } from '@playwright/test'

import { createLanguage, insertAiDraftExercise, registerAndLogin } from './fixtures.js'

/** Flujo 3: un docente aprueba (publica) un ejercicio generado por IA desde
 * la bandeja de aprobaciones (RF-32/33, §9.6). El borrador se inserta
 * directamente en la base de datos (ver fixtures.insertAiDraftExercise) ya
 * que forzar una generación real exitosa requeriría API keys de un
 * proveedor LLM configuradas — algo que este entorno local no tiene ni
 * necesita para probar la UI de aprobación en sí. */
test('docente aprueba un ejercicio generado por IA desde la bandeja', async ({ page }) => {
  const teacher = await registerAndLogin('teacher', 'doc-e2e3')
  const language = await createLanguage(teacher, 'e2e3')
  const title = `Ejercicio IA E2E3 ${Date.now()}`
  await insertAiDraftExercise(teacher.email, language.id, title)

  await page.goto('/login')
  await page.fill('#email', teacher.email)
  await page.fill('#password', teacher.password)
  await page.click('button[type=submit]')
  await page.waitForURL('**/app/docente')

  await page.goto('/app/docente/bandeja')
  await expect(page.getByText(title)).toBeVisible()

  await page
    .locator('.rounded-card')
    .filter({ hasText: title })
    .getByRole('button', { name: 'Publicar' })
    .click()

  await expect(page.getByText(title)).not.toBeVisible()
  await expect(page.getByText('No hay nada pendiente de aprobación')).toBeVisible()

  await page.goto('/app/docente/ejercicios')
  await expect(page.getByText(title)).toBeVisible()
  await expect(page.getByText('Publicado').first()).toBeVisible()
})
