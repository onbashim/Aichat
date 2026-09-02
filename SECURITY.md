# Security Policy

Do not commit tokens, API keys, database credentials, webhook secrets, or private conversation exports.
Production secrets belong in Railway Variables. Rotate any credential immediately if it is exposed.

Autopilot is intentionally fail-closed. Changes that weaken Owner authorization, webhook-secret validation,
BusinessBotRights checks, deduplication, or global/per-chat kill switches require security review and tests.
