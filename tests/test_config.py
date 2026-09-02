from app.core.config import Settings


def test_postgres_url_is_normalized_for_asyncpg():
    settings = Settings(database_url="postgresql://user:pass@db/name")
    assert settings.database_url == "postgresql+asyncpg://user:pass@db/name"


def test_autopilot_is_disabled_by_default():
    assert Settings().autopilot_enabled is False


def test_ai_automation_is_disabled_by_default():
    assert Settings().ai_automation_enabled is False
