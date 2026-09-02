from app.core.security import is_owner, verify_webhook_secret

def test_owner_authorization_is_exact():
    assert is_owner(123,123); assert not is_owner(124,123); assert not is_owner(None,123)
def test_webhook_secret_verification():
    assert verify_webhook_secret("secret","secret"); assert not verify_webhook_secret("wrong","secret")
