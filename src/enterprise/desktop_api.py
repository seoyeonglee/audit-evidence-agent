"""Loopback desktop transport; domain identity still requires a separate bearer."""

import argparse
import os
import secrets
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from src.platform.routes import create_router as operations_router
from .routes import create_router as enterprise_router


def create_desktop_app(secret):
    if not secret or len(secret) < 32:
        raise RuntimeError("Desktop transport secret required")
    app = FastAPI(title="Local Audit Agent")

    @app.middleware("http")
    async def desktop_transport(request: Request, call_next):
        if not secrets.compare_digest(
            request.headers.get("X-Desktop-Secret", ""), secret
        ):
            return JSONResponse(
                {"detail": "Desktop transport authorization required"}, status_code=403
            )
        return await call_next(request)

    @app.get("/desktop/health")
    def health():
        return {"status": "ready", "profile": "local-synthetic-offline"}

    app.include_router(operations_router(demo_enabled=True))
    app.include_router(enterprise_router(demo_enabled=True))
    return app


def main():
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    uvicorn.run(
        create_desktop_app(os.environ.get("AUDIT_DESKTOP_SECRET")),
        host="127.0.0.1",
        port=args.port,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
