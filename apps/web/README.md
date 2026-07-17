# Lógica>_ — Frontend

SPA en React + TypeScript + Vite para la plataforma "Lógica>_". Modo nocturno único
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
- `npm run e2e` — Playwright (requiere el stack Docker completo, `make up`)
- `npm run build` — build de producción
