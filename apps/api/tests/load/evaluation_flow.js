// k6 sobre el flujo de evaluación cronometrada: login → take (start_or_get_attempt)
// → N submit_answer → submit (finalize_attempt) → poll de ranking.
//
// Objetivo (ítem 17 del plan de mejoras): exponer dos hotspots ya identificados
// por lectura de código, no hipotéticos:
//   1. `start_or_get_attempt` (evaluations/service.py) hace un N+1 — un
//      `get_exercise()` por cada pregunta de la evaluación en vez de una sola
//      query con IN — así que `take_evaluation_duration` debe crecer
//      ~linealmente con NUM_QUESTIONS.
//   2. `get_ranking` hace `zrevrange(0, -1)` sin paginación sobre una clave
//      `ranking:{evaluation_id}` sin TTL — así que `ranking_duration` debe
//      crecer con el número de estudiantes que ya finalizaron, no quedarse
//      constante.
//
// Requiere `make seed` corrido contra el target (usa la institución/docente
// demo de `inem.edu.co`) y la API arriba (`make up`). Local-only, como los e2e
// de Playwright — no corre en CI.
//
// Uso:
//   make load
//   make load VUS=50 QUESTIONS=25 DURATION=30s   # escala para forzar el N+1/zrevrange
import http from 'k6/http'
import { check, sleep } from 'k6'
import { Trend } from 'k6/metrics'

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000'
const NUM_QUESTIONS = parseInt(__ENV.QUESTIONS || '15', 10)
const RUN_ID = Date.now()

const TEACHER_EMAIL = 'docente.logica@inem.edu.co'
const TEACHER_PASSWORD = 'Logica2026!'
const STUDENT_DOMAIN = 'inem.edu.co'
const STUDENT_PASSWORD = 'CargaK6_2026!'

export const options = {
  scenarios: {
    evaluacion_cronometrada: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: __ENV.RAMP_DURATION || '10s', target: parseInt(__ENV.VUS || '20', 10) },
        { duration: __ENV.DURATION || '20s', target: parseInt(__ENV.VUS || '20', 10) },
        { duration: '5s', target: 0 },
      ],
    },
  },
  thresholds: {
    // Umbrales generosos a propósito: el punto de esta corrida es medir y
    // mostrar la forma de la curva (¿crece con N?), no imponer un SLA todavía
    // — eso viene después de tener una primera medición real, igual que
    // Lighthouse (ítem 13) no se fijó con un presupuesto aspiracional.
    http_req_failed: ['rate<0.05'],
    take_evaluation_duration: ['p(95)<5000'],
    ranking_duration: ['p(95)<5000'],
  },
}

const takeEvaluationDuration = new Trend('take_evaluation_duration')
const rankingDuration = new Trend('ranking_duration')

function authHeaders(token) {
  return { headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' } }
}

export function setup() {
  const login = http.post(
    `${BASE_URL}/auth/login`,
    JSON.stringify({ email: TEACHER_EMAIL, password: TEACHER_PASSWORD }),
    { headers: { 'Content-Type': 'application/json' } },
  )
  check(login, { 'login docente ok': (r) => r.status === 200 })
  const teacherToken = login.json('access_token')

  const languages = http.get(`${BASE_URL}/languages`, authHeaders(teacherToken))
  const languageId = languages.json()[0].id

  const group = http.post(
    `${BASE_URL}/groups`,
    JSON.stringify({ name: `Carga k6 ${RUN_ID}`, grade_or_shift: 'k6' }),
    authHeaders(teacherToken),
  )
  check(group, { 'crear grupo ok': (r) => r.status === 201 })
  const groupId = group.json('id')
  const inviteCode = group.json('invite_code')

  // Una evaluación `fixed` exige que cada ejercicio pertenezca a un tema
  // habilitado para el grupo (evaluations/service.py::_eligible_topic_ids) —
  // se crea un tema dedicado a esta corrida, se habilita para el grupo de
  // carga, y cada ejercicio se asocia a él antes de armar la evaluación.
  const topic = http.post(
    `${BASE_URL}/topics`,
    JSON.stringify({ language_id: languageId, name: `Tema de carga k6 ${RUN_ID}`, level: 'basico' }),
    authHeaders(teacherToken),
  )
  check(topic, { 'crear tema ok': (r) => r.status === 201 })
  const topicId = topic.json('id')

  const enableTopic = http.post(
    `${BASE_URL}/groups/${groupId}/topics/${topicId}/enable`,
    null,
    authHeaders(teacherToken),
  )
  check(enableTopic, { 'habilitar tema ok': (r) => r.status === 200 })

  const answerByExerciseId = {}
  const exerciseIds = []
  for (let i = 0; i < NUM_QUESTIONS; i++) {
    const expected = i % 2 === 0
    const exercise = http.post(
      `${BASE_URL}/exercises`,
      JSON.stringify({
        language_id: languageId,
        title: `k6 pregunta ${i}`,
        type: 'true_false',
        content: { statement: `Enunciado de carga ${i}`, answer: expected },
      }),
      authHeaders(teacherToken),
    )
    check(exercise, { 'crear ejercicio ok': (r) => r.status === 201 })
    const exerciseId = exercise.json('id')

    const attach = http.post(
      `${BASE_URL}/exercises/${exerciseId}/topics/${topicId}`,
      null,
      authHeaders(teacherToken),
    )
    check(attach, { 'asociar ejercicio a tema ok': (r) => r.status === 201 })

    exerciseIds.push(exerciseId)
    answerByExerciseId[exerciseId] = expected
  }

  const evaluation = http.post(
    `${BASE_URL}/evaluations`,
    JSON.stringify({
      group_id: groupId,
      title: `Evaluación de carga k6 ${RUN_ID}`,
      mode: 'cumulative',
      is_ranked: true,
      exercise_ids: exerciseIds,
    }),
    authHeaders(teacherToken),
  )
  check(evaluation, { 'crear evaluación ok': (r) => r.status === 201 })

  return {
    evaluationId: evaluation.json('id'),
    inviteCode,
    answerByExerciseId,
  }
}

export default function (data) {
  const email = `k6.${RUN_ID}.${__VU}.${__ITER}@${STUDENT_DOMAIN}`
  const register = http.post(
    `${BASE_URL}/auth/register`,
    JSON.stringify({
      email,
      password: STUDENT_PASSWORD,
      full_name: `Estudiante k6 ${__VU}-${__ITER}`,
      role: 'student',
    }),
    { headers: { 'Content-Type': 'application/json' } },
  )
  check(register, { 'registro estudiante ok': (r) => r.status === 201 })

  const login = http.post(
    `${BASE_URL}/auth/login`,
    JSON.stringify({ email, password: STUDENT_PASSWORD }),
    { headers: { 'Content-Type': 'application/json' } },
  )
  const token = login.json('access_token')
  const headers = authHeaders(token)

  const join = http.post(
    `${BASE_URL}/groups/join`,
    JSON.stringify({ invite_code: data.inviteCode }),
    headers,
  )
  check(join, { 'unirse al grupo ok': (r) => r.status === 201 })

  // start_or_get_attempt — el N+1 vive aquí: esta llamada hace 1 query por
  // pregunta de la evaluación.
  const take = http.get(`${BASE_URL}/evaluations/${data.evaluationId}/take`, headers)
  check(take, { 'take evaluación ok': (r) => r.status === 200 })
  takeEvaluationDuration.add(take.timings.duration)

  for (const ex of take.json('exercises')) {
    const answer = data.answerByExerciseId[ex.exercise_id]
    http.post(
      `${BASE_URL}/evaluations/${data.evaluationId}/answers`,
      JSON.stringify({ evaluation_exercise_id: ex.evaluation_exercise_id, answer: { value: answer } }),
      headers,
    )
  }

  const submit = http.post(`${BASE_URL}/evaluations/${data.evaluationId}/submit`, null, headers)
  check(submit, { 'submit evaluación ok': (r) => r.status === 200 })

  // get_ranking — el zrevrange(0, -1) vive aquí: sin paginación, esta llamada
  // trae una fila por cada estudiante que ya finalizó, en cada poll.
  for (let i = 0; i < 3; i++) {
    const ranking = http.get(`${BASE_URL}/evaluations/${data.evaluationId}/ranking`, headers)
    check(ranking, { 'ranking ok': (r) => r.status === 200 })
    rankingDuration.add(ranking.timings.duration)
    sleep(1)
  }
}
