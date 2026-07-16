class PseIntExecutionLimitError(Exception):
    """Raised when an interpreted program exceeds the step budget — this is
    OUR interpreter running inside the API process, so an infinite Mientras/
    Repetir must be bounded here; there's no OS-level sandbox around it like
    there is for Piston-executed languages."""
