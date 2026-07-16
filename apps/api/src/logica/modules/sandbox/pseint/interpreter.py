"""A small tree-walking interpreter for the PSeInt subset in grammar.py.

This runs arbitrary student-submitted pseudocode *inside the API process* —
there is no OS-level sandbox around it the way Piston isolates Python/C/etc.
That makes the step budget in `_tick` a hard correctness requirement, not an
optimization: without it, a student's `Mientras Verdadero Hacer` would hang
the request worker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lark import Lark, Token, Tree
from lark.exceptions import UnexpectedInput

from logica.modules.sandbox.pseint.errors import PseIntExecutionLimitError
from logica.modules.sandbox.pseint.grammar import PSEINT_GRAMMAR

_parser = Lark(PSEINT_GRAMMAR, parser="earley", propagate_positions=True)


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    error_line: int | None = None
    error_message: str | None = None


def validate_pseint(source: str) -> ValidationResult:
    """Skill "validar sintaxis PSeInt" (§9.3): parses without executing."""
    try:
        _parser.parse(source)
    except UnexpectedInput as exc:
        message = str(exc).splitlines()[0] if str(exc) else "Error de sintaxis"
        return ValidationResult(
            valid=False, error_line=getattr(exc, "line", None), error_message=message
        )
    return ValidationResult(valid=True)


@dataclass
class TraceStep:
    line: int | None
    variables: dict[str, Any]


@dataclass
class PseIntRunResult:
    stdout: list[str]
    trace: list[TraceStep]
    variables: dict[str, Any]


def _tree(node: Tree[Token] | Token) -> Tree[Token]:
    assert isinstance(node, Tree)
    return node


_TYPE_DEFAULTS: dict[str, Any] = {
    "entero": 0,
    "real": 0.0,
    "caracter": "",
    "cadena": "",
    "logico": False,
}


class _PseIntInterpreter:
    def __init__(self, inputs: list[str] | None = None, max_steps: int = 10_000) -> None:
        self.env: dict[str, Any] = {}
        self.stdout: list[str] = []
        self.trace: list[TraceStep] = []
        self._inputs = list(inputs or [])
        self._input_cursor = 0
        self._steps = 0
        self._max_steps = max_steps

    def run(self, tree: Tree[Token]) -> PseIntRunResult:
        _name, block = tree.children
        self._exec_block(_tree(block))
        return PseIntRunResult(stdout=self.stdout, trace=list(self.trace), variables=dict(self.env))

    def _tick(self) -> None:
        self._steps += 1
        if self._steps > self._max_steps:
            raise PseIntExecutionLimitError(
                "Se excedió el límite de pasos de ejecución (posible ciclo infinito)"
            )

    def _exec_block(self, block: Tree[Token]) -> None:
        for stmt_node in block.children:
            inner = _tree(_tree(stmt_node).children[0])
            self._tick()
            line = None if inner.meta.empty else inner.meta.line
            getattr(self, f"_exec_{inner.data}")(inner)
            self.trace.append(TraceStep(line=line, variables=dict(self.env)))

    def _exec_definir_stmt(self, node: Tree[Token]) -> None:
        *names, tipo = node.children
        default = _TYPE_DEFAULTS.get(str(tipo).lower(), 0)
        for name in names:
            self.env[str(name)] = default

    def _exec_asignacion_stmt(self, node: Tree[Token]) -> None:
        name, expr = node.children
        self.env[str(name)] = self._eval(expr)

    def _exec_escribir_stmt(self, node: Tree[Token]) -> None:
        self.stdout.append("".join(self._to_display(self._eval(e)) for e in node.children))

    def _exec_leer_stmt(self, node: Tree[Token]) -> None:
        for name in node.children:
            raw = self._inputs[self._input_cursor] if self._input_cursor < len(self._inputs) else ""
            self._input_cursor += 1
            self.env[str(name)] = self._coerce_input(raw)

    def _exec_si_stmt(self, node: Tree[Token]) -> None:
        condition = node.children[0]
        then_block = node.children[1]
        else_block = node.children[2] if len(node.children) > 2 else None
        if self._truthy(self._eval(condition)):
            self._exec_block(_tree(then_block))
        elif else_block is not None:
            self._exec_block(_tree(else_block))

    def _exec_mientras_stmt(self, node: Tree[Token]) -> None:
        condition, block = node.children
        while self._truthy(self._eval(condition)):
            self._tick()
            self._exec_block(_tree(block))

    def _exec_para_stmt(self, node: Tree[Token]) -> None:
        children = node.children
        name = str(children[0])
        if len(children) == 5:
            step_expr, block = children[3], children[4]
            step = self._eval(step_expr)
        else:
            block = children[3]
            step = 1

        self.env[name] = self._eval(children[1])
        end = self._eval(children[2])
        while (step >= 0 and self.env[name] <= end) or (step < 0 and self.env[name] >= end):
            self._tick()
            self._exec_block(_tree(block))
            self.env[name] = self.env[name] + step

    def _exec_repetir_stmt(self, node: Tree[Token]) -> None:
        block, condition = node.children
        while True:
            self._tick()
            self._exec_block(_tree(block))
            if self._truthy(self._eval(condition)):
                break

    def _eval(self, node: Tree[Token] | Token) -> Any:
        if isinstance(node, Token):
            return self._eval_token(node)

        data = node.data
        if data == "number" or data == "string":
            child = node.children[0]
            assert isinstance(child, Token)
            return self._eval_token(child)
        if data == "var":
            name = str(node.children[0])
            if name not in self.env:
                raise KeyError(f"Variable no definida: {name}")
            return self.env[name]
        if data == "true_lit":
            return True
        if data == "false_lit":
            return False
        if data == "neg":
            return -self._eval(node.children[0])
        if data == "not_op":
            return not self._truthy(self._eval(node.children[0]))
        if data == "binop_pow":
            base, exponent = node.children
            return self._eval(base) ** self._eval(exponent)
        if data == "binop":
            left, op, right = node.children
            return self._apply_binop(str(op), self._eval(left), self._eval(right))

        raise ValueError(f"Nodo de expresión no soportado: {data}")

    def _eval_token(self, token: Token) -> Any:
        if token.type == "NUMBER":
            text = str(token)
            return float(text) if "." in text else int(text)
        if token.type == "STRING":
            return str(token)[1:-1]
        return str(token)

    def _apply_binop(self, op: str, left: Any, right: Any) -> Any:
        lowered = op.lower()
        if lowered == "y":
            return self._truthy(left) and self._truthy(right)
        if lowered == "o":
            return self._truthy(left) or self._truthy(right)
        if op == "+":
            if isinstance(left, str) or isinstance(right, str):
                return self._to_display(left) + self._to_display(right)
            return left + right
        if op == "-":
            return left - right
        if op == "*":
            return left * right
        if op == "/":
            return left / right
        if op == "%":
            return left % right
        if op == "=":
            return left == right
        if op == "<>":
            return left != right
        if op == "<":
            return left < right
        if op == "<=":
            return left <= right
        if op == ">":
            return left > right
        if op == ">=":
            return left >= right
        raise ValueError(f"Operador no soportado: {op}")

    def _truthy(self, value: Any) -> bool:
        return bool(value)

    def _to_display(self, value: Any) -> str:
        if isinstance(value, bool):
            return "Verdadero" if value else "Falso"
        return str(value)

    def _coerce_input(self, raw: str) -> Any:
        try:
            return float(raw) if "." in raw else int(raw)
        except ValueError:
            return raw


def run_pseint(
    source: str, inputs: list[str] | None = None, max_steps: int = 10_000
) -> PseIntRunResult:
    """Skill "ejecutar PSeInt": parses and interprets, returning stdout, the
    final variable state, and a step-by-step trace (used to grade/auto-author
    "trazado de variables" exercises)."""
    tree = _parser.parse(source)
    interpreter = _PseIntInterpreter(inputs=inputs, max_steps=max_steps)
    return interpreter.run(tree)
