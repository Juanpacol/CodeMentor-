from decimal import Decimal

from logica.ai.harness.router import (
    _MODEL_CHAINS,
    _MODEL_PRICES_USD_PER_MTOK,
    estimate_cost_usd,
)


def test_every_model_in_chains_has_a_price_entry() -> None:
    """La tabla de precios y _MODEL_CHAINS deben derivar juntos — si alguien
    agrega/cambia un modelo en una cadena sin actualizar la tabla de
    precios, este test lo atrapa antes de que el costo se calcule mal en
    silencio."""
    all_models = {model for chain in _MODEL_CHAINS.values() for model in chain}
    missing = all_models - set(_MODEL_PRICES_USD_PER_MTOK)
    assert missing == set(), f"modelos sin precio conocido: {missing}"


def test_unknown_model_costs_zero_never_raises() -> None:
    cost = estimate_cost_usd("un-modelo-que-no-existe", 1_000_000, 1_000_000)
    assert cost == Decimal("0")


def test_estimate_cost_usd_arithmetic() -> None:
    # groq/llama-3.1-8b-instant: (0.05, 0.08) USD por millón de tokens.
    cost = estimate_cost_usd("groq/llama-3.1-8b-instant", 1_000_000, 1_000_000)
    assert cost == Decimal("0.13")


def test_ollama_is_free() -> None:
    cost = estimate_cost_usd("ollama/llama3.1", 1_000_000, 1_000_000)
    assert cost == Decimal("0")
