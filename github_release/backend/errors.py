class UserFacingError(RuntimeError):
    """An error that is safe to show without exposing secrets or internals."""


class DocumentError(UserFacingError):
    pass


class LLMError(UserFacingError):
    pass


class StructuredOutputError(LLMError):
    """A safe structured-generation failure with a redacted debug trace."""

    def __init__(self, message: str, *, trace=None):
        super().__init__(message)
        self.trace = trace


class KeyStoreError(UserFacingError):
    pass


class NotFoundError(UserFacingError):
    pass
