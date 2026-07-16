import uuid

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from logica.core.security import get_current_user
from logica.db import get_db
from logica.modules.groups import service
from logica.modules.groups.models import Group
from logica.modules.groups.schemas import (
    CsvEnrollResult,
    GroupCreateRequest,
    GroupOut,
    GroupUpdateRequest,
    JoinGroupRequest,
)
from logica.modules.users.models import User

router = APIRouter(prefix="/groups", tags=["groups"])


@router.post("", response_model=GroupOut, status_code=201)
async def create_group(
    payload: GroupCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Group:
    group = await service.create_group(db, user, payload.name, payload.grade_or_shift)
    await db.commit()
    return group


@router.get("/mine", response_model=list[GroupOut])
async def list_my_groups(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[Group]:
    return await service.list_my_groups(db, user)


@router.patch("/{group_id}", response_model=GroupOut)
async def update_group(
    group_id: uuid.UUID,
    payload: GroupUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Group:
    group = await service.update_group(db, user, group_id, payload.name, payload.grade_or_shift)
    await db.commit()
    return group


@router.post("/{group_id}/archive", response_model=GroupOut)
async def archive_group(
    group_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Group:
    group = await service.archive_group(db, user, group_id)
    await db.commit()
    return group


@router.post("/join", status_code=201)
async def join_group(
    payload: JoinGroupRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    await service.join_group_by_code(db, user, payload.invite_code)
    await db.commit()
    return {"detail": "Te uniste al grupo correctamente"}


@router.post("/{group_id}/enroll-csv", response_model=CsvEnrollResult)
async def enroll_csv(
    group_id: uuid.UUID,
    file: UploadFile,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CsvEnrollResult:
    content = await file.read()
    result = await service.bulk_enroll_csv(db, user, group_id, content)
    await db.commit()
    return result
