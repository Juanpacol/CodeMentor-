import pytest

from logica.modules.groups.csv_import import parse_csv_enrollment


def test_parses_valid_rows() -> None:
    content = b"email,full_name,student_code\na@example.com,Ana,S1\nb@example.com,Beto,S2\n"
    rows, errors = parse_csv_enrollment(content)
    assert errors == []
    assert len(rows) == 2
    assert rows[0].email == "a@example.com"
    assert rows[0].student_code == "S1"


def test_missing_required_columns_raises() -> None:
    content = b"correo,nombre\nx@example.com,Alguien\n"
    with pytest.raises(ValueError):
        parse_csv_enrollment(content)


def test_empty_email_row_becomes_error() -> None:
    content = b"email,full_name\n,Sin Correo\n"
    rows, errors = parse_csv_enrollment(content)
    assert rows == []
    assert len(errors) == 1
    assert "correo" in errors[0].reason
    assert errors[0].row_number == 2


def test_email_without_at_sign_becomes_error() -> None:
    content = b"email,full_name\nno-es-un-correo,Alguien\n"
    _, errors = parse_csv_enrollment(content)
    assert len(errors) == 1


def test_empty_full_name_becomes_error() -> None:
    content = b"email,full_name\na@example.com,\n"
    rows, errors = parse_csv_enrollment(content)
    assert rows == []
    assert len(errors) == 1
    assert "nombre" in errors[0].reason


def test_duplicate_email_in_file_becomes_error() -> None:
    content = b"email,full_name\na@example.com,Ana\na@example.com,Ana Otra Vez\n"
    rows, errors = parse_csv_enrollment(content)
    assert len(rows) == 1
    assert len(errors) == 1
    assert "duplicado" in errors[0].reason


def test_student_code_column_is_optional() -> None:
    content = b"email,full_name\na@example.com,Ana\n"
    rows, errors = parse_csv_enrollment(content)
    assert errors == []
    assert rows[0].student_code is None


def test_row_with_extra_whitespace_is_normalized() -> None:
    content = b"email,full_name\n  A@Example.com  ,  Ana  \n"
    rows, errors = parse_csv_enrollment(content)
    assert errors == []
    assert rows[0].email == "a@example.com"
    assert rows[0].full_name == "Ana"
