from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI, Header, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.ai.engine import AIEngine
from app.ai.provider import OpenAIProvider, UnavailableAIProvider
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.rate_limit import SlidingWindowRateLimiter
from app.core.security import verify_webhook_secret
from app.database.session import create_engine_and_sessionmaker
from app.events.bus import EventBus
from app.plugins.builtin import future_plugins
from app.plugins.manager import PluginManager
from app.repositories.core import CoreRepository
from app.services.command_center import CommandCenter
from app.services.orchestrator import ConversationOrchestrator
from app.telegram.client import TelegramBotAPI
from app.telegram.middleware import OwnerAuthenticationMiddleware
from app.telegram.parser import TelegramUpdateParser
from app.telegram.service import TelegramUpdateService
from app.version import __version__

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Container:
    settings: Settings
    event_bus: EventBus
    plugin_manager: PluginManager
    telegram: TelegramBotAPI | None
    engine: AsyncEngine | None
    session_factory: async_sessionmaker[AsyncSession] | None
    update_service: TelegramUpdateService | None


async def build_container(settings: Settings) -> Container:
    event_bus = EventBus()
    plugin_manager = PluginManager(event_bus)
    for plugin in future_plugins():
        plugin_manager.register(plugin)
    await plugin_manager.start()

    engine = None
    session_factory = None
    if settings.database_url:
        engine, session_factory = create_engine_and_sessionmaker(settings.database_url)

    telegram = TelegramBotAPI(settings.telegram_bot_token) if settings.telegram_bot_token else None
    provider = (
        OpenAIProvider(
            settings.openai_api_key,
            settings.openai_model,
            settings.openai_timeout_seconds,
            settings.openai_max_retries,
        )
        if settings.openai_api_key
        else UnavailableAIProvider()
    )
    ai = AIEngine(provider, event_bus)

    update_service = None
    if telegram:
        limiter = SlidingWindowRateLimiter(
            settings.ai_rate_limit_requests, settings.ai_rate_limit_window_seconds
        )
        orchestrator = ConversationOrchestrator(
            settings=settings,
            ai=ai,
            telegram=telegram,
            event_bus=event_bus,
            rate_limiter=limiter,
        )
        command_center = CommandCenter(settings, ai, telegram)
        owner_auth = OwnerAuthenticationMiddleware(
            owner_id=settings.telegram_owner_id,
            rate_limiter=SlidingWindowRateLimiter(
                settings.owner_rate_limit_requests,
                settings.owner_rate_limit_window_seconds,
            ),
        )
        update_service = TelegramUpdateService(
            settings=settings,
            telegram=telegram,
            event_bus=event_bus,
            orchestrator=orchestrator,
            command_center=command_center,
            owner_auth=owner_auth,
        )

    return Container(
        settings=settings,
        event_bus=event_bus,
        plugin_manager=plugin_manager,
        telegram=telegram,
        engine=engine,
        session_factory=session_factory,
        update_service=update_service,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        container = await build_container(settings)
        app.state.container = container
        if container.telegram and settings.webhook_url and settings.telegram_webhook_secret:
            try:
                await container.telegram.set_webhook(
                    settings.webhook_url, settings.telegram_webhook_secret
                )
                logger.info("telegram webhook configured")
            except Exception:
                logger.exception("telegram webhook configuration failed")
        try:
            yield
        finally:
            await container.plugin_manager.stop()
            if container.telegram:
                await container.telegram.close()
            if container.engine:
                await container.engine.dispose()

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        lifespan=lifespan,
        docs_url=None if settings.app_env == "production" else "/docs",
        redoc_url=None,
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": settings.app_name, "version": __version__}

    @app.get("/ready")
    async def ready(request: Request):
        container: Container = request.app.state.container
        missing = []
        for name, value in (
            ("TELEGRAM_BOT_TOKEN", settings.telegram_bot_token),
            ("TELEGRAM_OWNER_ID", settings.telegram_owner_id),
            ("TELEGRAM_WEBHOOK_SECRET", settings.telegram_webhook_secret),
            ("OPENAI_API_KEY", settings.openai_api_key),
            ("DATABASE_URL", settings.database_url),
        ):
            if not value:
                missing.append(name)
        if missing or container.engine is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"ready": False, "missing": missing},
            )
        try:
            async with container.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"ready": False, "database": str(exc)},
            ) from exc
        return {"ready": True}

    @app.post("/telegram/webhook")
    async def telegram_webhook(
        request: Request,
        x_telegram_bot_api_secret_token: str | None = Header(default=None),
    ) -> dict[str, bool]:
        container: Container = request.app.state.container
        if not verify_webhook_secret(
            x_telegram_bot_api_secret_token,
            settings.telegram_webhook_secret,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="invalid webhook secret"
            )
        if container.session_factory is None or container.update_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="service not configured"
            )
        body = await request.json()
        parsed = TelegramUpdateParser().parse(body)
        async with container.session_factory() as session:
            repo = CoreRepository(session)
            try:
                await container.update_service.process(repo, parsed)
                await session.commit()
            except Exception:
                await session.rollback()
                raise
        return {"ok": True}

    return app


app = create_app()
