"""AI-specific observability (§9.4 "observabilidad dedicada... separado del
monitoreo general de la aplicación"): latency, error rate, cache hit rate and
volume per task/agent, exposed on the same `/metrics` Prometheus endpoint
that `prometheus-fastapi-instrumentator` sets up for general HTTP metrics in
main.py — a different registry section, not a different endpoint."""

from prometheus_client import Counter, Histogram

ai_requests_total = Counter(
    "ai_harness_requests_total",
    "Total de llamadas completadas por el harness de IA, por tarea y modelo",
    ["task", "model", "from_cache"],
)

ai_errors_total = Counter(
    "ai_harness_errors_total",
    "Errores del harness de IA por tarea y tipo de error",
    ["task", "error_type"],
)

ai_request_latency_seconds = Histogram(
    "ai_harness_request_latency_seconds",
    "Latencia de una llamada completa al harness de IA (incluye guardrails/caché/proveedor)",
    ["task"],
)

ai_tokens_total = Counter(
    "ai_harness_tokens_total",
    "Tokens consumidos por el harness de IA (prompt+completion), por tarea",
    ["task"],
)
