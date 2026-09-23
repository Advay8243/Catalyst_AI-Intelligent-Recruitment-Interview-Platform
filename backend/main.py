from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api import router
from backend.calling_api import router as calling_router
from backend.config import get_settings
from backend.review_api import router as review_router
from backend.services.ai.errors import AIProviderError
from backend.services.core import ConflictError, NotFoundError


settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(NotFoundError)
async def not_found_handler(_: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ConflictError)
async def conflict_handler(_: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(AIProviderError)
async def ai_provider_error_handler(_: Request, exc: AIProviderError) -> JSONResponse:
    status_code = 503 if exc.retryable else 502
    return JSONResponse(
        status_code=status_code,
        content={
            "detail": str(exc),
            "operation": exc.operation,
            "retryable": exc.retryable,
        },
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(router)
app.include_router(calling_router)
app.include_router(review_router)
