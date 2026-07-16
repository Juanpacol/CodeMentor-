import pytest

from logica.modules.sandbox.pseint.errors import PseIntExecutionLimitError
from logica.modules.sandbox.pseint.interpreter import run_pseint, validate_pseint


def test_valid_minimal_program() -> None:
    result = validate_pseint(
        """
        Proceso Saludo
            Escribir "Hola mundo";
        FinProceso
        """
    )
    assert result.valid is True
    assert result.error_line is None


def test_syntax_error_reports_line() -> None:
    result = validate_pseint(
        """
        Proceso ConError
            Escribir "Hola"
            Si x Entonces
        FinProceso
        """
    )
    assert result.valid is False
    assert result.error_line is not None


def test_missing_finproceso_is_invalid() -> None:
    result = validate_pseint("Proceso Incompleto\nEscribir 1;\n")
    assert result.valid is False


def test_run_writes_stdout() -> None:
    result = run_pseint(
        """
        Proceso Hola
            Escribir "Hola", " ", "mundo";
        FinProceso
        """
    )
    assert result.stdout == ["Hola mundo"]


def test_definir_and_asignacion() -> None:
    result = run_pseint(
        """
        Proceso Suma
            Definir x, y Como Entero;
            x <- 2;
            y <- 3;
            Escribir x + y;
        FinProceso
        """
    )
    assert result.variables["x"] == 2
    assert result.variables["y"] == 3
    assert result.stdout == ["5"]


def test_si_sino_takes_then_branch() -> None:
    result = run_pseint(
        """
        Proceso Condicional
            Definir x Como Entero;
            x <- 10;
            Si x > 5 Entonces
                Escribir "mayor";
            SiNo
                Escribir "menor";
            FinSi
        FinProceso
        """
    )
    assert result.stdout == ["mayor"]


def test_si_sino_takes_else_branch() -> None:
    result = run_pseint(
        """
        Proceso Condicional
            Definir x Como Entero;
            x <- 1;
            Si x > 5 Entonces
                Escribir "mayor";
            SiNo
                Escribir "menor";
            FinSi
        FinProceso
        """
    )
    assert result.stdout == ["menor"]


def test_mientras_loop_accumulates() -> None:
    result = run_pseint(
        """
        Proceso Ciclo
            Definir x Como Entero;
            x <- 0;
            Mientras x < 5 Hacer
                x <- x + 1;
            FinMientras
            Escribir x;
        FinProceso
        """
    )
    assert result.variables["x"] == 5
    assert result.stdout == ["5"]


def test_para_loop_with_default_step() -> None:
    result = run_pseint(
        """
        Proceso ParaSimple
            Definir i Como Entero;
            Para i <- 1 Hasta 3 Hacer
                Escribir i;
            FinPara
        FinProceso
        """
    )
    assert result.stdout == ["1", "2", "3"]


def test_para_loop_with_explicit_step() -> None:
    result = run_pseint(
        """
        Proceso ParaPaso
            Definir i Como Entero;
            Para i <- 10 Hasta 0 Con Paso -5 Hacer
                Escribir i;
            FinPara
        FinProceso
        """
    )
    assert result.stdout == ["10", "5", "0"]


def test_repetir_hasta_que_runs_at_least_once() -> None:
    result = run_pseint(
        """
        Proceso RepetirUnaVez
            Definir x Como Entero;
            x <- 100;
            Repetir
                Escribir x;
            Hasta Que x > 0;
        FinProceso
        """
    )
    assert result.stdout == ["100"]


def test_leer_consumes_provided_inputs_in_order() -> None:
    result = run_pseint(
        """
        Proceso Lectura
            Definir a, b Como Entero;
            Leer a, b;
            Escribir a + b;
        FinProceso
        """,
        inputs=["4", "6"],
    )
    assert result.stdout == ["10"]


def test_comparison_and_logical_operators() -> None:
    result = run_pseint(
        """
        Proceso Logica
            Definir x Como Entero;
            x <- 7;
            Si x > 5 Y x < 10 Entonces
                Escribir "en rango";
            FinSi
        FinProceso
        """
    )
    assert result.stdout == ["en rango"]


def test_infinite_loop_raises_execution_limit_error() -> None:
    with pytest.raises(PseIntExecutionLimitError):
        run_pseint(
            """
            Proceso Infinito
                Mientras Verdadero Hacer
                    Escribir "otra vez";
                FinMientras
            FinProceso
            """,
            max_steps=200,
        )


def test_trace_records_a_step_per_statement() -> None:
    result = run_pseint(
        """
        Proceso Trazado
            Definir x Como Entero;
            x <- 1;
            x <- x + 1;
        FinProceso
        """
    )
    assert [step.variables.get("x") for step in result.trace] == [0, 1, 2]
