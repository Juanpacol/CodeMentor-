import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from logica.ai.agents.config_repository import get_agent_config, list_agent_configs_for_group
from logica.ai.agents.models import AgentConfig, AgentName
from logica.core.errors import PermissionDeniedError
from logica.modules.groups.service import get_group_with_access
from logica.modules.users.models import Role, User


class AgentDisabledError(PermissionDeniedError):
    pass


async def is_agent_enabled(db: AsyncSession, group_id: uuid.UUID, agent_name: AgentName) -> bool:
    """Absence of a row means enabled — see AgentConfig docstring."""
    config = await get_agent_config(db, group_id, agent_name)
    return config is None or config.enabled


async def ensure_agent_enabled(
    db: AsyncSession, group_id: uuid.UUID, agent_name: AgentName
) -> None:
    if not await is_agent_enabled(db, group_id, agent_name):
        raise AgentDisabledError(
            f"El agente '{agent_name.name}' está desactivado para este grupo. "
            "El docente puede seguir haciendo esta tarea manualmente."
        )


async def list_agent_status(
    db: AsyncSession, user: User, group_id: uuid.UUID
) -> dict[AgentName, bool]:
    await get_group_with_access(db, user, group_id)  # raises if no access at all
    configs = {c.agent_name: c for c in await list_agent_configs_for_group(db, group_id)}
    return {name: (configs[name].enabled if name in configs else True) for name in AgentName}


async def set_agent_enabled(
    db: AsyncSession, teacher: User, group_id: uuid.UUID, agent_name: AgentName, enabled: bool
) -> AgentConfig:
    if teacher.role not in (Role.teacher, Role.admin):
        raise PermissionDeniedError(
            "Solo un docente o administrador puede activar/desactivar agentes"
        )
    await get_group_with_access(db, teacher, group_id)

    config = await get_agent_config(db, group_id, agent_name)
    if config is None:
        config = AgentConfig(group_id=group_id, agent_name=agent_name, enabled=enabled)
        db.add(config)
    else:
        config.enabled = enabled

    await db.flush()
    await db.refresh(config)
    return config
