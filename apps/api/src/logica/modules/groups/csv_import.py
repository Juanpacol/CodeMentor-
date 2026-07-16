import csv
import io
from dataclasses import dataclass

REQUIRED_COLUMNS = {"email", "full_name"}


@dataclass(frozen=True)
class ParsedEnrollmentRow:
    email: str
    full_name: str
    student_code: str | None


@dataclass(frozen=True)
class RowError:
    row_number: int
    raw_row: str
    reason: str


def parse_csv_enrollment(content: bytes) -> tuple[list[ParsedEnrollmentRow], list[RowError]]:
    """Pure function (no DB access) so edge cases — corrupt rows, missing
    columns, duplicate emails — are cheap to unit test (§8.2)."""
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    headers = {h.strip().lower() for h in (reader.fieldnames or [])}
    if not REQUIRED_COLUMNS.issubset(headers):
        raise ValueError(
            "El CSV debe tener al menos las columnas: email, full_name "
            "(y opcionalmente student_code)"
        )
    fieldmap = {h.strip().lower(): h for h in (reader.fieldnames or [])}

    rows: list[ParsedEnrollmentRow] = []
    errors: list[RowError] = []
    seen_emails: set[str] = set()

    for row_number, raw in enumerate(reader, start=2):  # header occupies line 1
        raw_row_str = ",".join(f"{k}={v}" for k, v in raw.items())
        email = (raw.get(fieldmap["email"]) or "").strip().lower()
        full_name = (raw.get(fieldmap["full_name"]) or "").strip()
        student_code = None
        if "student_code" in fieldmap:
            student_code = (raw.get(fieldmap["student_code"]) or "").strip() or None

        if not email or "@" not in email:
            errors.append(
                RowError(
                    row_number=row_number, raw_row=raw_row_str, reason="correo vacío o inválido"
                )
            )
            continue
        if not full_name:
            errors.append(
                RowError(row_number=row_number, raw_row=raw_row_str, reason="nombre completo vacío")
            )
            continue
        if email in seen_emails:
            errors.append(
                RowError(
                    row_number=row_number,
                    raw_row=raw_row_str,
                    reason="correo duplicado dentro del archivo",
                )
            )
            continue

        seen_emails.add(email)
        rows.append(
            ParsedEnrollmentRow(email=email, full_name=full_name, student_code=student_code)
        )

    return rows, errors
