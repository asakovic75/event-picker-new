from typing import Optional, Any
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime

class ErrorCode:
    AUTH_REQUIRED = 1000
    INVALID_CREDENTIALS = 1001
    TOKEN_EXPIRED = 1002
    TOKEN_INVALID = 1003
    EVENT_NOT_FOUND = 2000
    USER_NOT_FOUND = 2001
    VALIDATION_ERROR = 3000
    INVALID_CITY = 3001
    INVALID_CATEGORY = 3002
    RATE_LIMIT_EXCEEDED = 4000
    GEMINI_ERROR = 4001
    INTERNAL_ERROR = 5000

class AppException(HTTPException):
    def __init__(self, code: int, message: str, status_code: int = 400, details: Optional[Any] = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(status_code=status_code, detail=message)

def error_response(code: int, message: str, status_code: int = 400, details: Optional[Any] = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code,
            "message": message,
            "details": details,
            "timestamp": datetime.utcnow().isoformat()
        }
    )