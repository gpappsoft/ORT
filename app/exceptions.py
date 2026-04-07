from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

class CustomExceptionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except CustomException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"message": exc.message},
            )
        except Exception as exc:
            return JSONResponse(
                status_code=500,
                content={"message": "Internal Server Error"},
            )

class CustomException(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)

