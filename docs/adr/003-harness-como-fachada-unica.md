# ADR-003: El harness es la única puerta de entrada a un LLM, y el RAG usa recuperación híbrida

## Estado

Aceptado — 2026-07-16.

## Contexto

§9.1 del documento de requerimientos exige que ninguna parte del sistema llame a un modelo de lenguaje directamente: enrutamiento con respaldo, plantillas versionadas, guardrails de entrada/salida, control de costos y trazabilidad deben aplicar a **toda** interacción con IA, no a una implementación distinta por agente. Al mismo tiempo, §9.4 pide minimizar datos personales y mantener una estrategia de proveedor flexible (terceros + modelo autoalojado según sensibilidad).

## Decisión 1: `ai.harness.complete_task()` es la única función que un skill o agente puede llamar para hablar con un LLM

`complete_task()` (en `ai/harness/harness.py`) compone, en orden estricto: render de plantilla → guardrail de entrada → verificación de presupuesto → búsqueda en caché → enrutador de modelos con respaldo (`ai/harness/router.py`) → guardrail de salida → escritura en caché → registro de uso → auditoría (`ai_interactions`) → traza en Langfuse. Ningún paso es opcional ni delegable al llamador.

La alternativa — dejar que cada agente de la Fase 6 arme su propia secuencia de guardrails/caché/auditoría — se descartó porque garantiza divergencia: un agente nuevo que olvide un paso (por ejemplo, el guardrail de salida en el Agente Tutor durante una evaluación, RF-31) sería un incidente de seguridad silencioso, no un error que las pruebas atraparían automáticamente. Con una única fachada, probar el harness una vez cubre a todos sus consumidores.

## Decisión 2: el enrutador usa una función de indirección a nivel de módulo (`_completion_fn`), no una clase inyectable

`ai/harness/router.py` no expone una clase `ModelRouter` con un cliente HTTP inyectado por constructor — expone una función `_completion_fn` a nivel de módulo que envuelve la única llamada a `litellm.acompletion`. Las pruebas la sustituyen con `monkeypatch` para simular fallas de proveedor y verificar el respaldo (Groq → Gemini → Ollama) sin gastar tokens reales ni depender de credenciales en CI. El mismo patrón se repite en `ai/rag/embedder.py` (`embed_texts`/`embed_query`) para evitar cargar el modelo de `sentence-transformers` en cada corrida de pruebas.

## Decisión 3: la recuperación del RAG combina vector + texto completo con Reciprocal Rank Fusion (RRF), no solo similitud de embeddings

`ai/rag/retriever.py` no ordena únicamente por distancia coseno del embedding. Un modelo de embeddings pequeño y multilingüe (`intfloat/multilingual-e5-small`, elegido por ser gratuito y autoalojado — §9.4) puede subponderar coincidencias exactas de palabras clave de PSeInt ("Mientras", "Repetir") frente a paráfrasis semánticas. Combinar ese ranking con una búsqueda de texto completo de Postgres (`to_tsvector('spanish', ...)`) mediante RRF (constante `k=60`, elección estándar, no calibrada por dataset) evita tener que calibrar cómo pesar una distancia coseno contra un `ts_rank` — dos métricas que viven en escalas no comparables — sin sacrificar la búsqueda semántica.

## Consecuencias

- Los agentes de la Fase 6 (Tutor, Generador de ejercicios, Asistente de calificación, Analítica de aprendizaje, Integridad de código) se implementan como consumidores delgados de `complete_task()` — su código específico es solo la plantilla de prompt y qué hacer con el texto de respuesta, nunca guardrails ni auditoría propios.
- Cambiar de proveedor de embeddings o agregar un cuarto modelo de respaldo es un cambio de una línea en `_MODEL_CHAINS`/`embedder.py`, no una migración de código en cada llamador.
- El costo de este diseño es una capa de indirección adicional en cada llamada; aceptable dado que ninguna ruta de esta plataforma es sensible a la latencia de microsegundos que esa indirección introduce.
