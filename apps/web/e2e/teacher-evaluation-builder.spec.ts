import { expect, test } from '@playwright/test'

import {
  attachExercise,
  createExercise,
  createGroup,
  createLanguage,
  createTopic,
  enableTopic,
  registerAndLogin,
} from './fixtures.js'

/** Flujo 2: un docente crea una evaluación con alcance (fija, hasta un
 * tema) desde el constructor, seleccionando ejercicios del banco — verifica
 * que el wizard completo funciona y que la API acepta la creación. */
test('docente crea una evaluación con alcance fijo hasta un tema', async ({ page }) => {
  const runId = Date.now()
  const teacher = await registerAndLogin('teacher', 'doc-e2e2')

  const language = await createLanguage(teacher, `e2e2-${runId}`)
  const topicName = `Tema E2E2 ${runId}`
  const topic = await createTopic(teacher, language.id, topicName)
  const groupName = `Grupo E2E2 ${runId}`
  const group = await createGroup(teacher, groupName)
  await enableTopic(teacher, group.id, topic.id)

  const exerciseTitle = `V o F E2E2 ${runId}`
  const exercise = await createExercise(teacher, language.id, exerciseTitle, 'true_false', {
    statement: '¿2+2 es 4?',
    answer: true,
  })
  await attachExercise(teacher, exercise.id, topic.id)

  await page.goto('/login')
  await page.fill('#email', teacher.email)
  await page.fill('#password', teacher.password)
  await page.click('button[type=submit]')
  await page.waitForURL('**/app/docente')

  await page.goto('/app/docente/evaluaciones/nueva')
  await page.fill('#title', `Quiz E2E2 ${runId}`)
  await page.selectOption('#group', { label: groupName })
  await page.selectOption('#mode', 'fixed')
  await page.selectOption('#up_to_topic', { label: topicName })
  await page.getByText(exerciseTitle).click()

  await page.locator('button[type=submit]').click()
  await page.waitForURL('**/app/docente/evaluaciones/**', { timeout: 15_000 })

  await expect(page.getByText('Gestión de evaluación')).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Respuestas' })).toBeVisible()
})
