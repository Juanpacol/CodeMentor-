"""Input/output safety filters (§9.1): every harness call passes through
these before reaching a model and before its response reaches a user. This
is deliberately simple pattern-matching, not a second LLM call — guardrails
that themselves depend on an LLM add latency, cost, and a new failure mode
to every single request."""

import re
from dataclasses import dataclass

from logica.core.errors import PermissionDeniedError

# Heuristic prompt-injection markers: phrases that try to override the
# system framing rather than answer within it. Not exhaustive — a heuristic
# net, not a guarantee — but catches the common classroom-tested attempts.
_INJECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignora(?:r)?\s+(?:las\s+)?instrucciones\s+anteriores",
        r"ignore\s+(?:the\s+)?(?:previous|above)\s+instructions",
        r"olvida\s+(?:todo\s+)?lo\s+anterior",
        r"you\s+are\s+now\s+(?:in\s+)?(?:developer|dan|jailbreak)",
        r"act(?:úa|ua)?\s+como\s+(?:si\s+no\s+tuvieras|un)\s+(?:restricciones|dan)",
        r"dame\s+la\s+respuesta\s+completa",
        r"dame\s+el\s+c[oó]digo\s+completo\s+(?:de la|del)\s+soluci[oó]n",
        r"give\s+me\s+the\s+(?:full|complete)\s+(?:answer|solution|code)",
        r"revela\s+la\s+soluci[oó]n",
    ]
]


class PromptInjectionDetectedError(PermissionDeniedError):
    pass


def check_input_safety(user_text: str) -> None:
    """Raises if the student's message looks like an attempt to manipulate
    the agent into revealing an answer or breaking its framing (RF-31)."""
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(user_text):
            raise PromptInjectionDetectedError(
                "Tu mensaje no pudo procesarse: evita pedirle al asistente que "
                "ignore sus instrucciones o te dé la respuesta completa."
            )


_FULL_SOLUTION_MARKERS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"la\s+respuesta\s+correcta\s+es",
        r"the\s+correct\s+answer\s+is",
        r"aqu[ií]\s+(?:tienes|est[aá])\s+el\s+c[oó]digo\s+completo",
    ]
]


@dataclass(frozen=True)
class OutputCheckResult:
    safe: bool
    reason: str | None = None


def check_output_safety(model_text: str, *, forbid_full_solution: bool) -> OutputCheckResult:
    """Runs before an AI response reaches a student. `forbid_full_solution`
    is true for the Tutor agent during an active evaluation (RF-31) — the
    same text may be perfectly fine as feedback after grading."""
    if forbid_full_solution:
        for pattern in _FULL_SOLUTION_MARKERS:
            if pattern.search(model_text):
                return OutputCheckResult(
                    safe=False, reason="La respuesta del modelo revelaba la solución completa"
                )
    return OutputCheckResult(safe=True)


def anonymize_for_provider(text: str, *, student_alias: str) -> str:
    """Minimización de datos (§9.4): replaces anything that looks like it
    could be the student's real identity with an internal anonymous alias
    before the text is sent to an external LLM provider. Callers are
    responsible for never including full names/document numbers in `text`
    in the first place — this is a defense-in-depth pass, not the only line."""
    return text.replace(student_alias, "[estudiante]") if student_alias else text
