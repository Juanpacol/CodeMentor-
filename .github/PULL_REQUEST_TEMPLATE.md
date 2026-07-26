## Qué cambia y por qué

<!-- El diff ya muestra el qué. Explica el porqué: qué problema resuelve o qué motivó el cambio. -->

## Cómo se probó

- [ ] `make lint && make typecheck && make test` (si tocaste `apps/api`)
- [ ] `cd apps/web && npm run lint && npx tsc -b && npm run test -- --run` (si tocaste `apps/web`)
- [ ] Si agregaste/modificaste una migración: probé `upgrade head` y `downgrade -1` localmente
- [ ] Probado manualmente en el navegador/API (describe el caso si aplica)

## Checklist

- [ ] La PR tiene un solo propósito (si encontraste algo no relacionado, lo separé)
- [ ] Agregué/actualicé tests para el comportamiento nuevo
- [ ] Actualicé `CLAUDE.md`/`docs/` si este cambio afecta convenciones o arquitectura documentada
