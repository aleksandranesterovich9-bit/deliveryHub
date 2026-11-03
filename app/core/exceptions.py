"""Business errors raised by the application layer.

They know nothing about HTTP: the API layer maps them to status codes
(see `app/api/errors.py`), and the worker simply logs them.
"""


class AppError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    pass


class ConflictError(AppError):
    """Duplicates and actions that are not allowed in the current state."""


class AuthenticationError(AppError):
    pass


class PermissionDeniedError(AppError):
    pass


class TooManyRequestsError(AppError):
    def __init__(self, message: str, retry_after: int) -> None:
        super().__init__(message)
        self.retry_after = retry_after
