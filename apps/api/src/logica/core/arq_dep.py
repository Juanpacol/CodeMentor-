from arq import ArqRedis
from fastapi import Request


async def get_arq_pool(request: Request) -> ArqRedis:
    pool: ArqRedis = request.app.state.arq_pool
    return pool
