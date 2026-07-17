# CodeMentor — Frontend

SPA en React + TypeScript + Vite para la plataforma "CodeMentor". Modo nocturno único
(estética Notion night), Tailwind v4, TanStack Query, `motion` para animaciones.

## Desarrollo

```bash
npm install --legacy-peer-deps
npm run dev
```

Requiere la API corriendo en `http://localhost:8000` (ver `docker-compose.yml` en la raíz
del repo, `make up`). El origen `http://localhost:5173` ya está permitido en CORS.

## Regenerar el cliente TypeScript de la API

Con la API corriendo:

```bash
../../scripts/gen_openapi_client.sh
```

Regenera `src/lib/api/schema.d.ts` a partir de `/openapi.json` — se commitea, así que el
build de este proyecto no depende de tener la API levantada.

## Scripts

- `npm run dev` — servidor de desarrollo (puerto 5173)
- `npm run lint` — oxlint
- `npx tsc -b` — chequeo de tipos
- `npm run test` — vitest (componentes/hooks)
- `npm run e2e` — Playwright, 3 flujos E2E contra el stack Docker real (ver abajo)
- `npm run build` — build de producción

## Tests E2E (Playwright)

Los 3 flujos en `e2e/*.spec.ts` corren contra el stack completo real, nunca mockeado:
estudiante practica y pide una pista de IA (verificando la degradación a 503 sin API
keys configuradas), docente crea una evaluación con alcance, docente aprueba un
ejercicio generado por IA desde la bandeja de aprobaciones.

Requiere:

```bash
make up              # postgres+redis+api+worker (desde la raíz del repo)
npx playwright install chromium   # una sola vez
npm run e2e
```

`e2e/fixtures.ts` crea todos los datos de prueba (docentes, estudiantes, grupos,
ejercicios) llamando directamente a la API real — nunca a través de la UI, para que
los tests sean rápidos y no dependan de flujos que ya prueban otros specs. El flujo de
aprobación de IA inserta un ejercicio `origin=ai, status=draft` directamente en la base
de datos de desarrollo (`insertAiDraftExercise`), ya que forzar una generación real
exitosa requeriría API keys de un proveedor LLM — innecesario para probar la UI de
aprobación en sí.

Playwright **no corre en CI** (requeriría levantar todo el stack Docker en Actions) —
es local-only por ahora; se reevaluará en la Fase 10 junto con el deploy.
