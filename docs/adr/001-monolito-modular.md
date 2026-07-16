# ADR-001: Monolito modular en lugar de microservicios desde el inicio

## Estado

Aceptado — 2026-07-16.

## Contexto

El documento de requerimientos pide una arquitectura que escale (RE-01..RE-07) sin sobre-diseñar para una carga que hoy es de un colegio (35-40 estudiantes concurrentes). El proyecto también debe ser mantenible por un equipo pequeño o incluso una sola persona (§8.4).

## Decisión

Construir un **monolito modular stateless**: un único servicio FastAPI desplegable, organizado en módulos de dominio con fronteras internas estrictas (`router → service → repository`, sin imports cruzados entre módulos salvo a través de interfaces explícitas). El sandbox de ejecución de código y el servidor MCP sí son procesos separados desde el día 1, porque su aislamiento es un requisito de seguridad (§4.2), no una optimización prematura.

## Alternativas consideradas

- **Microservicios por dominio desde el inicio**: descartado. Añade complejidad operativa (orquestación, descubrimiento de servicios, transacciones distribuidas) que no se justifica en esta escala y that ralentiza la entrega del piloto (Fase 1 de la hoja de ruta, §7).
- **Monolito no modular ("big ball of mud")**: descartado. No cumpliría RE-05 (plugins de ejercicio) ni permitiría dividir el trabajo entre desarrolladores (§3.3).

## Consecuencias

- Añadir una sede o institución (RE-04) es un cambio de datos (`institution_id`), no de arquitectura.
- Escalar a más carga (RE-01) es añadir réplicas del mismo contenedor `api` detrás de un balanceador — no requiere repartir código entre servicios.
- Si en el futuro un módulo (p. ej. `grading` o el `sandbox`) necesita escalar independientemente, sus fronteras internas ya limpias facilitan extraerlo sin reescritura.
