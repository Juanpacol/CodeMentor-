import secrets
import string
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from logica.core.audit import record_audit
from logica.core.errors import ConflictError, NotFoundError, PermissionDeniedError
from logica.core.security import hash_password
from logica.modules.groups.csv_import import parse_csv_enrollment
from logica.modules.groups.models import Group, GroupMembership
from logica.modules.groups.repository import (
    get_group,
    get_group_by_invite_code,
    get_membership,
    list_groups_for_student,
    list_groups_for_teacher,
)
from logica.modules.groups.schemas import CreatedAccount, CsvEnrollResult, CsvEnrollRowError
from logica.modules.users.models import Role, User
from logica.modules.users.repository import get_user_by_email

_INVITE_ALPHABET = string.ascii_uppercase + string.digits


async def _generate_unique_invite_code(db: AsyncSession, institution_id: uuid.UUID) -> str:
    for _ in range(10):
        code = "".join(secrets.choice(_INVITE_ALPHABET) for _ in range(6))
        if await get_group_by_invite_code(db, institution_id, code) is None:
            return code
    raise RuntimeError("No se pudo generar un código de invitación único")


def _ensure_teacher(user: User) -> None:
    if user.role not in (Role.teacher, Role.admin):
        raise PermissionDeniedError("Solo un docente puede administrar grupos")


async def create_group(
    db: AsyncSession, teacher: User, name: str, grade_or_shift: str | None
) -> Group:
    _ensure_teacher(teacher)
    invite_code = await _generate_unique_invite_code(db, teacher.institution_id)
    group = Group(
        institution_id=teacher.institution_id,
        teacher_id=teacher.id,
        name=name,
        grade_or_shift=grade_or_shift,
        invite_code=invite_code,
    )
    db.add(group)
    await db.flush()
    await db.refresh(group)
    return group


async def _get_owned_group(db: AsyncSession, teacher: User, group_id: uuid.UUID) -> Group:
    group = await get_group(db, group_id)
    if group is None or group.institution_id != teacher.institution_id:
        raise NotFoundError("Grupo no encontrado")
    if teacher.role != Role.admin and group.teacher_id != teacher.id:
        raise PermissionDeniedError("No administras este grupo")
    return group


async def update_group(
    db: AsyncSession,
    teacher: User,
    group_id: uuid.UUID,
    name: str | None,
    grade_or_shift: str | None,
) -> Group:
    group = await _get_owned_group(db, teacher, group_id)
    if name:
        group.name = name
    if grade_or_shift is not None:
        group.grade_or_shift = grade_or_shift
    await db.flush()
    await db.refresh(group)
    return group


async def archive_group(db: AsyncSession, teacher: User, group_id: uuid.UUID) -> Group:
    group = await _get_owned_group(db, teacher, group_id)
    group.archived_at = datetime.now(UTC)
    await db.flush()
    await record_audit(
        db,
        institution_id=teacher.institution_id,
        actor_user_id=teacher.id,
        action="group_archived",
        target_type="group",
        target_id=str(group.id),
    )
    return group


async def get_group_with_access(
    db: AsyncSession, user: User, group_id: uuid.UUID
) -> tuple[Group, bool]:
    """Shared by content/evaluations: returns (group, is_teacher_view).
    Teachers must own the group (or be admin); students must be enrolled."""
    group = await get_group(db, group_id)
    if group is None or group.institution_id != user.institution_id:
        raise NotFoundError("Grupo no encontrado")

    if user.role in (Role.teacher, Role.admin):
        if user.role != Role.admin and group.teacher_id != user.id:
            raise PermissionDeniedError("No administras este grupo")
        return group, True

    membership = await get_membership(db, group_id, user.id)
    if membership is None:
        raise PermissionDeniedError("No perteneces a este grupo")
    return group, False


async def list_my_groups(db: AsyncSession, user: User) -> list[Group]:
    if user.role in (Role.teacher, Role.admin):
        return await list_groups_for_teacher(db, user.id)
    return await list_groups_for_student(db, user.id)


async def join_group_by_code(db: AsyncSession, student: User, invite_code: str) -> GroupMembership:
    if student.role != Role.student:
        raise PermissionDeniedError("Solo un estudiante puede unirse por código de invitación")

    group = await get_group_by_invite_code(db, student.institution_id, invite_code.upper())
    if group is None or group.archived_at is not None:
        raise NotFoundError("Código de invitación inválido")

    existing = await get_membership(db, group.id, student.id)
    if existing is not None:
        raise ConflictError("Ya perteneces a este grupo")

    membership = GroupMembership(group_id=group.id, student_id=student.id)
    db.add(membership)
    await db.flush()
    return membership


async def bulk_enroll_csv(
    db: AsyncSession, teacher: User, group_id: uuid.UUID, csv_content: bytes
) -> CsvEnrollResult:
    group = await _get_owned_group(db, teacher, group_id)

    try:
        parsed_rows, parse_errors = parse_csv_enrollment(csv_content)
    except ValueError as exc:
        raise ConflictError(str(exc)) from exc

    errors = [
        CsvEnrollRowError(row_number=e.row_number, raw_row=e.raw_row, reason=e.reason)
        for e in parse_errors
    ]
    created_accounts: list[CreatedAccount] = []
    enrolled = 0
    already_enrolled = 0

    for row in parsed_rows:
        user = await get_user_by_email(db, teacher.institution_id, row.email)
        if user is None:
            temp_password = secrets.token_urlsafe(9)
            user = User(
                institution_id=teacher.institution_id,
                email=row.email,
                student_code=row.student_code,
                full_name=row.full_name,
                hashed_password=hash_password(temp_password),
                role=Role.student,
            )
            db.add(user)
            await db.flush()
            created_accounts.append(
                CreatedAccount(email=row.email, temporary_password=temp_password)
            )

        existing_membership = await get_membership(db, group.id, user.id)
        if existing_membership is not None:
            already_enrolled += 1
            continue

        db.add(GroupMembership(group_id=group.id, student_id=user.id))
        enrolled += 1

    await db.flush()
    await record_audit(
        db,
        institution_id=teacher.institution_id,
        actor_user_id=teacher.id,
        action="bulk_enroll_csv",
        target_type="group",
        target_id=str(group.id),
        details={"enrolled": enrolled, "errors": len(errors)},
    )

    return CsvEnrollResult(
        enrolled=enrolled,
        already_enrolled=already_enrolled,
        created_accounts=created_accounts,
        errors=errors,
    )
