import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from logica.modules.groups.models import Group, GroupMembership


async def get_group(db: AsyncSession, group_id: uuid.UUID) -> Group | None:
    return await db.get(Group, group_id)


async def get_group_by_invite_code(
    db: AsyncSession, institution_id: uuid.UUID, invite_code: str
) -> Group | None:
    stmt = select(Group).where(
        Group.institution_id == institution_id, Group.invite_code == invite_code
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_groups_for_teacher(
    db: AsyncSession, teacher_id: uuid.UUID, include_archived: bool = False
) -> list[Group]:
    stmt = select(Group).where(Group.teacher_id == teacher_id)
    if not include_archived:
        stmt = stmt.where(Group.archived_at.is_(None))
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_groups_for_student(db: AsyncSession, student_id: uuid.UUID) -> list[Group]:
    stmt = (
        select(Group)
        .join(GroupMembership, GroupMembership.group_id == Group.id)
        .where(GroupMembership.student_id == student_id, Group.archived_at.is_(None))
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_membership(
    db: AsyncSession, group_id: uuid.UUID, student_id: uuid.UUID
) -> GroupMembership | None:
    stmt = select(GroupMembership).where(
        GroupMembership.group_id == group_id, GroupMembership.student_id == student_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
