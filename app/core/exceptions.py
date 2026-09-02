class TelegramAIError(Exception):
    """Base application error."""


class PermissionDenied(TelegramAIError):
    pass


class RateLimitExceeded(TelegramAIError):
    pass


class InvalidAction(TelegramAIError):
    pass
