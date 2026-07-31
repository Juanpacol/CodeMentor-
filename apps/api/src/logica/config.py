from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"

    database_url: str = Field(default="postgresql+asyncpg://logica:logica@localhost:5432/logica")
    redis_url: str = Field(default="redis://localhost:6379/0")

    jwt_secret: str = Field(default="change-me-in-env")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14

    institution_email_domains: list[str] = Field(default_factory=lambda: ["inem.edu.co"])

    google_client_id: str | None = None

    groq_api_key: str | None = None
    gemini_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"

    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "http://localhost:3000"

    sandbox_url: str = "http://localhost:2000"

    # RF-16/RE-03: exported reports are written here by the arq worker and
    # streamed back by the API — a shared Docker volume in compose, a plain
    # local folder otherwise. No S3/object storage needed to stay 100% free.
    reports_dir: str = "./reports"

    ai_daily_token_budget_per_student: int = 20_000
    # Fase 16: un docente consume en una sola acción lo que un estudiante en un
    # día — generar una guía son N llamadas (una por sección) con contexto RAG
    # en cada una. Con el tope de estudiante, la primera guía se rechazaría por
    # presupuesto. Sigue siendo un tope: acota un bucle descontrolado o un cron
    # mal configurado, no el uso normal.
    ai_daily_token_budget_per_teacher: int = 200_000
    # Ítem 14: umbral mensual de costo ESTIMADO (no facturación real) para el
    # nivel de alerta ok/warning/critical del dashboard de costo — ver
    # ai/repository.py::budget_status_for_institution. En los free tiers de
    # Groq/Gemini el gasto real es $0; este número sirve para atribución
    # relativa entre agentes, no para un corte duro.
    ai_monthly_cost_limit_usd: float = 5.0

    # Fase 17: adquisición de material de referencia para las rúbricas. Ninguna
    # de estas requiere API key — la fuente es la action API de Wikimedia, que es
    # abierta. `content_acquisition_enabled=False` deja el pipeline de rúbricas
    # funcionando sin red: las guías se generan igual, solo que fundamentadas en
    # el material que ya haya subido el docente.
    content_acquisition_enabled: bool = True
    content_acquisition_timeout_seconds: float = 10.0
    content_acquisition_max_sources_per_topic: int = 3

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    # Despliegue gratuito (Fase 10): el free tier de Render solo incluye web
    # services, no background workers (esos son de pago) — en producción el
    # worker de arq corre como una tarea asyncio dentro del mismo proceso de
    # uvicorn en vez de como contenedor separado (ver workers/inprocess.py).
    # En Docker Compose local el worker sigue siendo su propio contenedor
    # (Dockerfile.worker), así que esto se queda en False salvo que se active
    # explícitamente en el entorno de producción.
    run_worker_in_process: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
