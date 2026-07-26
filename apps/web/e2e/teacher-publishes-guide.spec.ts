import { AxeBuilder } from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

import {
  createGroup,
  createGuideFolder,
  createGuideTemplate,
  createLanguage,
  createTopic,
  enableTopic,
  insertDraftGuide,
  joinGroup,
  registerAndLogin,
} from './fixtures.js'

/** Fase 16: el docente publica una guía redactada por IA y el estudiante la lee.
 *
 * Un solo spec para las dos mitades en vez de dos archivos: lo que importa
 * verificar es justo el traspaso — que el borrador NO se vea antes y sí después.
 * Probarlas por separado dejaría sin cubrir la transición, que es la regla de
 * §9.2 que esta fase implementa. */
test('docente publica una guía de IA y el estudiante la ve solo después', async ({ browser }) => {
  const teacher = await registerAndLogin('teacher', 'doc-guias')
  const student = await registerAndLogin('student', 'est-guias')
  const language = await createLanguage(teacher, 'guias')
  const topic = await createTopic(teacher, language.id, 'Ciclos E2E')
  const group = await createGroup(teacher, `Guías E2E ${Date.now()}`)
  await joinGroup(student, group.invite_code)
  await enableTopic(teacher, group.id, topic.id)

  const folder = await createGuideFolder(teacher, group.id, `Carpeta E2E ${Date.now()}`)
  const template = await createGuideTemplate(teacher, `Plantilla E2E ${Date.now()}`)
  const title = `Guía IA E2E ${Date.now()}`
  await insertDraftGuide(teacher.email, folder.id, template.id, topic.id, title)

  // Contextos separados (y no `browser.newPage()`): docente y estudiante
  // necesitan sesiones independientes, y `@axe-core/playwright` exige que la
  // página venga de un contexto explícito.
  const teacherContext = await browser.newContext()
  const studentContext = await browser.newContext()
  const teacherPage = await teacherContext.newPage()
  const studentPage = await studentContext.newPage()

  async function login(page: typeof teacherPage, user: typeof teacher, landing: string) {
    await page.goto('/login')
    await page.fill('#email', user.email)
    await page.fill('#password', user.password)
    await page.click('button[type=submit]')
    await page.waitForURL(landing)
  }

  // El estudiante aterriza en `/app`; el docente en `/app/docente`.
  await login(studentPage, student, '**/app')
  await studentPage.goto(`/app/grupos/${group.id}`)
  // Un borrador no existe para el estudiante.
  await expect(studentPage.getByText(title)).not.toBeVisible()

  await login(teacherPage, teacher, '**/app/docente')
  await teacherPage.goto(`/app/docente/grupos/${group.id}`)
  await teacherPage.getByRole('tab', { name: 'Guías' }).click()

  await expect(teacherPage.getByText(title)).toBeVisible()
  await expect(teacherPage.getByText('Borrador · IA')).toBeVisible()

  const a11yResults = await new AxeBuilder({ page: teacherPage })
    .withTags(['wcag2a', 'wcag2aa'])
    .analyze()
  expect(a11yResults.violations, JSON.stringify(a11yResults.violations, null, 2)).toEqual([])

  await teacherPage.getByRole('button', { name: new RegExp(title) }).click()
  // El docente puede verificar de qué material salió antes de publicar.
  await expect(teacherPage.getByText('Apuntes de clase E2E')).toBeVisible()
  await teacherPage.getByRole('button', { name: 'Publicar' }).click()

  await expect(teacherPage.getByText('Guía publicada')).toBeVisible()

  await studentPage.reload()
  await expect(studentPage.getByText(title)).toBeVisible()
  // El contenido se muestra renderizado, no como markdown en crudo.
  await studentPage.getByText(title).click()
  await expect(
    studentPage.getByRole('heading', { level: 2, name: 'Objetivos' }),
  ).toBeVisible()

  await teacherContext.close()
  await studentContext.close()
})
