from datetime import date

from logica.modules.progress.service import _streaks


def _days(*iso: str) -> set[date]:
    return {date.fromisoformat(value) for value in iso}


HOY = date(2026, 7, 28)


def test_sin_actividad_no_hay_racha() -> None:
    assert _streaks(set(), HOY) == (0, 0)


def test_cuenta_dias_consecutivos_hacia_atras_desde_hoy() -> None:
    activos = _days("2026-07-26", "2026-07-27", "2026-07-28")
    assert _streaks(activos, HOY) == (3, 3)


def test_hoy_todavia_vacio_no_rompe_la_racha() -> None:
    """A las 9 a.m. nadie ha practicado aún. Cortar la racha ahí castigaría al
    estudiante por la hora a la que abre la página, no por dejar de practicar."""
    activos = _days("2026-07-25", "2026-07-26", "2026-07-27")
    current, _ = _streaks(activos, HOY)
    assert current == 3


def test_la_racha_se_rompe_cuando_ayer_tampoco_hubo_nada() -> None:
    activos = _days("2026-07-24", "2026-07-25", "2026-07-26")
    current, longest = _streaks(activos, HOY)
    assert current == 0
    assert longest == 3


def test_la_racha_maxima_sobrevive_a_una_interrupcion() -> None:
    # Cuatro seguidos en junio, dos ahora: la actual es 2, la máxima sigue en 4.
    activos = _days(
        "2026-06-01",
        "2026-06-02",
        "2026-06-03",
        "2026-06-04",
        "2026-07-27",
        "2026-07-28",
    )
    assert _streaks(activos, HOY) == (2, 4)


def test_un_solo_dia_cuenta_como_racha_de_uno() -> None:
    assert _streaks(_days("2026-07-28"), HOY) == (1, 1)
