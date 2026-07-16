import uuid

import pytest
from fastapi import HTTPException

from logica.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("Sup3rSecreta!")
    assert hashed != "Sup3rSecreta!"
    assert verify_password("Sup3rSecreta!", hashed) is True


def test_password_hash_rejects_wrong_password() -> None:
    hashed = hash_password("Sup3rSecreta!")
    assert verify_password("OtraClave!", hashed) is False


def test_access_token_roundtrip() -> None:
    user_id = uuid.uuid4()
    institution_id = uuid.uuid4()
    token = create_access_token(user_id=user_id, institution_id=institution_id, role="teacher")

    payload = decode_token(token, expected_type="access")
    assert payload.sub == user_id
    assert payload.institution_id == institution_id
    assert payload.role == "teacher"
    assert payload.token_type == "access"


def test_refresh_token_rejected_as_access_token() -> None:
    token = create_refresh_token(user_id=uuid.uuid4(), institution_id=uuid.uuid4(), role="student")
    with pytest.raises(HTTPException) as exc_info:
        decode_token(token, expected_type="access")
    assert exc_info.value.status_code == 401


def test_garbage_token_rejected() -> None:
    with pytest.raises(HTTPException) as exc_info:
        decode_token("no-es-un-jwt-valido", expected_type="access")
    assert exc_info.value.status_code == 401
