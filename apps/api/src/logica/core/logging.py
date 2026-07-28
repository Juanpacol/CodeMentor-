import logging

import structlog


def configure_logging(*, log_level: str) -> None:
    """Logs en JSON (item 3, manejo de errores & logging): sin esto
    `structlog.get_logger()` (usado en ~14 módulos) cae a su renderer de
    consola por defecto, no estructurado. `merge_contextvars` es la pieza que
    hace que el `request_id` bindeado por `RequestIdMiddleware` aparezca en
    cada línea de log de la request sin tocar esos ~14 call-sites.
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping()[log_level.upper()]
        ),
        cache_logger_on_first_use=True,
    )
