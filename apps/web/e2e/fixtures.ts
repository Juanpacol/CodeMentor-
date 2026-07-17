/** Helpers de datos de prueba para los E2E — llaman directamente a la API
 * real (no a través del frontend) porque crear un grupo, un tema y unos
 * ejercicios usando la UI en cada test sería lento y frágil; los 3 flujos
 * E2E solo ejercitan la UI en la parte que de verdad importa probar. */
const API_URL = 'http://localhost:8000'

async function api<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`${options.method ?? 'GET'} ${path} -> ${res.status}: ${body}`)
  }
  return res.json() as Promise<T>
}

export interface TestUser {
  email: string
  password: string
  accessToken: string
}

export async function registerAndLogin(
  role: 'student' | 'teacher',
  namePrefix: string,
): Promise<TestUser> {
  const unique = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  const email = `${namePrefix}-${unique}@inem.edu.co`
  const password = 'Sup3rSecreta!'

  await api('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password, full_name: `${namePrefix} E2E`, role }),
  })
  const tokens = await api<{ access_token: string }>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
  return { email, password, accessToken: tokens.access_token }
}

export async function createLanguage(teacher: TestUser, slugSuffix: string) {
  return api<{ id: string }>(
    '/languages',
    {
      method: 'POST',
      body: JSON.stringify({
        name: 'Python E2E',
        // Único incluso entre reintentos del mismo test dentro de la
        // misma corrida (por eso no basta con slugSuffix solo).
        slug: `python-e2e-${slugSuffix}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        syntax_mode: 'python',
      }),
    },
    teacher.accessToken,
  )
}

export async function createTopic(teacher: TestUser, languageId: string, name: string) {
  return api<{ id: string }>(
    '/topics',
    {
      method: 'POST',
      body: JSON.stringify({ language_id: languageId, name, level: 'basico', order_index: 1 }),
    },
    teacher.accessToken,
  )
}

export async function createGroup(teacher: TestUser, name: string) {
  return api<{ id: string; invite_code: string }>(
    '/groups',
    { method: 'POST', body: JSON.stringify({ name }) },
    teacher.accessToken,
  )
}

export async function enableTopic(teacher: TestUser, groupId: string, topicId: string) {
  await api(
    `/groups/${groupId}/topics/${topicId}/enable`,
    { method: 'POST' },
    teacher.accessToken,
  )
}

export async function createExercise(
  teacher: TestUser,
  languageId: string,
  title: string,
  type: string,
  content: Record<string, unknown>,
) {
  return api<{ id: string }>(
    '/exercises',
    { method: 'POST', body: JSON.stringify({ language_id: languageId, title, type, content }) },
    teacher.accessToken,
  )
}

export async function attachExercise(teacher: TestUser, exerciseId: string, topicId: string) {
  await api(
    `/exercises/${exerciseId}/topics/${topicId}`,
    { method: 'POST' },
    teacher.accessToken,
  )
}

export async function joinGroup(student: TestUser, inviteCode: string) {
  await api(
    '/groups/join',
    { method: 'POST', body: JSON.stringify({ invite_code: inviteCode }) },
    student.accessToken,
  )
}

/** `POST /exercises` siempre crea con `origin=teacher` — el único camino
 * público hacia un borrador `origin=ai` es `POST /ai/exercises/generate`,
 * que sin proveedores de IA configurados en este entorno local devuelve
 * 503 (ver el flujo 1, que prueba justo esa degradación). Para probar la
 * bandeja de aprobaciones de punta a punta sin depender de tokens reales,
 * este helper inserta la fila directamente en la base de datos de
 * desarrollo — el mismo atajo que ya se usó para la verificación manual
 * de la Fase 9 (commit 4). */
export async function insertAiDraftExercise(
  teacherEmail: string,
  languageId: string,
  title: string,
): Promise<string> {
  const { execFileSync } = await import('node:child_process')
  const script = `
import asyncio
from sqlalchemy import select
from logica.db import get_session_factory
from logica.modules.users.models import User
from logica.modules.content.models import Language, Topic, TopicGroupState  # noqa: F401 (registra FKs)
from logica.modules.groups.models import Group, GroupMembership  # noqa: F401 (registra FKs)
from logica.modules.exercises.models import Exercise, ExerciseType, ExerciseOrigin, ExerciseStatus

async def main():
    sf = get_session_factory()
    async with sf() as db:
        result = await db.execute(select(User).where(User.email == "${teacherEmail}"))
        teacher = result.scalar_one()
        ex = Exercise(
            institution_id=teacher.institution_id,
            language_id="${languageId}",
            created_by_id=teacher.id,
            title="${title}",
            type=ExerciseType.true_false,
            content={"statement": "Generado por IA (simulado para E2E)", "answer": True},
            origin=ExerciseOrigin.ai,
            status=ExerciseStatus.draft,
        )
        db.add(ex)
        await db.commit()
        print(ex.id)

asyncio.run(main())
`
  const output = execFileSync('uv', ['run', 'python', '-c', script], {
    cwd: new URL('../../api', import.meta.url).pathname,
    env: {
      ...process.env,
      DATABASE_URL: 'postgresql+asyncpg://logica:logica@localhost:5434/logica',
    },
    encoding: 'utf-8',
  })
  return output.trim().split('\n').pop()!
}
