from app.core.errors import AppError


class ProviderUsageError(AppError):
    """Safe provider failure with independently validated usage, never raw output."""

    def __init__(self, error: AppError, input_tokens: int, output_tokens: int) -> None:
        super().__init__(error.code, error.message, error.status)
        self.input_tokens, self.output_tokens = input_tokens, output_tokens
