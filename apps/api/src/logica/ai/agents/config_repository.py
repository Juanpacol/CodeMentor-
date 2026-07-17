import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from logica.ai.agents.models import AgentConfig, AgentName


async def get_agent_config(
    db: AsyncSession, group_id: uuid.UUID, agent_name: AgentName
) -> AgentConfig | None:
    stmt = select(AgentConfig).where(
        AgentConfig.group_id == group_id, AgentConfig.agent_name == agent_name
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_agent_configs_for_group(db: AsyncSession, group_id: uuid.UUID) -> list[AgentConfig]:
    stmt = select(AgentConfig).where(AgentConfig.group_id == group_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())
