"""Verificación de Google Sign-In (OIDC) sin `authlib`: el frontend obtiene un
`id_token` con Google Identity Services (One Tap / botón), y acá solo se
verifica su firma contra las claves públicas de Google — no hay redirect ni
intercambio de código en el backend.
"""

from dataclasses import dataclass

import jwt

from logica.config import get_settings
from logica.core.errors import ValidationDomainError

_GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
_GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")

# `PyJWKClient` cachea las claves en memoria y las refresca cuando aparece un
# `kid` desconocido, así que no hace falta manejar TTL a mano.
_jwks_client = jwt.PyJWKClient(_GOOGLE_JWKS_URL)


@dataclass
class GoogleClaims:
    email: str
    email_verified: bool
    full_name: str


def verify_google_id_token(id_token: str) -> GoogleClaims:
    settings = get_settings()
    if not settings.google_client_id:
        raise ValidationDomainError("Login con Google no está configurado")

    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.google_client_id,
            issuer=_GOOGLE_ISSUERS,
        )
    except jwt.InvalidTokenError as exc:
        raise ValidationDomainError("Token de Google inválido") from exc

    if not claims.get("email_verified"):
        raise ValidationDomainError("El correo de Google no está verificado")

    return GoogleClaims(
        email=claims["email"],
        email_verified=bool(claims["email_verified"]),
        full_name=claims.get("name", claims["email"]),
    )
