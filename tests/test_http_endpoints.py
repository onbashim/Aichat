from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_health_returns_200():
    app = create_app(Settings(app_env="test"))
    with TestClient(app) as client: response = client.get("/health")
    assert response.status_code == 200; assert response.json()["status"] == "ok"


def test_webhook_rejects_invalid_secret_before_processing():
    app = create_app(Settings(app_env="test", telegram_webhook_secret="expected-secret"))
    with TestClient(app) as client:
        response = client.post("/telegram/webhook", headers={"X-Telegram-Bot-Api-Secret-Token":"wrong-secret"}, json={"update_id":1,"message":{}})
    assert response.status_code == 403
