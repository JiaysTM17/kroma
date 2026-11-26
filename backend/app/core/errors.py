from __future__ import annotations

from app.domain.enums import ErrorCode


class AppError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        status_code: int = 400,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(
            code=ErrorCode.NOT_FOUND,
            message=message,
            status_code=404,
            retryable=False,
        )


class ConflictError(AppError):
    def __init__(
        self,
        message: str = "Resource conflict",
        code: ErrorCode = ErrorCode.CONFLICT,
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            status_code=409,
            retryable=False,
        )


class PayloadTooLargeError(AppError):
    def __init__(
        self,
        message: str = "Payload exceeds maximum allowed size",
        code: ErrorCode = ErrorCode.PAYLOAD_TOO_LARGE,
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            status_code=413,
            retryable=False,
        )


class UnsupportedMediaTypeError(AppError):
    def __init__(
        self,
        message: str = "Unsupported media type",
        code: ErrorCode = ErrorCode.UNSUPPORTED_MEDIA_TYPE,
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            status_code=415,
            retryable=False,
        )


class ValidationAppError(AppError):
    def __init__(
        self,
        message: str = "Validation error",
        code: ErrorCode = ErrorCode.VALIDATION_ERROR,
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            status_code=422,
            retryable=False,
        )


class SecurityError(AppError):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        status_code: int = 422,
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            status_code=status_code,
            retryable=False,
        )


class InternalStorageError(AppError):
    def __init__(self, message: str = "Storage operation failed") -> None:
        super().__init__(
            code=ErrorCode.INTERNAL_ERROR,
            message=message,
            status_code=500,
            retryable=True,
        )
