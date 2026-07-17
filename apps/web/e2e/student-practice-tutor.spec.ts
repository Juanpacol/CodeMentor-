import { expect, test } from '@playwright/test'

import {
  attachExercise,
  createExercise,
  createGroup,
  createLanguage,
  createTopic,
  enableTopic,
  joinGroup,
  registerAndLogin,
} from './fixtures.js'

/** Flujo 1: un estudiante practica y le pide una pista al tutor. Sin
 * proveedores de IA configurados (ninguna API key en el entorno local), el
 * harness responde 503 tras agotar la cadena de respaldo — el objetivo de
 * este test es justamente comprobar que esa degradación (§9.4) se ve como
 * un aviso amable en la UI, no como un error roto, sin gastar tokens
 * reales en el intento. */
test('estudiante practica y recibe degradación amable al pedir una pista de IA', async ({
  page,
}) => {
  const runId = Date.now()
  const teacher = await registerAndLogin('teacher', 'doc-e2e1')
  const student = await registerAndLogin('student', 'est-e2e1')

  const language = await createLanguage(teacher, `e2e1-${runId}`)
  const topic = await createTopic(teacher, language.id, `Tema E2E1 ${runId}`)
  const groupName = `Grupo E2E1 ${runId}`
  const group = await createGroup(teacher, groupName)
  await enableTopic(teacher, group.id, topic.id)

  const exerciseTitle = `V o F E2E1 ${runId}`
  const exercise = await createExercise(teacher, language.id, exerciseTitle, 'true_false', {
    statement: 'Python usa indentación significativa.',
    answer: true,
  })
  await attachExercise(teacher, exercise.id, topic.id)
  await joinGroup(student, group.invite_code)

  await page.goto('/login')
  await page.fill('#email', student.email)
  await page.fill('#password', student.password)
  await page.click('button[type=submit]')
  await page.waitForURL('**/app')

  await page.getByText(groupName).click()
  await page.waitForURL('**/app/grupos/**')
  await page.getByText('Ir a practicar').click()
  await page.waitForURL('**/practicar')

  await page.getByText(exerciseTitle).click()
  await expect(page.getByText('Python usa indentación significativa.')).toBeVisible()

  await page.getByRole('button', { name: 'Verdadero', exact: true }).click()
  await page.getByRole('button', { name: 'Enviar respuesta' }).click()
  await expect(page.getByText(/Correcto|Puntaje/)).toBeVisible()

  await page.fill(
    'textarea[placeholder="Cuéntale al tutor en qué estás atascado..."]',
    'No entiendo por qué es verdadero',
  )
  await page.getByRole('button', { name: 'Pedir pista' }).click()

  // La cadena de respaldo (Groq→Gemini→Ollama) sin API keys tarda varios
  // segundos en agotarse antes de responder 503 — de ahí el timeout largo.
  await expect(page.getByText('El asistente de IA no está disponible en este momento.')).toBeVisible({
    timeout: 30_000,
  })
})
