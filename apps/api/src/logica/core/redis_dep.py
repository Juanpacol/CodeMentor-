from fastapi import Request
from redis.asyncio import Redis


async def get_redis(request: Request) -> Redis:
    redis: Redis = request.app.state.redis
    return redis
