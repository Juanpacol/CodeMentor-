"""Seed de datos demo. Se completa incrementalmente a medida que existen los modelos
de dominio (Fase 1: institución/usuarios/grupos; Fase 2: temas/lenguajes; ...).
"""

import asyncio

import structlog

logger = structlog.get_logger()


async def seed() -> None:
    logger.info("seed_start")
    # TODO(Fase 1+): crear institución demo, docente, estudiantes, grupo piloto.
    logger.info("seed_done")


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
