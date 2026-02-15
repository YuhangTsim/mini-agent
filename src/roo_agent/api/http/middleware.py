"""Middleware for HTTP API (CORS, error handling, etc.)."""

from __future__ import annotations

from fastapi import Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Callable


def setup_cors(app) -> None:
    """Configure CORS middleware for local development."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",  # Vite dev server
            "http://127.0.0.1:5173",
            "http://localhost:3000",  # Alternative frontend port
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


async def error_handler_middleware(request: Request, call_next: Callable):
    """Global error handling middleware."""
    try:
        response = await call_next(request)
        return response
    except ValueError as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Validation Error", "detail": str(e)},
        )
    except KeyError as e:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "Not Found", "detail": str(e)},
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Internal Server Error", "detail": str(e)},
        )
