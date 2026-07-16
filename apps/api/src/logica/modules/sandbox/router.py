from fastapi import APIRouter, Depends

from logica.core.errors import ValidationDomainError
from logica.core.security import get_current_user
from logica.modules.sandbox.pseint.errors import PseIntExecutionLimitError
from logica.modules.sandbox.pseint.interpreter import (
    PseIntRunResult,
    ValidationResult,
    run_pseint,
    validate_pseint,
)
from logica.modules.sandbox.schemas import (
    PseIntRunOut,
    PseIntSourceRequest,
    PseIntTraceStepOut,
    PseIntValidationOut,
)
from logica.modules.users.models import User

router = APIRouter(prefix="/sandbox/pseint", tags=["sandbox"])


@router.post("/validate", response_model=PseIntValidationOut)
async def validate(
    payload: PseIntSourceRequest, user: User = Depends(get_current_user)
) -> ValidationResult:
    return validate_pseint(payload.source)


@router.post("/run", response_model=PseIntRunOut)
async def run(payload: PseIntSourceRequest, user: User = Depends(get_current_user)) -> PseIntRunOut:
    try:
        result: PseIntRunResult = run_pseint(payload.source, inputs=payload.inputs)
    except PseIntExecutionLimitError as exc:
        raise ValidationDomainError(str(exc)) from exc
    except Exception as exc:  # invalid programs raise from within Lark/the interpreter
        raise ValidationDomainError(f"No se pudo ejecutar el pseudocódigo: {exc}") from exc

    return PseIntRunOut(
        stdout=result.stdout,
        variables=result.variables,
        trace=[PseIntTraceStepOut(line=s.line, variables=s.variables) for s in result.trace],
    )
