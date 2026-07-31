"""Límites de tasa (RE-08 hardening) sobre endpoints sensibles de auth.

Solo se activan con ENV=prod (igual que HSTS en `security_headers.py`) —
en dev/test, decenas de tests y flujos de desarrollo golpean /auth/login
repetidamente y un límite real produciría 429 falsos sin relación con lo
que se está probando. El storage es el mismo Redis que ya usa el resto
de la app, así que el conteo es compartido entre réplicas si el despliegue
llega a escalar horizontalmente.

`user_limiter` es una segunda instancia, para endpoints ya autenticados
(ej. llamadas a IA) donde limitar por IP penalizaría a toda una red/aula
compartida en vez de al usuario que realmente abusa. `_user_or_ip_key`
decodifica el JWT directamente (sin pasar por `get_current_user`, que es
un `Depends` y `key_func` de slowapi solo recibe el `Request`) y cae a IP
si no hay token válido — así endpoints públicos o llamadas sin auth no
rompen.
"""

import jwt
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from logica.config import get_settings

_settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_settings.redis_url,
    enabled=_settings.env == "prod",
)


def _user_or_ip_key(request: Request) -> str:
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[len("bearer ") :]
        try:
            raw = jwt.decode(token, _settings.jwt_secret, algorithms=[_settings.jwt_algorithm])
            return f"user:{raw['sub']}"
        except jwt.InvalidTokenError:
            pass
    return get_remote_address(request)


user_limiter = Limiter(
    key_func=_user_or_ip_key,
    storage_uri=_settings.redis_url,
    enabled=_settings.env == "prod",
)
