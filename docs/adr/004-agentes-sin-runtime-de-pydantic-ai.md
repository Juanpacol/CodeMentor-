# ADR-004: Los 5 agentes de la Fase 6 no usan el runtime `Agent`/`Model` de Pydantic AI

## Estado

Aceptado — 2026-07-17.

## Contexto

El plan original de arquitectura listaba **Pydantic AI** como el framework de agentes ("Agentes tipados, testeables con `TestModel` sin gastar tokens, tools = skills"), y la dependencia `pydantic-ai-slim` se instaló desde la Fase 0. Al llegar a la Fase 6 e implementar los 5 agentes de §9.2 (Tutor, Generador de ejercicios, Asistente de calificación, Analítica de aprendizaje, Integridad de código), surgió un conflicto real con una decisión ya tomada y documentada en el [ADR-003](003-harness-como-fachada-unica.md): **ninguna parte del sistema puede llamar a un LLM fuera de `ai.harness.complete_task()`**, que ya centraliza guardrails de entrada/salida, presupuesto diario, caché y auditoría (RF-34).

`pydantic_ai.Agent` hace su propia llamada al modelo internamente a través de sus propias clases `Model` (una por proveedor). Usarlo tal cual habría significado que los agentes llamaran a Groq/Gemini/Ollama **por fuera** del harness, perdiendo guardrails, presupuesto, caché y auditoría exactamente para los 5 componentes de IA más sensibles del proyecto (los que generan contenido para menores de edad o sugieren calificaciones).

## Decisión

Se investigó la alternativa de escribir una subclase de `pydantic_ai.models.Model` que delegara internamente en `complete_task()`. Es técnicamente viable (una clase de ~100-150 líneas), pero no elimina el problema de fondo: `complete_task()` necesita saber explícitamente qué fragmento del prompt es texto no confiable del estudiante (`untrusted_input`, para el guardrail de inyección de prompt) y qué plantilla versionada usar — información que Pydantic AI no expone de forma reconciliable con nuestro sistema de plantillas Jinja2 sin la misma contabilidad manual que ya requeriría escribir cada agente como función simple.

Dado que **ninguno de los 5 agentes necesita un loop agéntico multi-paso con herramientas** — cada uno hace una única transformación texto/contexto → salida (texto libre o JSON estructurado) — se optó por: cada agente es una función `async` simple que arma sus variables de plantilla, llama a `complete_task()` (Tutor, Analítica) o al nuevo helper `ai.harness.structured.complete_structured()` (Generador de ejercicios, Asistente de calificación, Integridad de código), y este último parsea el JSON de respuesta hacia un `pydantic.BaseModel` de salida con reintento automático (hasta 2 veces) si la validación falla.

La dependencia `pydantic-ai-slim` se removió de `pyproject.toml` por no tener uso real en el código — mantenerla habría sido cargar ~15 paquetes transitivos (incluyendo SDKs de Groq/Google/OpenAI redundantes con LiteLLM) sin ningún beneficio.

## Consecuencias

- Las "salidas estructuradas tipadas" que Pydantic AI habría dado gratis se logran igual, con un helper propio (~90 líneas) que reutiliza `pydantic.BaseModel`/`ValidationError` — la pieza de valor real de Pydantic AI para este proyecto, sin el runtime de invocación de modelo que habría duplicado al harness.
- `TestModel`/`FunctionModel` de Pydantic AI ya no aplican; en su lugar, los tests de los 5 agentes usan el mismo patrón de la Fase 5 (`monkeypatch` sobre `logica.ai.harness.harness.router_complete`), consistente en todo el proyecto.
- Si en el futuro un agente necesitara de verdad un loop multi-paso con *tool calling* nativo (por ejemplo, un agente que decida dinámicamente qué skills invocar), esa sería la señal correcta para reconsiderar este ADR y evaluar de nuevo un adaptador `Model` — hoy esa necesidad no existe.
