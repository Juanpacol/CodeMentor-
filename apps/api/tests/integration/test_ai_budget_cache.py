import uuid

import pytest
from redis.asyncio import Redis

from logica.ai.harness import budget, cache
from logica.config import get_settings
from logica.core.errors import ConflictError


class TestBudget:
    async def test_starts_at_zero(self, redis_client: Redis) -> None:
        student_id = str(uuid.uuid4())
        assert await budget.get_tokens_used_today(redis_client, student_id) == 0

    async def test_record_usage_accumulates(self, redis_client: Redis) -> None:
        student_id = str(uuid.uuid4())
        await budget.record_usage(redis_client, student_id, 100)
        await budget.record_usage(redis_client, student_id, 50)
        assert await budget.get_tokens_used_today(redis_client, student_id) == 150

    async def test_check_budget_passes_under_limit(self, redis_client: Redis) -> None:
        student_id = str(uuid.uuid4())
        await budget.record_usage(redis_client, student_id, 10)
        await budget.check_budget(redis_client, student_id)  # no raise

    async def test_check_budget_raises_at_limit(self, redis_client: Redis) -> None:
        student_id = str(uuid.uuid4())
        limit = get_settings().ai_daily_token_budget_per_student
        await budget.record_usage(redis_client, student_id, limit)
        with pytest.raises(ConflictError):
            await budget.check_budget(redis_client, student_id)

    async def test_different_students_have_independent_budgets(self, redis_client: Redis) -> None:
        student_a = str(uuid.uuid4())
        student_b = str(uuid.uuid4())
        limit = get_settings().ai_daily_token_budget_per_student
        await budget.record_usage(redis_client, student_a, limit)
        await budget.check_budget(redis_client, student_b)  # unaffected, no raise


class TestCache:
    async def test_miss_returns_none(self, redis_client: Redis) -> None:
        assert (
            await cache.get_cached_response(redis_client, "progressive_hint", "algún prompt")
            is None
        )

    async def test_hit_returns_stored_value(self, redis_client: Redis) -> None:
        await cache.set_cached_response(redis_client, "progressive_hint", "prompt X", "respuesta X")
        result = await cache.get_cached_response(redis_client, "progressive_hint", "prompt X")
        assert result == "respuesta X"

    async def test_different_prompts_do_not_collide(self, redis_client: Redis) -> None:
        await cache.set_cached_response(redis_client, "progressive_hint", "prompt A", "respuesta A")
        await cache.set_cached_response(redis_client, "progressive_hint", "prompt B", "respuesta B")
        assert (
            await cache.get_cached_response(redis_client, "progressive_hint", "prompt A")
            == "respuesta A"
        )
        assert (
            await cache.get_cached_response(redis_client, "progressive_hint", "prompt B")
            == "respuesta B"
        )

    async def test_different_tasks_do_not_collide_on_same_prompt(self, redis_client: Redis) -> None:
        await cache.set_cached_response(redis_client, "progressive_hint", "mismo prompt", "pista")
        await cache.set_cached_response(
            redis_client, "pedagogical_feedback", "mismo prompt", "retro"
        )
        assert (
            await cache.get_cached_response(redis_client, "progressive_hint", "mismo prompt")
            == "pista"
        )
        assert (
            await cache.get_cached_response(redis_client, "pedagogical_feedback", "mismo prompt")
            == "retro"
        )
