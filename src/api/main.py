"""
FastAPI application factory.
Creates the app with CORS, auth initialization, and router registration.
Swagger UI available at /docs, ReDoc at /redoc.
"""
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure src/ is on the path
_src_dir = str(Path(__file__).parent.parent)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic for the FastAPI app."""
    import config
    from api.auth.jwt_handler import JWTHandler
    from api.auth.user_db import UserDB
    from api.auth.dependencies import init_auth

    print(f"[API] Initializing FastAPI REST API on port {config.API_PORT}")

    # Initialize JWT handler
    jwt_handler = JWTHandler(
        secret=config.API_JWT_SECRET,
        algorithm=config.API_JWT_ALGORITHM,
        access_expiry_minutes=config.API_JWT_EXPIRY_MINUTES,
        refresh_expiry_days=config.API_JWT_REFRESH_EXPIRY_DAYS,
    )

    # Initialize user database
    user_db = UserDB(db_path=config.API_USER_DB_PATH)

    # Wire up auth dependencies
    init_auth(jwt_handler, user_db)

    # Store on app state for route access
    app.state.jwt_handler = jwt_handler
    app.state.user_db = user_db

    print("[API] Auth system initialized")
    print(f"[API] Swagger UI: http://localhost:{config.API_PORT}/docs")
    print(f"[API] ReDoc: http://localhost:{config.API_PORT}/redoc")

    yield

    print("[API] Shutting down API server")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    import config

    app = FastAPI(
        title="GST Scanner API",
        description=(
            "REST API for GST Scanner - Invoice OCR, parsing, validation, "
            "order processing, and export functionality.\n\n"
            "**Authentication**: Use `/auth/login` to get a JWT token, then pass it "
            "as `Authorization: Bearer <token>` header on protected endpoints."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.API_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )

    # Register routers
    from api.routes.auth_routes import router as auth_router
    from api.routes.invoice_routes import router as invoice_router
    from api.routes.order_routes import router as order_router
    from api.routes.health_routes import router as health_router
    from api.routes.export_routes import router as export_router

    app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
    app.include_router(invoice_router, prefix="/invoices", tags=["Invoices"])
    app.include_router(order_router, prefix="/orders", tags=["Orders"])
    app.include_router(health_router, prefix="/health", tags=["Health"])
    app.include_router(export_router, prefix="/exports", tags=["Exports"])

    # Rate limiting middleware
    from api.middleware.rate_limiter import RateLimitMiddleware
    app.add_middleware(RateLimitMiddleware, requests_per_minute=config.API_RATE_LIMIT_PER_MINUTE)

    @app.get("/", tags=["Root"])
    async def root():
        """API root - redirect to docs."""
        return {
            "service": "GST Scanner API",
            "version": "1.0.0",
            "docs": "/docs",
            "redoc": "/redoc",
            "health": "/health",
        }

    return app
