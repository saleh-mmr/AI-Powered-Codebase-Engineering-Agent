class ImportFailure(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.code, self.message, self.retryable = code, message, retryable


class LeaseLost(Exception):
    """This worker may no longer publish progress or results."""
