"""Límites de tasa (RE-08 hardening) sobre endpoints sensibles de auth.

Solo se activan con ENV=prod (igual que HSTS en `security_headers.py`) —
en dev/test, decenas de tests y flujos de desarrollo golpean /auth/login
repetidamente y un límite real produciría 429 falsos sin relación con lo
que se está probando. El storage es el mismo Redis que ya usa el resto
de la app, así que el conteo es compartido entre réplicas si el despliegue
llega a escalar horizontalmente.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from logica.config import get_settings

_settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_settings.redis_url,
    enabled=_settings.env == "prod",
)
